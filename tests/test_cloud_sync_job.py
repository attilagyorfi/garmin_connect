from datetime import date

import pytest

from cloud_sync_job import (
    MAX_TRANSIENT_RETRIES, _advance_activities, _advance_hr_zones,
    _earliest_activity_date, _is_retryable_error, _new_job, _public,
    _resume_failed_job, _retry_delay, _schedule_retry,
)
from garmin_sync import GarminSyncError


def test_empty_sync_status_is_idle():
    assert _public(None) == {
        "status": "idle",
        "phase": "idle",
        "progress": 0,
        "message": "Még nem indult szinkron.",
    }


def test_new_job_starts_activity_backfill_without_discarding_cache():
    raw = {"activities": [{"activityId": 1}]}
    job = _new_job(raw)
    assert job["status"] == "running"
    assert job["phase"] == "activities"
    assert job["raw"] is raw


def test_earliest_activity_date_ignores_invalid_rows():
    rows = [
        {"startTimeLocal": "not-a-date"},
        {"startTimeGMT": "2024-03-02T08:00:00Z"},
        {"startTimeLocal": "2023-11-07 06:30:00"},
    ]
    assert _earliest_activity_date(rows) == date(2023, 11, 7)


def test_activity_step_merges_page_then_moves_to_hr_zones():
    class Client:
        def get_activities(self, offset, limit):
            assert (offset, limit) == (0, 100)
            return [{
                "activityId": 2,
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2025-01-03 08:00:00",
            }]

    class Sync:
        client = Client()

        @staticmethod
        def _merge_records(old, new, key):
            assert key == "activityId"
            return old + new

    job = _new_job({"activities": [{"activityId": 1}]})
    _advance_activities(job, Sync())
    assert job["phase"] == "hr_zones"
    assert job["activities_fetched"] == 2
    assert job["hr_zone_ids"] == ["2"]
    assert job["earliest_date"] == "2025-01-03"


@pytest.mark.parametrize("message", [
    "429 Too Many Requests",
    "Garmin rate limit",
    "Connection timed out",
    "503 Service Unavailable",
])
def test_transient_garmin_errors_are_retryable(message):
    assert _is_retryable_error(RuntimeError(message))


def test_retry_backoff_is_bounded_and_keeps_progress():
    job = _new_job({"activities": [{"activityId": 1}]})
    job.update(activity_offset=300, activities_fetched=301, progress=12)

    _schedule_retry(job, RuntimeError("429 Too Many Requests"))

    assert job["status"] == "running"
    assert job["phase"] == "activities"
    assert job["activity_offset"] == 300
    assert job["activities_fetched"] == 301
    assert job["retry_after_seconds"] == _retry_delay(1)
    assert job["next_retry_at"]
    assert "raw" not in _public(job)


def test_retry_exhaustion_can_resume_the_same_run():
    job = _new_job({"activities": [{"activityId": 1}]})
    job["retry_count"] = MAX_TRANSIENT_RETRIES
    run_id = job["run_id"]

    _schedule_retry(job, RuntimeError("429 Too Many Requests"))

    assert job["status"] == "failed"
    assert job["resume_phase"] == "activities"
    resumed = _resume_failed_job(job)
    assert resumed["run_id"] == run_id
    assert resumed["status"] == "running"
    assert resumed["phase"] == "activities"
    assert resumed["retry_count"] == 0


def test_hr_zone_rate_limit_does_not_advance_cursor_or_become_missing_data():
    class Client:
        @staticmethod
        def get_activity_hr_in_timezones(_activity_id):
            raise RuntimeError("429 Too Many Requests")

    class Sync:
        client = Client()

    job = _new_job({
        "activities": [{"activityId": 9, "activityType": {"typeKey": "running"}}],
    })
    job.update(phase="hr_zones", hr_zone_ids=["9"], hr_zones_done=0, hr_zones_total=1)

    with pytest.raises(GarminSyncError, match="átmenetileg"):
        _advance_hr_zones(job, Sync())

    assert job["hr_zones_done"] == 0
    assert "hr_zone_minutes" not in job["raw"]["activities"][0]
