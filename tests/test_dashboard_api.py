from dashboard_api import build_dashboard_payload, sync_dashboard


def test_dashboard_payload_has_frontend_contract(tmp_path):
    payload = build_dashboard_payload(tmp_path)
    assert payload["source"] == "demo"
    assert 0 <= payload["readiness"] <= 100
    assert len(payload["metrics"]) == 4
    assert len(payload["heat"]) == 84
    assert payload["decision"]["title"]
    assert payload["trends"]
    assert payload["sessions"]
    assert len(payload["zones"]) == 5


def test_full_sync_is_requested(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("dashboard_api.GarminSync.sync", lambda self, days: calls.append(days))
    monkeypatch.setattr("dashboard_api.build_dashboard_payload", lambda cache_dir: {"source": "garmin"})
    assert sync_dashboard(tmp_path)["source"] == "garmin"
    assert calls == [None]
