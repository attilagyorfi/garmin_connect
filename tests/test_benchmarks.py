from datetime import date

import pytest

from benchmarks import (
    SOURCES, aerobic_card, aerobic_percentile, athlete_benchmarks, fitness_age_card, level_for, rhr_card, rhr_percentile,
    sleep_card, steps_card, strength_card, vo2max_card, vo2max_percentile,
)

TODAY = date(2026, 10, 5)
ATHLETE = {"sex": "male", "age": 35}


def test_levels_use_rounded_percentile_boundaries():
    assert level_for(59.97) == (2, "jó")
    assert level_for(24.4) == (0, "építkező")
    assert level_for(95) == (4, "elit")


def test_vo2max_percentile_matches_hunt_mean_and_sd():
    assert vo2max_percentile(49.1, "male", 35)[0] == pytest.approx(50)
    assert vo2max_percentile(49.1 + 7.5, "male", 35)[0] == pytest.approx(84.13, abs=0.01)
    assert vo2max_percentile(40.0, "female", 72)[1][:2] == (70, 120)


def test_vo2max_card_reports_next_goal_and_trend():
    card = vo2max_card({**ATHLETE, "vo2max_running": 51.0, "vo2max_history": [{"date": "2026-06-01", "running": 49.1}, {"date": "2026-10-01", "running": 51.0}]}, TODAY)
    assert card["percentile"] == 60 and card["category"] == "jó"
    assert "a „kiváló” szinthez" in card["nextGoal"]
    assert "50. percentilis" in card["trend"] and "+10 pont" in card["trend"]
    assert card["sources"] == ["hunt2013"]


def test_vo2max_card_needs_sex_age_and_value():
    assert vo2max_card({"age": 35, "vo2max_running": 50}, TODAY)["status"] == "missing"
    assert vo2max_card({**ATHLETE}, TODAY)["status"] == "missing"


def test_aerobic_percentile_interpolates_ehis_bins():
    shares = (33.9, 26.9, 20.3, 19.0)
    assert aerobic_percentile(0, shares) == (0.0, False)
    assert aerobic_percentile(150, shares) == (pytest.approx(60.8), False)
    assert aerobic_percentile(400, shares) == (pytest.approx(81.1), True)


def test_aerobic_card_uses_closed_weeks_and_who_weighting():
    weeks = [{"week_start": "2026-09-07", "moderate": 100, "vigorous": 40, "equivalent": 180},
             {"week_start": "2026-09-14", "moderate": 100, "vigorous": 40, "equivalent": 180},
             {"week_start": "2026-10-05", "moderate": 0, "vigorous": 0, "equivalent": 0}]
    card = aerobic_card({**ATHLETE, "intensity_weeks": weeks}, TODAY)
    assert card["value"] == 140 and card["cohort"] == "35–44 éves magyar férfiak"
    assert "teljesíted a WHO-ajánlást" in card["detail"]


def test_strength_card_counts_last_four_weeks():
    activities = [{"startTimeLocal": f"2026-09-{day:02d} 07:00:00", "kind": "strength"} for day in (10, 14, 17, 21, 24, 28, 30, 30, 1)]
    card = strength_card(ATHLETE, activities, TODAY, lambda item: item["kind"] == "strength")
    assert card["value"] == 2.0 and card["atLeast"] and card["percentile"] == 71


def test_rhr_lower_is_better_and_marked_informative():
    assert rhr_percentile(69, (47, 50, 52, 55, 61, 69, 76, 84, 89, 95, 101)) == 50
    card = rhr_card(ATHLETE, [55, 56, 54, 55])
    assert card["percentile"] == 90 and card["confidence"] == "tájékoztató" and card["caveat"]


def test_sleep_steps_and_fitness_age_cards():
    assert sleep_card([7.5] * 12 + [6.0] * 2)["category"] == "kiváló"
    assert sleep_card([7.5] * 9 + [6.0] * 5)["category"] == "jó"
    assert sleep_card([7.0])["status"] == "missing"
    assert steps_card({"age": 65, "avg_daily_steps": 8100})["category"] == "kiváló"
    assert steps_card({"age": 30, "avg_daily_steps": 8100})["category"] == "jó"
    card = fitness_age_card({"age": 40, "fitness_age": 33.0, "achievable_fitness_age": 30.0})
    assert card["headline"].startswith("7,0 évvel fiatalabb") and "30,0" in card["nextGoal"]


def test_athlete_benchmarks_lists_only_used_sources():
    result = athlete_benchmarks({**ATHLETE, "vo2max_running": 50.0}, [], [], [], TODAY, lambda item: False)
    assert [card["key"] for card in result["cards"]] == ["vo2max", "aerobic", "strength", "rhr", "sleep", "steps", "fitness_age"]
    assert {source["key"] for source in result["sources"]} <= set(SOURCES)
    assert athlete_benchmarks(None, [], [], [], TODAY, lambda item: False) is None
