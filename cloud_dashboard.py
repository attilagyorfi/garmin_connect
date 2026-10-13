"""Durable storage keys and the per-user dashboard snapshot read path.

Syncing is done by cloud_sync_job with the user's own stored Garmin session only."""
from __future__ import annotations

from typing import Any

from cloud_cache import load_json, load_user_json


RAW_CACHE_KEY = "garmin_raw_cache_v1"
DASHBOARD_KEY = "dashboard_snapshot_v1"


class NoDashboardData(RuntimeError):
    """No snapshot exists yet; this is not a service outage."""


def dashboard_snapshot(user_id: str | None = None) -> dict[str, Any]:
    payload = load_user_json(user_id, DASHBOARD_KEY) if user_id else load_json(DASHBOARD_KEY)
    if not payload:
        raise NoDashboardData("Még nincs feltöltött Garmin-adat. Indíts szinkronizálást.")
    return payload
