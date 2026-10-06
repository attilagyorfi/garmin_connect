from datetime import date

from garmin_profile import (
    athlete_summary, estimated_one_rep_max, fetch_profile_metrics, parse_body_composition, parse_daily_steps,
    parse_fitness_age, parse_intensity_minutes, parse_max_metrics, parse_personal_records, parse_race_predictions,
    computed_bmi, parse_user_profile, strength_bests, strength_set_candidates, summarize_exercise_sets,
)


def test_user_profile_reads_nested_user_data_and_converts_grams():
    parsed = parse_user_profile({"userData": {"gender": "FEMALE", "birthDate": "1991-06-02", "height": 168.0, "weight": 61500.0, "vo2MaxRunning": 44.0}})
    assert parsed == {"sex": "female", "birth_date": "1991-06-02", "height_cm": 168.0, "weight_kg": 61.5, "vo2max_running": 44.0, "vo2max_cycling": None}


def test_user_profile_tolerates_missing_data():
    assert parse_user_profile(None)["sex"] is None
    assert parse_user_profile({"userData": {"gender": None, "weight": 0}})["weight_kg"] is None


def test_max_metrics_builds_sorted_history_and_latest_values():
    payload = [
        {"generic": {"calendarDate": "2026-09-01", "vo2MaxPreciseValue": 50.4}, "cycling": None},
        {"generic": {"calendarDate": "2026-06-01", "vo2MaxValue": 49}, "cycling": {"calendarDate": "2026-06-01", "vo2MaxValue": 47}},
    ]
    parsed = parse_max_metrics(payload)
    assert parsed["vo2max_running"] == 50.4
    assert parsed["vo2max_cycling"] == 47
    assert [row["date"] for row in parsed["vo2max_history"]] == ["2026-06-01", "2026-09-01"]


def test_fitness_age_and_race_predictions():
    assert parse_fitness_age({"fitnessAge": 31.2, "chronologicalAge": 38})["fitness_age"] == 31.2
    assert parse_fitness_age({"components": {"bmi": {"value": 23.9}}})["fitness_age_bmi"] == 23.9
    assert parse_race_predictions([{"time5K": 1400, "time10K": 2950, "timeHalfMarathon": 6500, "timeMarathon": 14000}])["10k"] == 2950


def test_body_composition_uses_latest_weigh_in_and_skips_empty_rows():
    parsed = parse_body_composition({"dateWeightList": [
        {"calendarDate": "2026-09-20", "weight": 80200.0, "bmi": 24.8, "bodyFat": 18.1},
        {"calendarDate": "2026-10-01", "weight": 79400.0, "bmi": 24.5, "bodyFat": 17.6},
        {"calendarDate": "2026-10-02", "weight": None},
    ], "totalAverage": {"weight": 79800.0}})
    assert parsed["body_weight_kg"] == 79.4
    assert parsed["bmi"] == 24.5
    assert len(parsed["body_history"]) == 2


def test_intensity_minutes_count_vigorous_double():
    weeks = parse_intensity_minutes([{"calendarDate": "2026-09-28", "moderateValue": 100, "vigorousValue": 40, "weeklyGoal": 150}])
    assert weeks == [{"week_start": "2026-09-28", "moderate": 100, "vigorous": 40, "equivalent": 180, "goal": 150}]


def test_daily_steps_accepts_nested_values():
    days = parse_daily_steps([{"calendarDate": "2026-10-01", "values": {"totalSteps": 9100, "stepGoal": 8000}}, {"calendarDate": "2026-10-02", "totalSteps": 4000}])
    assert [day["steps"] for day in days] == [9100, 4000]


def test_personal_records_label_running_distances():
    records = parse_personal_records([{"typeId": 3, "activityType": "running", "value": 1320.5, "prStartTimeGmtFormatted": "2026-08-01T07:00:00.0", "activityId": 9}, {"typeId": 99}])
    assert records == [{"type_id": 3, "activity_type": "running", "label": "5 km", "value": 1320.5, "date": "2026-08-01", "activity_id": "9"}]


def test_exercise_sets_keep_active_sets_with_most_probable_exercise():
    sets = summarize_exercise_sets({"exerciseSets": [
        {"setType": "ACTIVE", "repetitionCount": 5, "weight": 100000.0, "exercises": [{"category": "SQUAT", "name": "BACK_SQUAT", "probability": 92}, {"category": "LUNGE", "probability": 8}]},
        {"setType": "REST", "repetitionCount": None},
    ]})
    assert sets == [{"category": "SQUAT", "exercise": "BACK_SQUAT", "reps": 5, "weight_kg": 100.0}]


def test_strength_candidates_only_recent_unfetched_strength_activities():
    activities = [
        {"activityId": 1, "activityType": {"typeKey": "strength_training"}, "startTimeLocal": "2026-09-01 07:00:00"},
        {"activityId": 2, "activityType": {"typeKey": "strength_training"}, "startTimeLocal": "2024-01-01 07:00:00"},
        {"activityId": 3, "activityType": {"typeKey": "running"}, "startTimeLocal": "2026-09-02 07:00:00"},
        {"activityId": 4, "activityType": {"typeKey": "strength_training"}, "startTimeLocal": "2026-09-03 07:00:00", "exercise_sets": []},
    ]
    assert strength_set_candidates(activities, date(2026, 10, 5)) == ["1"]


def test_strength_bests_use_epley_and_ignore_high_rep_sets():
    assert round(estimated_one_rep_max(100, 5), 1) == 116.7
    activities = [{"startTimeLocal": "2026-09-01 07:00:00", "exercise_sets": [
        {"category": "SQUAT", "reps": 5, "weight_kg": 100}, {"category": "SQUAT", "reps": 20, "weight_kg": 90}, {"category": "SQUAT", "reps": 3, "weight_kg": 105},
        {"category": "UNKNOWN", "reps": 5, "weight_kg": 200}, {"category": "CARDIO", "reps": 10, "weight_kg": 20},
    ]}]
    bests = strength_bests(activities, date(2026, 10, 5))
    assert bests["SQUAT"]["e1rm_kg"] == 116.7 and set(bests) == {"SQUAT"}


def test_fetch_profile_metrics_records_source_status_per_endpoint():
    class Client:
        def get_user_profile(self):
            return {"userData": {"gender": "MALE", "birthDate": "1990-01-01", "weight": 80000.0}}

        def get_max_metrics_range(self, start, end):
            return [{"generic": {"calendarDate": end, "vo2MaxPreciseValue": 52.1}}]

        def get_fitnessage_data(self, day):
            raise RuntimeError("boom")

        def get_body_composition(self, start, end):
            return {"dateWeightList": []}

        def get_weekly_intensity_minutes(self, start, end):
            return []

        def get_daily_steps(self, start, end):
            return [{"calendarDate": end, "totalSteps": 7000}]

        def get_personal_record(self):
            return []

        def get_race_predictions(self):
            return {"time5K": 1500}

        def get_endurance_score(self, day):
            return {"overallScore": 6000}

    def safe_call(call, default, errors, label):
        try:
            result = call()
            return default if result is None else result
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}")
            return default

    errors = []
    profile = fetch_profile_metrics(Client(), safe_call, errors, date(2026, 10, 5))
    assert profile["sex"] == "male" and profile["weight_kg"] == 80.0 and profile["vo2max_running"] == 52.1
    assert profile["sources"]["fitness_age"] == "error" and profile["sources"]["body_composition"] == "ok"
    assert profile["sources"]["intensity_minutes"] == "empty" and profile["sources"]["daily_steps"] == "ok"
    assert errors == ["profile:fitness_age: RuntimeError"]
    summary = athlete_summary(profile, [], date(2026, 10, 5))
    assert summary["age"] == 36 and summary["avg_daily_steps"] == 7000
    assert summary["bmi"] is None  # no height and no Garmin BMI
    assert computed_bmi(81.0, 180.0) == 25.0
    assert athlete_summary({"weight_kg": 81.0, "height_cm": 180.0}, [], date(2026, 10, 5))["bmi"] == 25.0
