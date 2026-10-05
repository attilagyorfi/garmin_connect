from datetime import date, timedelta

import cloud_sync_job
from cloud_sync_job import (
    _advance_activities, _advance_hr_zones, _advance_wellness, _authenticated_sync,
    _earliest_activity_date, _merged_activities, _new_job, _public,
)


class FakeStore:
    """In-memory stand-in for the Postgres-backed SyncStore."""

    def __init__(self, base=None):
        self.base = base or {}
        self.items = {}
        self.writes = []

    def base_raw(self):
        return self.base

    def stage(self, kind, items):
        self.writes.append((kind, dict(items)))
        bucket = self.items.setdefault(kind, {})
        for key, value in items.items():
            bucket[key] = {**bucket.get(key, {}), **value}

    def staged(self, kind):
        return dict(self.items.get(kind, {}))

    def known_wellness_dates(self, start, end):
        dates = {item["date"] for item in self.base.get("wellness", [])} | set(self.items.get("wellness", {}))
        return {value for value in dates if start <= value <= end}


class Sync:
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _safe_call(call, default, errors, label):
        return call()


def test_empty_sync_status_is_idle():
    assert _public(None) == {
        "status": "idle",
        "phase": "idle",
        "progress": 0,
        "message": "Még nem indult szinkron.",
    }


def test_new_job_does_not_carry_raw_payload():
    job = _new_job()
    assert job["status"] == "running"
    assert job["phase"] == "activities"
    assert "raw" not in job


def test_earliest_activity_date_ignores_invalid_rows():
    rows = [
        {"startTimeLocal": "not-a-date"},
        {"startTimeGMT": "2024-03-02T08:00:00Z"},
        {"startTimeLocal": "2023-11-07 06:30:00"},
    ]
    assert _earliest_activity_date(rows) == date(2023, 11, 7)


def test_activity_step_stages_only_the_fetched_page_then_moves_to_hr_zones():
    class Client:
        def get_activities(self, offset, limit):
            assert (offset, limit) == (0, 100)
            return [{
                "activityId": 2,
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2025-01-03 08:00:00",
            }]

    store = FakeStore({"activities": [{"activityId": 1, "activityType": {"typeKey": "strength_training"}, "startTimeLocal": "2025-01-05 08:00:00"}]})
    job = _new_job()
    _advance_activities(job, Sync(Client()), store)
    assert store.writes == [("activity", {"2": {"activityId": 2, "activityType": {"typeKey": "running"}, "startTimeLocal": "2025-01-03 08:00:00"}})]
    assert job["phase"] == "hr_zones"
    assert job["activities_fetched"] == 1
    assert job["hr_zone_ids"] == ["2"]
    assert job["earliest_date"] == "2025-01-03"


def test_hr_zone_step_stages_partial_records_that_merge_onto_cached_activities():
    class Client:
        def get_activity_hr_in_timezones(self, activity_id):
            return [{"zoneNumber": 1, "secsInZone": 600}]

    store = FakeStore({"activities": [{"activityId": 7, "activityName": "Futás", "hr_zone_minutes": None}]})
    job = {**_new_job(), "phase": "hr_zones", "hr_zone_ids": ["7"], "earliest_date": date.today().isoformat()}
    _advance_hr_zones(job, Sync(Client()), store)
    assert store.writes == [("activity", {"7": {"hr_zone_minutes": [{"zoneNumber": 1, "secsInZone": 600}]}})]
    assert job["phase"] == "wellness"
    assert "hr_zone_ids" not in job
    merged = _merged_activities(store)
    assert merged == [{"activityId": 7, "activityName": "Futás", "hr_zone_minutes": [{"zoneNumber": 1, "secsInZone": 600}]}]


def test_wellness_step_skips_cached_days_and_stages_only_new_ones():
    start = date.today() - timedelta(days=2)
    calls = []

    class Client:
        def get_hrv_data(self, day):
            calls.append(day)
            return {"hrvSummary": {"lastNightAvg": 60}}

        def get_sleep_data(self, day):
            return {"dailySleepDTO": {"sleepTimeSeconds": 7 * 3600}}

        def get_heart_rates(self, day):
            return {"restingHeartRate": 50}

    store = FakeStore({"wellness": [{"date": start.isoformat(), "hrv": 55}]})
    job = {**_new_job(), "phase": "wellness", "wellness_cursor": start.isoformat(), "wellness_total": 3}
    _advance_wellness(job, Sync(Client()), store)
    assert calls == [(start + timedelta(days=1)).isoformat(), date.today().isoformat()]
    assert sorted(store.staged("wellness")) == calls
    assert store.staged("wellness")[calls[0]]["sleep_hours"] == 7
    assert job["phase"] == "finalize"
    assert job["wellness_done"] == 3


def test_authenticated_sync_reuses_stored_tokens_and_saves_refreshed_ones(monkeypatch):
    seen, saved = {}, []

    class FakeGarminSync:
        def __init__(self, cache_dir, email, password, tokens):
            seen.update(email=email, tokens=tokens)

        def authenticate(self):
            return None

        def export_tokens(self):
            return '{"di_token": "new"}'

    monkeypatch.setattr(cloud_sync_job, "GarminSync", FakeGarminSync)
    monkeypatch.setattr(cloud_sync_job, "load_credentials", lambda user_id: ("a@example.com", "titok"))
    monkeypatch.setattr(cloud_sync_job, "load_tokens", lambda user_id: '{"di_token": "old"}')
    monkeypatch.setattr(cloud_sync_job, "save_tokens", lambda user_id, tokens: saved.append(tokens))
    _authenticated_sync("user-1", "run-1")
    assert seen == {"email": "a@example.com", "tokens": '{"di_token": "old"}'}
    assert saved == ['{"di_token": "new"}']
