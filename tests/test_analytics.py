import numpy as np
import pandas as pd

from analytics import (
    ReadinessResult, build_daily_frames, cardio_load, data_quality,
    exponential_load, explainable_readiness, modality, musculoskeletal_load,
    performance_management, personal_baseline, red_flags, robust_z_score,
    strength_load, training_decision, weekly_summary,
)
from garmin_sync import demo_data


def demo_frames(days=90):
    payload = demo_data(days)
    return payload, *build_daily_frames(payload, payload["demo_feedback"])


def test_baseline_and_robust_z_score():
    series = pd.Series([50.0] * 27 + [200.0])
    baseline = personal_baseline(series)
    assert baseline["median"] == 50
    assert baseline["stable"] is True
    assert robust_z_score(50, series) == 0


def test_baseline_requires_valid_window_and_stability():
    assert personal_baseline(pd.Series([1.0] * 10))["stable"] is False
    try:
        personal_baseline(pd.Series([1]), 10)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid window accepted")


def test_cardio_fallback_order():
    load, method, confidence = cardio_load({"duration_min": 60, "hr_zone_minutes": [5, 10, 20, 10, 5], "avg_hr": 140, "max_hr": 180})
    assert (load, method, confidence) == (150, "hr_zones_edwards", "high")
    assert cardio_load({"duration_min": 60, "avg_hr": 135, "max_hr": 180})[1] == "heart_rate_duration"
    assert cardio_load({"duration_min": 60, "calories": 500})[1] == "calorie_proxy"
    assert cardio_load({"duration_min": 60})[1] == "duration_proxy"


def test_session_and_musculoskeletal_load():
    activity = {"duration_min": 50, "type": "strength_training", "distance_km": 0, "ascent_m": 0, "descent_m": 0}
    assert strength_load(activity, {"rpe": 8})[:2] == (400, "session_rpe")
    assert musculoskeletal_load(activity, {"focus": "lower body"}) == 150


def test_atl_ctl_tsb_use_time_constants_and_previous_day():
    load = pd.Series([0.0, 100.0, 0.0])
    atl = exponential_load(load, 7)
    assert np.isclose(atl.iloc[1], (1 - np.exp(-1 / 7)) * 100)
    pmc = performance_management(load)
    assert pmc.loc[1, "tsb"] == 0
    assert pmc.loc[2, "tsb"] < 0


def test_modalities_and_daily_multiload():
    payload, wellness, activities = demo_frames()
    assert modality("functional_strength_training") == "Strength / Functional"
    assert {"cardio_load", "strength_load", "musculoskeletal_load", "hybrid_load"} <= set(wellness.columns)
    assert not activities.empty


def test_quality_and_missing_component_reweighting():
    _, frame, _ = demo_frames()
    high = data_quality(frame.iloc[-1], 28, True, 1)
    assert high["level"] == "magas"
    frame.loc[frame.index[-1], "hrv"] = np.nan
    result = explainable_readiness(frame)
    assert "HRV" in result.missing
    assert result.score is not None
    assert sum(c["weight"] for c in result.components) in range(98, 103)


def test_readiness_explanation_and_confidence():
    payload, frame, _ = demo_frames()
    result = explainable_readiness(frame, payload["demo_checkins"].get(str(frame.index[-1].date())))
    assert 0 <= result.score <= 100
    assert result.confidence in {"magas", "közepes", "alacsony"}
    assert all({"score", "weight", "interpretation"} <= set(c) for c in result.components)


def test_pain_and_illness_override():
    _, frame, _ = demo_frames()
    result = ReadinessResult(95, "magas", [], ["jó"], [], [])
    pain = training_decision(result, frame, {"pain": "significant", "illness": False})
    sick = training_decision(result, frame, {"pain": "none", "illness": True})
    assert pain["type"] == "Mobilitás / prehab"
    assert sick["type"] == "Teljes pihenő"


def test_low_confidence_is_conservative():
    _, frame, _ = demo_frames()
    result = ReadinessResult(95, "alacsony", [], [], [], ["HRV"])
    assert training_decision(result, frame)["type"] == "Aktív regeneráció"


def test_red_flags_and_weekly_summary():
    _, frame, activities = demo_frames()
    flags = red_flags(frame, {"pain": "significant", "illness": False})
    assert any(item["title"] == "Jelentős fájdalom" for item in flags)
    summary = weekly_summary(frame, activities, flags)
    assert summary["total_load"] >= 0
    assert isinstance(summary["recommendations"], list)
