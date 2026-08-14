import numpy as np
import pandas as pd

from analytics import (
    ReadinessResult, build_daily_frames, cardio_load, data_quality, extract_hr_zone_minutes,
    deload_taper_recommendation, evaluate_training_plans, event_preparation_analysis,
    exponential_load, explainable_readiness, modality, musculoskeletal_load,
    plan_adjustment_message, plan_completion_status,
    performance_management, personal_baseline, red_flags, robust_z_score,
    mountain_readiness, mountain_weekly_trends, strength_load, training_decision, weekly_plan_template, weekly_summary,
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


def test_hr_zone_payload_variants_are_normalized_to_minutes():
    list_payload = [{"zoneNumber": 1, "secsInZone": 600}, {"zoneNumber": 2, "secsInZone": 1200}]
    dict_payload = {"zones": {"zone1": {"minutes": 5}, "zone4": 600}}
    assert extract_hr_zone_minutes(list_payload)[:2] == [10, 20]
    assert extract_hr_zone_minutes(dict_payload) == [5, 0, 0, 10, 0]
    assert extract_hr_zone_minutes({"unexpected": "shape"}) == [0, 0, 0, 0, 0]


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
    assert {"zone2_min", "high_intensity_min", "lower_body_load"} <= set(wellness.columns)
    assert wellness["zone2_min"].sum() > 0
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
    assert summary["zone2_min"] is not None
    assert isinstance(summary["recommendations"], list)


def test_consecutive_lower_body_load_triggers_recovery_flag():
    _, frame, _ = demo_frames()
    frame["lower_body_load"] = 0.0
    frame.loc[frame.index[-4], "lower_body_load"] = 50
    frame.loc[frame.index[-2:], "lower_body_load"] = 100
    assert any("alsótest" in item["title"].lower() for item in red_flags(frame))


def test_plan_completion_boundaries():
    assert plan_completion_status(60, 0) == "elmaradt"
    assert plan_completion_status(60, 40) == "részben teljesült"
    assert plan_completion_status(60, 60) == "teljesült"
    assert plan_completion_status(60, 90) == "túlteljesült"


def test_plans_match_manual_first_then_same_day_modality():
    activities = pd.DataFrame([
        {"activity_id": "11", "date": pd.Timestamp("2026-08-14"), "modality": "Cardio", "duration_min": 70},
        {"activity_id": "12", "date": pd.Timestamp("2026-08-14"), "modality": "Strength / Functional", "duration_min": 45},
    ])
    plans = [
        {"id": 1, "planned_date": "2026-08-14", "modality": "Cardio", "duration_min": 60, "intensity": "közepes", "matched_activity_id": None},
        {"id": 2, "planned_date": "2026-08-14", "modality": "Cardio", "duration_min": 45, "intensity": "magas", "matched_activity_id": "12"},
    ]
    evaluated = evaluate_training_plans(plans, activities)
    assert evaluated[0]["actual_activity_id"] == "11"
    assert evaluated[0]["status"] == "teljesült"
    assert evaluated[1]["actual_activity_id"] == "12"
    assert evaluated[1]["match_method"] == "kézi"


def test_plan_adjustment_does_not_recommend_catching_up_missed_sessions():
    plans = [{"planned_date": "2026-08-01", "status": "elmaradt", "intensity": "közepes"}] * 2
    assert "Ne próbáld egyszerre bepótolni" in plan_adjustment_message(plans)


def test_near_event_triggers_explainable_taper():
    _, frame, _ = demo_frames()
    result = deload_taper_recommendation(frame, [{"event_date": "2026-08-20"}], today="2026-08-14")
    assert result["type"] == "taper"
    assert result["reduction_pct"] == 40
    assert "közelgő_esemény" in result["rules"]


def test_multiple_fatigue_signals_trigger_deload():
    _, frame, _ = demo_frames()
    frame.loc[frame.index[-7:], "hybrid_tsb"] = -25
    feedback = {str(index): {"rpe": 9} for index in range(3)}
    result = deload_taper_recommendation(frame, [], feedback=feedback, today=frame.index[-1])
    assert result["type"] == "deload"
    assert result["duration_days"] == 7


def test_event_analysis_reports_specific_gaps():
    activities = pd.DataFrame([{"date": pd.Timestamp("2026-08-10"), "modality": "Cardio", "distance_km": 5, "ascent_m": 100, "duration_min": 45}])
    goal = {"event_date": "2026-10-01", "event_type": "terepfutás", "distance_km": 30, "elevation_m": 1500}
    result = event_preparation_analysis(goal, activities, today="2026-08-14")
    assert result["status"] == "hiányos"
    assert len(result["gaps"]) >= 3


def test_weekly_template_honors_rest_day_and_time_budget():
    goal = {"weekly_hours": 5, "cardio_target_pct": 60, "rest_day": "szerda"}
    plans = weekly_plan_template(goal, "2026-08-17")
    assert len(plans) == 5
    assert all(pd.Timestamp(plan["planned_date"]).weekday() != 2 for plan in plans)
    assert sum(plan["duration_min"] for plan in plans) <= 300


def test_mountain_readiness_is_explainable_and_goal_specific():
    _, _, activities = demo_frames()
    goal = {"event_type": "magashegyi trekking", "distance_km": 30, "elevation_m": 1800}
    result = mountain_readiness(activities, {}, goal, today=activities["date"].max())
    assert 0 <= result["score"] <= 100
    assert result["confidence"] in {"magas", "közepes", "alacsony"}
    assert {"Táv", "Szintemelkedés", "Back-to-back"} <= {item["name"] for item in result["components"]}
    assert result["metrics"]["ascent_28d_m"] >= 0


def test_mountain_weekly_trends_flag_abrupt_progression():
    activities = pd.DataFrame([
        {"activity_id":"1", "date":pd.Timestamp("2026-08-03"), "distance_km":10, "ascent_m":500, "descent_m":500, "duration_min":120},
        {"activity_id":"2", "date":pd.Timestamp("2026-08-10"), "distance_km":20, "ascent_m":1000, "descent_m":1000, "duration_min":240},
    ])
    weekly, warnings = mountain_weekly_trends(activities, {"1":{"pack_kg":4}, "2":{"pack_kg":8}})
    assert len(weekly) == 2
    assert {warning["metric"] for warning in warnings} >= {"distance_km", "ascent_m", "pack_kg_max"}
