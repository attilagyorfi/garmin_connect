from datetime import date, timedelta

import pandas as pd

from tips import (
    MAX_TIPS, generate_tips, hrv_tip, inactivity_tip, intensity_tip, load_ramp_tip, record_tip, resting_hr_tip,
    sleep_tip, streak_tip, volume_change_tip, vo2max_tip, weekly_digest,
)

TODAY = date(2026, 10, 7)  # Wednesday


def wellness(days=40, **columns):
    index = pd.date_range(end=pd.Timestamp(TODAY), periods=days, freq="D")
    frame = pd.DataFrame(index=index)
    for name, values in columns.items():
        frame[name] = values if isinstance(values, list) else [values] * days
    return frame


def activities(rows):
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_load_ramp_levels():
    assert load_ramp_tip(wellness(hybrid_atl=80.0, hybrid_ctl=50.0))["priority"] == 90
    assert load_ramp_tip(wellness(hybrid_atl=70.0, hybrid_ctl=50.0))["tone"] == "warn"
    assert load_ramp_tip(wellness(hybrid_atl=30.0, hybrid_ctl=50.0))["tone"] == "nudge"
    assert load_ramp_tip(wellness(hybrid_atl=50.0, hybrid_ctl=50.0)) is None
    assert load_ramp_tip(wellness(hybrid_atl=9.0, hybrid_ctl=3.0)) is None


def test_hrv_and_resting_hr_compare_with_personal_baseline():
    assert hrv_tip(wellness(hrv=[60.0] * 33 + [50.0] * 7))["tone"] == "warn"
    assert hrv_tip(wellness(hrv=[60.0] * 33 + [66.0] * 7))["tone"] == "celebrate"
    assert hrv_tip(wellness(hrv=[60.0] * 40)) is None
    tip = resting_hr_tip(wellness(resting_hr=[50.0] * 37 + [57.0] * 3))
    assert tip["tone"] == "warn" and "szakember" in tip["action"]
    assert resting_hr_tip(wellness(resting_hr=[50.0] * 37 + [53.0] * 3)) is None


def test_sleep_debt_and_good_sleep():
    assert sleep_tip(wellness(sleep_hours=[7.5] * 35 + [5.5, 5.8, 5.9, 7.0, 7.2]))["tone"] == "warn"
    assert sleep_tip(wellness(sleep_hours=7.4))["tone"] == "celebrate"
    assert sleep_tip(wellness(sleep_hours=[7.5] * 35 + [6.8, 7.2, 6.9, 7.0, 7.2])) is None


def test_intensity_mix_uses_only_zone_tracked_sessions():
    rows = [{"date": TODAY - timedelta(days=i), "duration_min": 60, "zone2_min": 20, "high_intensity_min": 25, "hr_zone_minutes": [1]} for i in range(2)]
    rows.append({"date": TODAY, "duration_min": 90, "zone2_min": None, "high_intensity_min": None, "hr_zone_minutes": None})
    assert intensity_tip(activities(rows), TODAY)["key"] == "intensity" and intensity_tip(activities(rows), TODAY)["tone"] == "warn"
    easy = [{"date": TODAY - timedelta(days=i), "duration_min": 60, "zone2_min": 50, "high_intensity_min": 2, "hr_zone_minutes": [1]} for i in range(2)]
    assert intensity_tip(activities(easy), TODAY) is None


def test_inactivity_streak_and_volume():
    assert inactivity_tip(activities([{"date": TODAY - timedelta(days=5), "duration_min": 30}]), TODAY)["title"] == "5 napja nem edzettél"
    weekly = [{"date": date(2026, 9, 7) + timedelta(days=7 * week + day), "duration_min": 40, "session_load": 100}
              for week in range(4) for day in (0, 2, 4)]
    assert streak_tip(activities(weekly), TODAY)["title"] == "4 hete tartod a ritmust"
    jump = [{"date": date(2026, 9, 22), "duration_min": 100, "session_load": 1}, {"date": date(2026, 9, 29), "duration_min": 150, "session_load": 1}]
    assert volume_change_tip(activities(jump), TODAY)["tone"] == "warn"


def test_record_and_vo2max_tips():
    athlete = {"personal_records": [{"type_id": 3, "label": "5 km", "value": 1335.0, "date": "2026-10-01"}, {"type_id": 4, "label": "10 km", "value": 2856.0, "date": "2026-01-01"}],
               "vo2max_history": [{"date": "2026-07-01", "running": 49.0}, {"date": "2026-10-01", "running": 50.5}]}
    tip = record_tip(athlete, TODAY)
    assert tip["title"] == "Új egyéni csúcs: 5 km" and "22:15" in tip["message"]
    assert vo2max_tip(athlete, TODAY)["tone"] == "celebrate"
    assert record_tip({"personal_records": []}, TODAY) is None


def test_generate_tips_caps_and_keeps_a_positive_signal():
    frame = wellness(hybrid_atl=80.0, hybrid_ctl=50.0, hrv=[60.0] * 33 + [50.0] * 7, resting_hr=[50.0] * 37 + [57.0] * 3,
                     sleep_hours=[7.5] * 35 + [5.5, 5.8, 5.9, 7.0, 7.2])
    rows = [{"date": TODAY - timedelta(days=5), "duration_min": 60, "zone2_min": 10, "high_intensity_min": 30, "hr_zone_minutes": [1], "session_load": 1},
            {"date": TODAY - timedelta(days=6), "duration_min": 60, "zone2_min": 10, "high_intensity_min": 30, "hr_zone_minutes": [1], "session_load": 1},
            {"date": date(2026, 9, 22), "duration_min": 60, "zone2_min": 0, "high_intensity_min": 0, "hr_zone_minutes": None, "session_load": 1}]
    benchmarks = {"cards": [{"key": "strength", "status": "ok", "value": 0.5, "nextGoal": None}]}
    athlete = {"vo2max_history": [{"date": "2026-07-01", "running": 49.0}, {"date": "2026-10-01", "running": 50.5}]}
    tips = generate_tips(frame, activities(rows), athlete, benchmarks, TODAY)
    assert len(tips) == MAX_TIPS and tips[0]["key"] == "load_ramp"
    assert any(tip["tone"] == "celebrate" for tip in tips)


def test_weekly_digest_summarises_last_closed_week():
    frame = wellness(sleep_hours=7.2, hrv=[60.0] * 30 + [54.0] * 10)
    rows = [{"date": date(2026, 9, 29), "duration_min": 60, "session_load": 100, "name": "Futás", "modality": "Cardio"},
            {"date": date(2026, 10, 2), "duration_min": 90, "session_load": 200, "name": "Erő", "modality": "Strength / Functional"},
            {"date": date(2026, 9, 23), "duration_min": 100, "session_load": 100, "name": "Túra", "modality": "Cardio"}]
    digest = weekly_digest(frame, activities(rows), [{"tone": "celebrate", "title": "Szép hét", "action": "x"}], TODAY)
    assert digest["weekStart"] == "2026-09-28" and digest["sessions"] == 2 and digest["minutes"] == 150
    assert digest["changePct"] == 50 and digest["strengthMinutes"] == 90 and digest["highlights"] == ["Szép hét"]
    assert "Erő (90 perc)" in digest["summary"] and "alacsonyabb" in digest["summary"]
