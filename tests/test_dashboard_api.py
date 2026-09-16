from dashboard_api import build_dashboard_payload, sync_dashboard
import pytest
from garmin_sync import demo_data
from analytics import build_daily_frames
from garmin_sync import _wellness_record


def test_dashboard_payload_has_frontend_contract(tmp_path):
    payload = build_dashboard_payload(tmp_path, allow_demo=True)
    assert payload["source"] == "demo"
    assert 0 <= payload["readiness"] <= 100
    assert len(payload["metrics"]) == 5
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
    assert metrics["HRV (éjszakai átlag)"]["score"] is None
    assert metrics["Garmin alváspontszám"]["score"] == round(raw["wellness"][-1]["sleep_score"])
    official_session = next(item for item in result["sessions"] if item["id"] == str(raw["activities"][0]["activityId"]))
    assert official_session["load"] == 123
    assert official_session["loadSource"] == "garmin_activity_training_load"
    assert official_session["aerobicTrainingEffect"] == 3.2
    assert official_session["anaerobicTrainingEffect"] == 1.1
    assert official_session["vo2Max"] == 52.0
    assert len(result["sessions"]) == len(raw["activities"])
    assert result["dataQuality"]["activityCount"] == len(raw["activities"])


def test_missing_measurements_are_not_zero(monkeypatch, tmp_path):
    raw = demo_data(90)
    for key in ("hrv", "sleep_score", "sleep_hours", "resting_hr"):
        raw["wellness"][-1][key] = None
    monkeypatch.setattr("dashboard_api.GarminSync.load_cache", lambda self: raw)
    result = build_dashboard_payload(tmp_path)
    assert {item["name"] for item in result["metrics"]} == {"Hybrid TSB"}
    assert set(result["dataQuality"]["missingMetrics"]) == {"HRV (éjszakai átlag)", "Garmin alváspontszám", "Alvásidő", "Nyugalmi pulzus"}


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
