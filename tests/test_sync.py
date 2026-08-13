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
