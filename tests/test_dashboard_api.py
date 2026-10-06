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


def test_metric_scores_come_from_readiness_components(tmp_path):
    from analytics import build_daily_frames, explainable_readiness
    from garmin_sync import demo_data

    payload = build_dashboard_payload(tmp_path)
    demo = demo_data(365)
    wellness, _ = build_daily_frames(demo, demo["demo_feedback"])
    result = explainable_readiness(wellness, demo["demo_checkins"].get(payload["today"]))
    scores = {item["name"]: item["score"] for item in result.components}
    metrics = {item["name"]: item for item in payload["metrics"]}
    assert metrics["HRV (éjszakai)"]["score"] == scores["HRV"]
    assert metrics["Nyugalmi pulzus"]["score"] == scores["RHR"]
    assert metrics["Alvás"]["score"] == scores["Alvás"]
    assert metrics["Hibrid TSB"]["score"] == scores["Terhelés / TSB"]
    assert all(item["tone"] in {"good", "warn", "bad"} for item in payload["metrics"])


def test_decision_title_comes_from_the_engine_choice(tmp_path, monkeypatch):
    # The engine returns its choice under "type"; a missing mapping silently turned every day into "Regeneráló edzés".
    import dashboard_api

    monkeypatch.setattr(dashboard_api, "training_decision", lambda *args, **kwargs: {"type": "Minőségi hibrid edzés", "duration": "45–75 perc", "max_intensity": "kemény, kontrollált", "rationale": "teszt"})
    payload = build_dashboard_payload(tmp_path)
    assert payload["decision"]["title"] == "Minőségi hibrid edzés"
    assert payload["decision"]["intensity"] == "kemény, kontrollált"
