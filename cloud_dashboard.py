"""Bridge the local analytics/cache model to durable serverless storage."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from cloud_cache import load_json, save_json, sync_lock
from dashboard_api import build_dashboard_payload
from garmin_sync import GarminSync, GarminSyncError


RAW_CACHE_KEY = "garmin_raw_cache_v1"
DASHBOARD_KEY = "dashboard_snapshot_v1"


def dashboard_snapshot() -> dict[str, Any]:
    payload = load_json(DASHBOARD_KEY)
    if not payload:
        raise RuntimeError("Még nincs feltöltött Garmin-adat. Indíts szinkronizálást.")
    return payload


def _write_raw_cache(cache_dir: Path, payload: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "garmin_cache.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def sync_cloud_dashboard() -> dict[str, Any]:
    with sync_lock() as db:
        if db is None:
            raise GarminSyncError("Már fut egy Garmin-szinkron. Várj néhány percet, majd próbáld újra.")
        raw = load_json(RAW_CACHE_KEY, db) or {}
        with tempfile.TemporaryDirectory(prefix="hybrid-garmin-") as directory:
            cache_dir = Path(directory)
            if raw:
                _write_raw_cache(cache_dir, raw)
            synced = GarminSync(cache_dir).sync(None)
            dashboard = build_dashboard_payload(cache_dir)
            save_json(RAW_CACHE_KEY, synced, db)
            save_json(DASHBOARD_KEY, dashboard, db)
            return dashboard
