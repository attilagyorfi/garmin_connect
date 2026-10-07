import pytest
from datetime import date, timedelta

import cloud_sync_job
from garmin_sync import WELLNESS_SCHEMA_VERSION
from cloud_sync_job import (
    _advance_activities, _advance_hr_zones, _advance_profile, _advance_strength_sets, _advance_wellness, _authenticated_sync,
    MAX_TRANSIENT_RETRIES, _earliest_activity_date, _is_retryable_error, _merged_activities, _new_job, _public,
    _resume_failed_job, _schedule_retry, advance_sync,
)
from garmin_sync import GarminSyncError


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
        current = {item["date"] for item in self.base.get("wellness", []) if item.get("metric_schema_version") == WELLNESS_SCHEMA_VERSION}
        dates = current | set(self.items.get("wellness", {}))
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
    assert job["phase"] == "strength_sets"
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

        def get_morning_training_readiness(self, day):
            readiness_calls.append(day)
            return {"score": 77, "level": "HIGH"}

    readiness_calls = []
    store = FakeStore({"wellness": [{"date": start.isoformat(), "hrv": 55, "metric_schema_version": WELLNESS_SCHEMA_VERSION}]})
    job = {**_new_job(), "phase": "wellness", "wellness_cursor": start.isoformat(), "wellness_total": 3}
    _advance_wellness(job, Sync(Client()), store)
    assert calls == [(start + timedelta(days=1)).isoformat(), date.today().isoformat()]
    assert sorted(store.staged("wellness")) == calls
    assert store.staged("wellness")[calls[0]]["sleep_hours"] == 7
    # Official readiness is read only for today; past days keep Garmin's finalized values.
    assert readiness_calls == [date.today().isoformat()]
    assert store.staged("wellness")[calls[-1]]["training_readiness"]["score"] == 77
    assert job["phase"] == "finalize"
    assert job["wellness_done"] == 3


def test_wellness_step_refetches_days_cached_with_an_older_metric_schema():
    day = date.today() - timedelta(days=1)
    calls = []

    class Client:
        def get_hrv_data(self, value):
            calls.append(value)
            return {"hrvSummary": {"lastNightAvg": 58, "status": "BALANCED", "baseline": {"balancedLow": 50, "balancedUpper": 66}}}

        def get_sleep_data(self, value):
            return {}

        def get_heart_rates(self, value):
            return {}

        def get_morning_training_readiness(self, value):
            return {}

    store = FakeStore({"wellness": [{"date": day.isoformat(), "hrv": 61}]})
    job = {**_new_job(), "phase": "wellness", "wellness_cursor": day.isoformat(), "wellness_total": 2}
    _advance_wellness(job, Sync(Client()), store)
    assert calls[0] == day.isoformat()
    staged = store.staged("wellness")[day.isoformat()]
    assert staged["hrv_status"] == "BALANCED" and staged["hrv_baseline_low"] == 50


def test_authenticated_sync_uses_stored_tokenstore_and_saves_refreshed_one(monkeypatch):
    seen, saved = {}, []

    class FakeGarminSync:
        def __init__(self, cache_dir, tokenstore):
            seen.update(tokenstore=tokenstore)

        def authenticate(self):
            return None

        def export_tokens(self):
            return '{"di_token": "new"}'

    monkeypatch.setattr(cloud_sync_job, "GarminSync", FakeGarminSync)
    monkeypatch.setattr(cloud_sync_job, "load_tokenstore", lambda user_id: '{"di_token": "old"}')
    monkeypatch.setattr(cloud_sync_job, "refresh_tokenstore", lambda user_id, tokens: saved.append(tokens))
    _authenticated_sync("user-1", "run-1")
    assert seen == {"tokenstore": '{"di_token": "old"}'}
    assert saved == ['{"di_token": "new"}']


def test_rejected_session_requires_reauth_but_outage_does_not(monkeypatch):
    marked = []

    def fake_sync(message):
        class FakeGarminSync:
            def __init__(self, cache_dir, tokenstore):
                pass

            def authenticate(self):
                raise cloud_sync_job.GarminSyncError(message)
        return FakeGarminSync

    monkeypatch.setattr(cloud_sync_job, "load_tokenstore", lambda user_id: "{}")
    monkeypatch.setattr(cloud_sync_job, "mark_reauth_required", marked.append)
    for message, expected in (("Garmin hitelesítési hiba. Csatlakoztasd újra.", ["u1"]), ("A Garmin átmenetileg nem elérhető.", ["u1"])):
        monkeypatch.setattr(cloud_sync_job, "GarminSync", fake_sync(message))
        with pytest.raises(cloud_sync_job.GarminSyncError):
            _authenticated_sync("u1", "run")
        assert marked == expected


@pytest.mark.parametrize("message", ["429 Too Many Requests", "Garmin rate limit", "Connection timed out", "503 Service Unavailable"])
def test_transient_garmin_errors_are_retryable(message):
    assert _is_retryable_error(RuntimeError(message))


def test_credential_errors_are_not_retryable():
    assert not _is_retryable_error(GarminSyncError("Garmin hitelesítési hiba. Csatlakoztasd újra a fiókot a Beállításokban."))


def test_retry_backoff_is_bounded_and_keeps_progress():
    job = {**_new_job(), "activity_offset": 300, "activities_fetched": 300, "progress": 12}
    _schedule_retry(job)
    assert job["status"] == "running" and job["phase"] == "activities"
    assert job["activity_offset"] == 300
    assert job["retry_after_seconds"] == 2 and job["next_retry_at"]
    for _ in range(MAX_TRANSIENT_RETRIES - 2):
        _schedule_retry(job)
    assert job["retry_after_seconds"] <= 60


def test_retry_exhaustion_can_resume_the_same_run():
    job = {**_new_job(), "phase": "wellness", "retry_count": MAX_TRANSIENT_RETRIES}
    run_id = job["run_id"]
    _schedule_retry(job)
    assert job["status"] == "failed" and job["resume_phase"] == "wellness"
    assert _public(job)["resumable"] is True
    resumed = _resume_failed_job(job)
    assert resumed["run_id"] == run_id
    assert (resumed["status"], resumed["phase"], resumed["retry_count"]) == ("running", "wellness", 0)


def test_hr_zone_rate_limit_does_not_advance_cursor_or_stage_empty_zones():
    class Client:
        @staticmethod
        def get_activity_hr_in_timezones(_activity_id):
            raise RuntimeError("429 Too Many Requests")

    store = FakeStore()
    job = {**_new_job(), "phase": "hr_zones", "hr_zone_ids": ["9"], "hr_zones_done": 0, "hr_zones_total": 1}
    with pytest.raises(GarminSyncError, match="átmenetileg"):
        _advance_hr_zones(job, Sync(Client()), store)
    assert job["hr_zones_done"] == 0
    assert store.staged("activity") == {}


class _Lock:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *args):
        return False


class _Db:
    def rollback(self):
        pass


def _wire_advance(monkeypatch, saved, store, sync_factory):
    monkeypatch.setattr(cloud_sync_job, "sync_lock", lambda user_id: _Lock(_Db()))
    monkeypatch.setattr(cloud_sync_job, "load_user_json", lambda user_id, key, db=None: saved.get(key))
    monkeypatch.setattr(cloud_sync_job, "save_user_json", lambda user_id, key, value, db=None: saved.__setitem__(key, value))
    monkeypatch.setattr(cloud_sync_job, "SyncStore", lambda db, user_id, run_id: store)
    monkeypatch.setattr(cloud_sync_job, "_authenticated_sync", sync_factory)
    store.clear = lambda all_runs=False: store.items.clear()


def test_rate_limited_step_schedules_retry_and_waits_before_calling_garmin(monkeypatch):
    calls = []

    class Client:
        def get_activities(self, offset, limit):
            calls.append(offset)
            raise RuntimeError("429 Too Many Requests")

    saved, store = {}, FakeStore()
    _wire_advance(monkeypatch, saved, store, lambda user_id, run_id: Sync(Client()))
    body, status = advance_sync("user")
    assert status == 202 and body["retry_count"] == 1 and body["retry_after_seconds"] == 2
    body, status = advance_sync("user", body["run_id"])
    assert status == 202 and calls == [0]  # still inside the back-off window


def test_failed_run_resumes_with_staged_data_when_its_run_id_is_sent(monkeypatch):
    class Client:
        def get_activities(self, offset, limit):
            return []

    store = FakeStore()
    store.items["activity"] = {"1": {"activityId": "1", "activityType": {"typeKey": "strength_training"}}}
    failed = {**_new_job(), "status": "failed", "phase": "failed", "resume_phase": "activities", "activity_offset": 100, "resumable": True}
    saved = {cloud_sync_job.SYNC_JOB_KEY: failed}
    _wire_advance(monkeypatch, saved, store, lambda user_id, run_id: Sync(Client()))
    body, status = advance_sync("user", failed["run_id"])
    assert status == 202 and body["run_id"] == failed["run_id"] and body["phase"] == "hr_zones"
    assert "1" in store.staged("activity")  # staged progress was kept, not cleared


def test_failed_run_without_run_id_starts_fresh(monkeypatch):
    class Client:
        def get_activities(self, offset, limit):
            return []

    store = FakeStore()
    store.items["activity"] = {"1": {"activityId": "1"}}
    failed = {**_new_job(), "status": "failed", "phase": "failed", "resume_phase": "activities"}
    saved = {cloud_sync_job.SYNC_JOB_KEY: failed}
    _wire_advance(monkeypatch, saved, store, lambda user_id, run_id: Sync(Client()))
    body, _ = advance_sync("user")
    assert body["run_id"] != failed["run_id"]
