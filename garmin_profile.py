"""Read-only Garmin athlete profile metrics: demographics, VO2max, fitness age, body composition,
activity volume, records and strength sets.

Garmin payloads differ by device, region and library version, so every parser accepts several
candidate keys and returns None/[] instead of failing. ``sources`` records per endpoint whether
data arrived, which keeps missing data visible instead of silently looking like zero.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

PROFILE_VERSION = 1
BODY_HISTORY_DAYS = 365
VO2MAX_HISTORY_DAYS = 365
INTENSITY_WEEKS = 12
STEPS_DAYS = 28
STRENGTH_SETS_DAYS = 365


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _first(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if payload.get(key) not in (None, ""):
            return payload[key]
    return None


def _first_num(payload: Any, *keys: str) -> float | None:
    return _num(_first(payload, *keys))


def _kg(value: Any) -> float | None:
    """Garmin reports body weight in grams; plausible kilogram values pass through unchanged."""
    number = _num(value)
    if number is None or number <= 0:
        return None
    return round(number / 1000, 2) if number > 500 else round(number, 2)


def _iso_day(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):  # epoch milliseconds
        return datetime.fromtimestamp(value / 1000).date().isoformat()
    text = str(value)[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _rows(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    value = _first(payload, *keys)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def parse_user_profile(payload: Any) -> dict[str, Any]:
    data = _first(payload, "userData") if isinstance(payload, dict) else None
    data = data if isinstance(data, dict) else payload if isinstance(payload, dict) else {}
    gender = str(_first(data, "gender", "genderType") or "").lower()
    sex = "male" if gender.startswith("m") else "female" if gender.startswith("f") else None
    return {
        "sex": sex,
        "birth_date": _iso_day(_first(data, "birthDate", "birthdate", "dateOfBirth")),
        "height_cm": _first_num(data, "height", "heightCm"),
        "weight_kg": _kg(_first(data, "weight", "weightInGrams")),
        "vo2max_running": _first_num(data, "vo2MaxRunning"),
        "vo2max_cycling": _first_num(data, "vo2MaxCycling"),
    }


def _vo2_entry(entry: dict[str, Any], sport: str) -> tuple[str | None, float | None]:
    block = entry.get(sport) if isinstance(entry.get(sport), dict) else None
    if not block:
        return None, None
    value = _first_num(block, "vo2MaxPreciseValue", "vo2MaxValue")
    return _iso_day(_first(block, "calendarDate") or entry.get("calendarDate")), value


def parse_max_metrics(payload: Any) -> dict[str, Any]:
    """VO2max history (running = 'generic', cycling) from get_max_metrics(_range)."""
    history: dict[str, dict[str, Any]] = {}
    for entry in _rows(payload, "maxMetrics", "metrics"):
        for sport, key in (("generic", "running"), ("cycling", "cycling")):
            day, value = _vo2_entry(entry, sport)
            if day and value:
                history.setdefault(day, {"date": day})[key] = value
    if isinstance(payload, dict) and not history:
        for sport, key in (("generic", "running"), ("cycling", "cycling")):
            day, value = _vo2_entry(payload, sport)
            if day and value:
                history.setdefault(day, {"date": day})[key] = value
    rows = sorted(history.values(), key=lambda item: item["date"])
    latest_running = next((row["running"] for row in reversed(rows) if row.get("running")), None)
    latest_cycling = next((row["cycling"] for row in reversed(rows) if row.get("cycling")), None)
    return {"vo2max_running": latest_running, "vo2max_cycling": latest_cycling, "vo2max_history": rows}


def parse_fitness_age(payload: Any) -> dict[str, Any]:
    components = _first(payload, "components") if isinstance(payload, dict) else None
    return {
        "fitness_age": _first_num(payload, "fitnessAge"),
        "chronological_age": _first_num(payload, "chronologicalAge"),
        "achievable_fitness_age": _first_num(payload, "achievableFitnessAge"),
        "fitness_age_bmi": _first_num(components.get("bmi") if isinstance(components, dict) else None, "value"),
    }


def computed_bmi(weight_kg: Any, height_cm: Any) -> float | None:
    weight, height = _num(weight_kg), _num(height_cm)
    return round(weight / (height / 100) ** 2, 1) if weight and height else None


def parse_body_composition(payload: Any) -> dict[str, Any]:
    history = []
    for row in _rows(payload, "dateWeightList", "dailyWeightSummaries"):
        day = _iso_day(_first(row, "calendarDate", "summaryDate", "date"))
        weight = _kg(_first(row, "weight"))
        if not day or weight is None:
            continue
        history.append({
            "date": day, "weight_kg": weight, "bmi": _first_num(row, "bmi"),
            "body_fat_pct": _first_num(row, "bodyFat", "bodyFatPercentage"),
            "muscle_mass_kg": _kg(_first(row, "muscleMass")),
        })
    history.sort(key=lambda item: item["date"])
    latest = history[-1] if history else {}
    average = _first(payload, "totalAverage") if isinstance(payload, dict) else None
    return {
        "body_history": history,
        "body_weight_kg": latest.get("weight_kg") or _kg(_first(average, "weight")),
        "bmi": latest.get("bmi") or _first_num(average, "bmi"),
        "body_fat_pct": latest.get("body_fat_pct") or _first_num(average, "bodyFat"),
    }


def parse_intensity_minutes(payload: Any) -> list[dict[str, Any]]:
    """Weekly moderate/vigorous minutes; WHO counts a vigorous minute as two moderate ones."""
    weeks = []
    for row in _rows(payload, "weeklyIntensityMinutes", "values"):
        day = _iso_day(_first(row, "calendarDate", "startDate", "weekStartDate"))
        moderate, vigorous = _first_num(row, "moderateValue", "moderate"), _first_num(row, "vigorousValue", "vigorous")
        if not day or (moderate is None and vigorous is None):
            continue
        weeks.append({"week_start": day, "moderate": moderate or 0, "vigorous": vigorous or 0,
                      "equivalent": (moderate or 0) + 2 * (vigorous or 0), "goal": _first_num(row, "weeklyGoal", "goal")})
    return sorted(weeks, key=lambda item: item["week_start"])


def parse_daily_steps(payload: Any) -> list[dict[str, Any]]:
    days = []
    for row in _rows(payload, "values", "dailySteps"):
        day = _iso_day(_first(row, "calendarDate", "date"))
        values = row.get("values") if isinstance(row.get("values"), dict) else row
        steps = _first_num(values, "totalSteps", "steps")
        if day and steps is not None:
            days.append({"date": day, "steps": steps, "goal": _first_num(values, "stepGoal", "goal")})
    return sorted(days, key=lambda item: item["date"])


RUNNING_RECORDS = {1: "1 km", 2: "1 mérföld", 3: "5 km", 4: "10 km", 5: "Félmaraton", 6: "Maraton", 7: "Leghosszabb futás"}


def parse_personal_records(payload: Any) -> list[dict[str, Any]]:
    records = []
    for row in _rows(payload, "personalRecords"):
        type_id = _num(row.get("typeId"))
        value = _first_num(row, "value")
        if type_id is None or value is None:
            continue
        activity_type = str(_first(row, "activityType") or "").lower()
        label = RUNNING_RECORDS.get(int(type_id)) if activity_type in ("", "running") else None
        records.append({
            "type_id": int(type_id), "activity_type": activity_type or None, "label": label, "value": value,
            "date": _iso_day(_first(row, "prStartTimeGmtFormatted", "prStartTimeLocalFormatted", "actStartDateTimeInGMTFormatted", "prStartTimeGmt")),
            "activity_id": str(row["activityId"]) if row.get("activityId") is not None else None,
        })
    return records


def parse_race_predictions(payload: Any) -> dict[str, float | None]:
    row = payload[-1] if isinstance(payload, list) and payload else payload
    return {
        "5k": _first_num(row, "time5K", "time5k"), "10k": _first_num(row, "time10K", "time10k"),
        "half_marathon": _first_num(row, "timeHalfMarathon"), "marathon": _first_num(row, "timeMarathon"),
    }


def parse_endurance_score(payload: Any) -> dict[str, Any]:
    dto = _first(payload, "enduranceScoreDTO") if isinstance(payload, dict) else None
    source = dto if isinstance(dto, dict) else payload
    return {"endurance_score": _first_num(source, "overallScore", "enduranceScore", "avg"),
            "endurance_classification": _first(source, "classification", "classificationId")}


def summarize_exercise_sets(payload: Any) -> list[dict[str, Any]]:
    """Active strength sets as {exercise, category, reps, weight_kg}; rest sets are dropped."""
    sets = []
    for row in _rows(payload, "exerciseSets"):
        if str(row.get("setType") or "ACTIVE").upper() != "ACTIVE":
            continue
        exercises = row.get("exercises") if isinstance(row.get("exercises"), list) else []
        best = max((item for item in exercises if isinstance(item, dict)), key=lambda item: _num(item.get("probability")) or 0, default={})
        reps = _first_num(row, "repetitionCount", "reps")
        sets.append({
            "category": best.get("category"), "exercise": best.get("name") or best.get("category"),
            "reps": int(reps) if reps is not None else None, "weight_kg": _kg(row.get("weight")),
        })
    return sets


def is_strength_activity(activity: dict[str, Any]) -> bool:
    raw_type = activity.get("activityType", {})
    kind = str(raw_type.get("typeKey", "") if isinstance(raw_type, dict) else raw_type).lower()
    return any(term in kind for term in ("strength", "weight", "functional", "hiit"))


def strength_set_candidates(activities: list[dict[str, Any]], today: date | None = None) -> list[str]:
    cutoff = (today or date.today()) - timedelta(days=STRENGTH_SETS_DAYS)
    ids = []
    for activity in activities:
        if not is_strength_activity(activity) or activity.get("activityId") is None or activity.get("exercise_sets") is not None:
            continue
        day = _iso_day(activity.get("startTimeLocal") or activity.get("startTimeGMT"))
        if day and date.fromisoformat(day) >= cutoff:
            ids.append(str(activity["activityId"]))
    return ids


def estimated_one_rep_max(weight_kg: float, reps: int) -> float:
    """Epley estimate; only meaningful for sets of roughly 1–12 reps."""
    return weight_kg if reps <= 1 else weight_kg * (1 + reps / 30)


# Garmin categories that are not loaded lifts (unrecognised sets, cardio intervals, warm-ups, core holds).
NON_LIFT_CATEGORIES = {"UNKNOWN", "CARDIO", "WARM_UP", "PLANK", "CRUNCH"}


def strength_bests(activities: list[dict[str, Any]], today: date | None = None) -> dict[str, dict[str, Any]]:
    """Best estimated 1RM per exercise category over the strength-set window."""
    cutoff = (today or date.today()) - timedelta(days=STRENGTH_SETS_DAYS)
    bests: dict[str, dict[str, Any]] = {}
    for activity in activities:
        day = _iso_day(activity.get("startTimeLocal") or activity.get("startTimeGMT"))
        if not day or date.fromisoformat(day) < cutoff:
            continue
        for item in activity.get("exercise_sets") or []:
            weight, reps, category = item.get("weight_kg"), item.get("reps"), item.get("category")
            if not category or category in NON_LIFT_CATEGORIES or not weight or not reps or reps > 12:
                continue
            estimate = round(estimated_one_rep_max(float(weight), int(reps)), 1)
            if estimate > bests.get(category, {}).get("e1rm_kg", 0):
                bests[category] = {"e1rm_kg": estimate, "weight_kg": weight, "reps": reps, "date": day}
    return bests


def athlete_summary(profile: dict[str, Any] | None, activities: list[dict[str, Any]], today: date | None = None) -> dict[str, Any] | None:
    """Compact, frontend-facing athlete block for the dashboard payload."""
    if not profile:
        return None
    today = today or date.today()
    birth = profile.get("birth_date")
    age = None
    if birth:
        born = date.fromisoformat(birth)
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    steps = [item["steps"] for item in profile.get("daily_steps") or [] if item.get("steps") is not None]
    keys = ("sex", "height_cm", "weight_kg", "body_fat_pct", "vo2max_running", "vo2max_cycling", "fitness_age",
            "chronological_age", "achievable_fitness_age", "endurance_score", "race_predictions", "personal_records", "sources")
    return {
        **{key: profile.get(key) for key in keys},
        "age": age,
        "bmi": profile.get("bmi") or profile.get("fitness_age_bmi") or computed_bmi(profile.get("weight_kg"), profile.get("height_cm")),
        "vo2max_history": (profile.get("vo2max_history") or [])[-12:],
        "body_history": (profile.get("body_history") or [])[-12:],
        "intensity_weeks": (profile.get("intensity_weeks") or [])[-12:],
        "avg_daily_steps": round(sum(steps) / len(steps)) if steps else None,
        "strength_bests": strength_bests(activities, today),
        "demo": bool(profile.get("demo")),
    }


def fetch_profile_metrics(client: Any, safe_call: Callable[..., Any], errors: list[str], today: date | None = None) -> dict[str, Any]:
    """One bounded batch of read-only calls; each endpoint may fail independently."""
    today = today or date.today()
    iso = today.isoformat()
    sources: dict[str, str] = {}

    def call(label: str, fn: Callable[[], Any], default: Any) -> Any:
        before = len(errors)
        result = safe_call(fn, default, errors, f"profile:{label}")
        sources[label] = "error" if len(errors) > before else "ok" if result not in (None, {}, []) else "empty"
        return result

    profile = parse_user_profile(call("user_profile", lambda: client.get_user_profile(), {}))
    metrics = parse_max_metrics(call("max_metrics", lambda: client.get_max_metrics_range((today - timedelta(days=VO2MAX_HISTORY_DAYS)).isoformat(), iso), []))
    fitness = parse_fitness_age(call("fitness_age", lambda: client.get_fitnessage_data(iso), {}))
    body = parse_body_composition(call("body_composition", lambda: client.get_body_composition((today - timedelta(days=BODY_HISTORY_DAYS)).isoformat(), iso), {}))
    intensity_start = today - timedelta(days=today.weekday() + 7 * (INTENSITY_WEEKS - 1))
    intensity = parse_intensity_minutes(call("intensity_minutes", lambda: client.get_weekly_intensity_minutes(intensity_start.isoformat(), iso), []))
    steps = parse_daily_steps(call("daily_steps", lambda: client.get_daily_steps((today - timedelta(days=STEPS_DAYS - 1)).isoformat(), iso), []))
    records = parse_personal_records(call("personal_records", lambda: client.get_personal_record(), []))
    races = parse_race_predictions(call("race_predictions", lambda: client.get_race_predictions(), {}))
    endurance = parse_endurance_score(call("endurance_score", lambda: client.get_endurance_score(iso), {}))
    return {
        "version": PROFILE_VERSION,
        "fetched_at": datetime.now().astimezone().isoformat(),
        **profile,
        "vo2max_running": metrics["vo2max_running"] or profile["vo2max_running"],
        "vo2max_cycling": metrics["vo2max_cycling"] or profile["vo2max_cycling"],
        "vo2max_history": metrics["vo2max_history"],
        **fitness,
        **body,
        "weight_kg": body["body_weight_kg"] or profile["weight_kg"],
        "bmi": body["bmi"] or fitness["fitness_age_bmi"] or computed_bmi(body["body_weight_kg"] or profile["weight_kg"], profile["height_cm"]),
        "intensity_weeks": intensity,
        "daily_steps": steps,
        "personal_records": records,
        "race_predictions": races,
        **endurance,
        "sources": sources,
    }
