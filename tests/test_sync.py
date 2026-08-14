from datetime import datetime

import pytest

from garmin_sync import GarminSync, GarminSyncError, demo_data


def test_demo_is_deterministic_for_metrics():
    first, second = demo_data(90), demo_data(90)
    assert first["wellness"] == second["wellness"]
    assert len(first["wellness"]) >= 90
    assert first["demo_feedback"] == second["demo_feedback"]


def test_missing_environment_is_clear(monkeypatch, tmp_path):
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    with pytest.raises(GarminSyncError, match="GARMIN_EMAIL"):
        GarminSync(tmp_path).authenticate()


def test_cache_freshness(tmp_path):
    sync = GarminSync(tmp_path, ttl_hours=12)
    sync.save_cache({"synced_at": datetime.now().astimezone().isoformat(), "activities": [], "wellness": []})
    assert sync.cache_is_fresh()


def test_sync_enriches_cardio_activity_with_read_only_hr_zones(tmp_path):
    class FakeClient:
        def get_activities_by_date(self, *_args, **_kwargs):
            return [{"activityId": 7, "activityType": {"typeKey": "running"}, "startTimeLocal": "2026-08-14 08:00:00", "duration": 3600}]

        def get_activity_hr_in_timezones(self, activity_id):
            assert activity_id == "7"
            return [{"zoneNumber": 2, "secsInZone": 1800}]

        def get_hrv_data(self, _day):
            return {"hrvSummary": {"lastNightAvg": 55}}

        def get_sleep_data(self, _day):
            return {"dailySleepDTO": {"sleepScore": 80}}

        def get_heart_rates(self, _day):
            return {"restingHeartRate": 50}

    sync = GarminSync(tmp_path)
    sync.client = FakeClient()
    payload = sync.sync(30)
    assert payload["activities"][0]["hr_zone_minutes"][0]["zoneNumber"] == 2
