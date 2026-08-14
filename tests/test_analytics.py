import numpy as np
import pandas as pd

from analytics import (
    ReadinessResult, build_daily_frames, cardio_load, data_quality, extract_hr_zone_minutes, feature_drift_audit,
    deload_taper_recommendation, evaluate_training_plans, event_preparation_analysis,
    exponential_load, explainable_readiness, modality, musculoskeletal_load,
    plan_adjustment_message, plan_completion_status,
    performance_management, personal_baseline, red_flags, retraining_recommendation, robust_z_score,
    model_promotion_decision, mountain_readiness, mountain_weekly_trends, multiday_readiness, pattern_uncertainty, personal_patterns, strength_load, training_decision, validate_recovery_model, weekly_plan_template, weekly_summary,
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


def test_multiday_readiness_counts_exposure_and_keeps_spo2_contextual():
    activities = pd.DataFrame([
        {"activity_id":"1", "date":pd.Timestamp("2026-08-10"), "duration_min":150, "distance_km":20, "ascent_m":900},
        {"activity_id":"2", "date":pd.Timestamp("2026-08-11"), "duration_min":140, "distance_km":18, "ascent_m":800},
    ])
    wellness = pd.DataFrame({"spo2":[95.0, 96.0]}, index=pd.date_range("2026-08-10", periods=2))
    result = multiday_readiness(activities, wellness, {"1":{"stability_min":30}, "2":{"single_leg_min":30}}, today="2026-08-11")
    assert result["metrics"]["long_days_56d"] == 2
    assert result["metrics"]["consecutive_pairs_56d"] == 1
    assert "medián" in result["spo2_context"]


def test_personal_patterns_require_minimum_valid_days():
    _, frame, activities = demo_frames(30)
    result = personal_patterns(frame.tail(40), activities, minimum_days=60)
    assert result["status"] == "insufficient"
    assert result["associations"] == []


def test_personal_patterns_report_sample_confidence_and_quality():
    payload, frame, activities = demo_frames(120)
    result = personal_patterns(frame, activities, payload["demo_feedback"], minimum_days=60)
    assert result["status"] == "ready"
    assert result["associations"]
    assert all({"rho", "sample_size", "confidence", "statement"} <= set(item) for item in result["associations"])
    assert "missing_pct" in result["quality"] and "outliers" in result["quality"]


def test_pattern_uncertainty_is_deterministic_and_reports_windows():
    payload, frame, activities = demo_frames(120)
    first = pattern_uncertainty(frame, activities, payload["demo_feedback"], bootstrap_samples=50)
    second = pattern_uncertainty(frame, activities, payload["demo_feedback"], bootstrap_samples=50)
    assert first == second
    assert first
    assert all({"ci_low", "ci_high", "stable", "window_estimates"} <= set(item) for item in first)
    assert any(item["window_count"] >= 2 for item in first)


def test_recovery_model_requires_enough_chronological_samples():
    _, frame, activities = demo_frames(90)
    result = validate_recovery_model(frame, activities)
    assert result["status"] == "insufficient"
    assert result["eligible"] is False


def test_recovery_model_beats_baseline_on_known_temporal_signal():
    rng = np.random.default_rng(11)
    days = 240
    sleep = rng.normal(75, 8, days)
    hrv = np.empty(days)
    hrv[0] = 55
    hrv[1:] = 35 + sleep[:-1] * .32 + rng.normal(0, .7, days - 1)
    frame = pd.DataFrame({
        "sleep_score": sleep,
        "hrv": hrv,
        "resting_hr": 52 - (hrv - hrv.mean()) * .15 + rng.normal(0, .3, days),
        "hybrid_tsb": rng.normal(0, 5, days),
        "hybrid_load": rng.uniform(0, 100, days),
    }, index=pd.date_range("2025-01-01", periods=days))
    result = validate_recovery_model(frame, pd.DataFrame())
    assert result["status"] == "validated"
    assert len(result["folds"]) == 3
    assert result["eligible"] is True
    assert result["model_mae"] < result["baseline_mae"]
    assert result["forecast_interval"][0] < result["forecast_interval"][1]
    assert len(result["feature_audit"]) == 6
    assert all("sign_stable" in item for item in result["feature_audit"])
    assert len(result["artifact"]["coefficients"]) == 6
    assert result["data_start"] < result["data_end"]


def test_model_promotion_requires_better_validated_candidate():
    active = [{"id": 1, "active": True, "model_mae": .8}]
    assert model_promotion_decision({"status":"validated", "eligible": True, "model_mae": .7}, active)["promote"] is True
    assert model_promotion_decision({"status":"validated", "eligible": True, "model_mae": .9}, active)["promote"] is False
    assert model_promotion_decision({"status":"validated", "eligible": False, "model_mae": .5}, active)["promote"] is False
    assert model_promotion_decision({"status":"validated", "eligible": True, "model_mae": .9}, [])["promote"] is True


def test_retraining_recommendation_explains_age_data_and_drift():
    active = [{"active":True, "trained_at":"2026-06-01T10:00:00+02:00", "data_end":"2026-06-01"}]
    result = retraining_recommendation(active, {"alerts":2}, "2026-08-01", today="2026-08-14")
    assert result["due"] is True
    assert result["new_data_days"] == 61
    assert result["model_age_days"] == 74
    assert len(result["reasons"]) == 3


def test_retraining_recommendation_is_quiet_for_fresh_model():
    active = [{"active":True, "trained_at":"2026-08-10T10:00:00+02:00", "data_end":"2026-08-10"}]
    result = retraining_recommendation(active, {"alerts":0}, "2026-08-14", today="2026-08-14")
    assert result["due"] is False
    assert result["reasons"] == ["nincs újratanítást indokló jel"]


def test_retraining_recommendation_when_no_active_model():
    assert retraining_recommendation([], {"alerts":0}, "2026-08-14")["due"] is True


def test_feature_drift_audit_detects_recent_distribution_shift():
    rng = np.random.default_rng(7)
    days = 120
    frame = pd.DataFrame({
        "sleep_score": np.r_[rng.normal(75, 2, 60), rng.normal(88, 2, 60)],
        "hrv": rng.normal(55, 3, days),
        "resting_hr": rng.normal(52, 2, days),
        "hybrid_tsb": rng.normal(0, 5, days),
        "hybrid_load": rng.normal(50, 10, days),
    }, index=pd.date_range("2026-01-01", periods=days))
    result = feature_drift_audit(frame, pd.DataFrame(), window=60)
    sleep = next(item for item in result["features"] if item["feature"] == "sleep_score")
    assert result["status"] == "ready"
    assert sleep["severity"] == "magas"
    assert sleep["psi"] >= .25 or sleep["median_shift_iqr"] >= 1


def test_feature_drift_audit_requires_two_windows():
    _, frame, activities = demo_frames(90)
    assert feature_drift_audit(frame.tail(100), activities, window=60)["status"] == "insufficient"
