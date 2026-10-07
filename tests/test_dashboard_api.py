from dashboard_api import build_dashboard_payload, sync_dashboard
import pytest
from garmin_sync import demo_data
from analytics import build_daily_frames
from garmin_sync import _wellness_record


def test_dashboard_payload_has_frontend_contract(tmp_path):
    payload = build_dashboard_payload(tmp_path, allow_demo=True)
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

    payload = build_dashboard_payload(tmp_path, allow_demo=True)
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
    payload = build_dashboard_payload(tmp_path, allow_demo=True)
    assert payload["decision"]["title"] == "Minőségi hibrid edzés"
    assert payload["decision"]["intensity"] == "kemény, kontrollált"


def test_missing_cache_does_not_generate_demo(tmp_path):
    with pytest.raises(ValueError, match="Nincs szinkronizált"):
        build_dashboard_payload(tmp_path)


def test_official_garmin_metrics_are_preferred_and_same_day_sessions_preserved(monkeypatch, tmp_path):
    raw = demo_data(90)
    raw["wellness"][-1]["training_readiness"] = {
        "score": 83,
        "level": "HIGH",
        "sleepScoreFactorPercent": 91,
        "recoveryTime": 180,
    }
    raw["activities"][0].update({
        "activityTrainingLoad": 123.4,
        "aerobicTrainingEffect": 3.2,
        "anaerobicTrainingEffect": 1.1,
        "vO2MaxValue": 52.0,
    })
    duplicate = dict(raw["activities"][0], activityId="additional-session")
    raw["activities"].append(duplicate)
    monkeypatch.setattr("dashboard_api.GarminSync.load_cache", lambda self: raw)
    result = build_dashboard_payload(tmp_path)
    metrics = {item["name"]: item for item in result["metrics"]}
    assert result["readiness"] == 83
    assert result["readinessSource"] == "garmin_training_readiness"
    assert result["decision"]["source"] == "hybrid_rules_using_garmin_readiness"
    assert all(item["source"] in {"garmin", "hybrid"} for item in result["metrics"])
    official_session = next(item for item in result["sessions"] if item["id"] == str(raw["activities"][0]["activityId"]))
    assert official_session["load"] == 123
    assert official_session["loadSource"] == "garmin_activity_training_load"
    assert official_session["aerobicTrainingEffect"] == 3.2
    assert official_session["anaerobicTrainingEffect"] == 1.1
    assert official_session["vo2Max"] == 52.0
    assert len(result["sessions"]) == len(raw["activities"])
    assert result["dataQuality"]["activityCount"] == len(raw["activities"])


def test_data_quality_counts_the_whole_history_not_just_listed_sessions(monkeypatch, tmp_path):
    raw = demo_data(365)
    monkeypatch.setattr("dashboard_api.GarminSync.load_cache", lambda self: raw)
    result = build_dashboard_payload(tmp_path)
    assert len(raw["activities"]) > len(result["sessions"]) == 100
    assert result["dataQuality"]["activityCount"] == len(raw["activities"])
    assert result["dataQuality"]["activityDateFrom"] < result["sessions"][-1]["date"]


def test_missing_measurements_are_not_zero(monkeypatch, tmp_path):
    raw = demo_data(90)
    for key in ("hrv", "sleep_score", "sleep_hours", "resting_hr"):
        raw["wellness"][-1][key] = None
    monkeypatch.setattr("dashboard_api.GarminSync.load_cache", lambda self: raw)
    result = build_dashboard_payload(tmp_path)
    assert {item["name"] for item in result["metrics"]} == {"Hibrid TSB"}
    assert set(result["dataQuality"]["missingMetrics"]) == {"HRV (éjszakai)", "Alvás", "Nyugalmi pulzus"}


def test_hrv_uses_garmin_last_night_average_without_substituting_other_statistics():
    record = _wellness_record(
        "2026-09-16",
        {"hrvSummary": {"weeklyAvg": 61, "lastNight5MinHigh": 88, "status": "BALANCED"}},
        {"dailySleepDTO": {"sleepScore": 82}},
        {"restingHeartRate": 49},
    )
    assert record["hrv"] is None
    assert record["hrv_source"] == "missing"
    assert record["hrv_weekly_avg"] == 61
    assert record["hrv_last_night_5_min_high"] == 88


def test_nonfinite_number_is_missing():
    from dashboard_api import _number
    assert _number(float("inf"), None) is None
    assert _number(float("nan"), None) is None
    assert _number(0, None) == 0
