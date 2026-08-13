from analytics import build_daily_frames, modality, readiness, tsb_zone


def sample_payload():
    return {
        "wellness": [
            {"date": f"2026-08-{day:02d}", "hrv": 55 + day % 3, "sleep_score": 80, "resting_hr": 52}
            for day in range(1, 13)
        ],
        "activities": [
            {
                "startTimeLocal": "2026-08-10 07:00:00",
                "activityName": "Run",
                "activityType": {"typeKey": "running"},
                "duration": 3600,
                "calories": 600,
            },
            {
                "startTimeLocal": "2026-08-11 07:00:00",
                "activityName": "Weights",
                "activityType": {"typeKey": "strength_training"},
                "duration": 2400,
                "calories": None,
            },
        ],
    }


def test_load_and_readiness():
    wellness, activities = build_daily_frames(sample_payload())
    assert activities.iloc[0]["modality"] == "Cardio"
    assert activities.iloc[1]["stress"] == 320
    assert wellness.iloc[-1]["atl"] > wellness.iloc[-1]["ctl"]
    assert readiness(wellness)[0] is not None


def test_categories_and_zones():
    assert modality("functional_strength_training") == "Strength / Functional"
    assert tsb_zone(6)[0] == "Fresh"
    assert tsb_zone(-25)[0] == "Overreaching"
