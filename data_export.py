"""Build a portable, secret-free export for one authenticated user."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cloud_cache import load_user_json
from user_state import load_state


DASHBOARD_KEY = "dashboard_snapshot_v1"
SYNC_JOB_KEY = "garmin_sync_job_v2"
SYNC_PUBLIC_FIELDS = (
    "run_id", "status", "phase", "progress", "message", "activities_fetched",
    "activity_offset", "hr_zones_done", "hr_zones_total", "wellness_done",
    "wellness_total", "started_at", "updated_at", "completed_at", "partial_errors",
    "retry_count", "retry_after_seconds", "next_retry_at", "last_error",
)


def _public_sync_status(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"status": "idle", "phase": "idle", "progress": 0, "message": "Még nem indult szinkron."}
    return {key: job.get(key) for key in SYNC_PUBLIC_FIELDS if job.get(key) is not None}


def build_user_export(user: dict[str, Any]) -> dict[str, Any]:
    """Return only the requesting user's application data, never credentials."""
    user_id = str(user["id"])
    state = load_state(user_id)
    dashboard = load_user_json(user_id, DASHBOARD_KEY)
    sync = _public_sync_status(load_user_json(user_id, SYNC_JOB_KEY))

    return {
        "exportVersion": 1,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "account": {
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role", "member"),
        },
        "preferences": {
            "accent": state.get("accent"),
            "profile": state.get("profile"),
        },
        "planning": {"plans": state.get("plans") or []},
        "selfReported": {
            "checkins": state.get("checkins") or {},
            "activityFeedback": state.get("feedback") or {},
        },
        "assistant": state.get("assistant") or {"memoryEnabled": False, "messages": []},
        "garmin": {
            "dashboard": dashboard,
            "syncStatus": sync,
        },
        "security": {
            "excluded": [
                "jelszó és jelszóhash",
                "munkamenet-cookie és hitelesítési tokenek",
                "Garmin-jelszó és titkosított Garmin-munkamenettoken",
                "más felhasználók adatai",
            ]
        },
    }
