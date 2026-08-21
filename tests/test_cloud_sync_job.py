from datetime import date

from cloud_sync_job import _advance_activities, _earliest_activity_date, _new_job, _public


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
