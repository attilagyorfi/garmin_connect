"""Build a portable, secret-free export for one authenticated user."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from assistant import ASSISTANT_KEY
from cloud_cache import load_user_json
from user_state import load_state

DASHBOARD_KEY = "dashboard_snapshot_v1"
SYNC_JOB_KEY = "garmin_sync_job_v2"
SYNC_PUBLIC_FIELDS = (
    "run_id", "status", "phase", "progress", "message", "activities_fetched",
    "activity_offset", "hr_zones_done", "hr_zones_total", "strength_sets_done", "strength_sets_total",
    "wellness_done", "wellness_total", "started_at", "updated_at", "completed_at", "partial_errors",
)


def _public_sync_status(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"status": "idle", "phase": "idle", "progress": 0, "message": "Még nem indult szinkron."}
    return {key: job.get(key) for key in SYNC_PUBLIC_FIELDS if job.get(key) is not None}


def _assistant_export(user_id: str) -> dict[str, Any]:
    stored = load_user_json(user_id, ASSISTANT_KEY) or {}
    return {
        "consent": bool(stored.get("consent")), "consentAt": stored.get("consentAt"),
        "memoryEnabled": stored.get("memoryEnabled", True),
        "memory": stored.get("memory") or [], "conversation": stored.get("conversation") or [],
    }


def build_user_export(user: dict[str, Any]) -> dict[str, Any]:
    """Return only the requesting user's application data, never credentials."""
    user_id = str(user["id"])
    state = load_state(user_id)
    return {
        "exportVersion": 2,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "account": {"email": user.get("email"), "name": user.get("name"), "role": user.get("role", "member")},
        "preferences": {"accent": state.get("accent"), "profile": state.get("profile")},
        "planning": {"plans": state.get("plans") or []},
        "selfReported": {"checkins": state.get("checkins") or {}, "activityFeedback": state.get("feedback") or {}},
        "assistant": _assistant_export(user_id),
        "garmin": {"dashboard": load_user_json(user_id, DASHBOARD_KEY), "syncStatus": _public_sync_status(load_user_json(user_id, SYNC_JOB_KEY))},
        "security": {
            "excluded": [
                "jelszó és jelszóhash",
                "munkamenet-cookie és hitelesítési tokenek",
                "titkosított Garmin-munkamenettoken",
                "más felhasználók adatai",
            ]
        },
    }
