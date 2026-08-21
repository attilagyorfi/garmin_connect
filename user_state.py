"""Validation and persistence for the single-user desktop application state."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from cloud_cache import load_json, load_user_json, save_json, save_user_json


STATE_KEY = "user_state_v1"
ACCENTS = {"teal", "blue", "violet", "orange", "rose"}
EXPERIENCE = {"kezdő", "középhaladó", "haladó"}
GOALS = {"Hibrid teljesítmény", "Futóteljesítmény", "Erőfejlesztés", "Hegyi állóképesség", "Általános egészség"}
PREFERENCES = {"kiegyensúlyozott", "teljesítmény", "regeneráció"}
DAYS = {"H", "K", "Sze", "Cs", "P", "Szo", "V"}
PLAN_TYPES = {"Kardió", "Erő", "Futás", "Túrázás", "Kerékpár", "Mobilitás", "Pihenő"}
PLAN_INTENSITIES = {"regeneráló", "könnyű", "könnyű–közepes", "közepes", "közepes–magas", "magas"}
AVATAR_PRESETS = {"athlete", "strength", "endurance", "classic", "photo"}


def empty_state() -> dict[str, Any]:
    return {"version": 2, "profile": None, "accent": "teal", "checkins": {}, "feedback": {}, "plans": []}


def _text(value: Any, maximum: int) -> str:
    return str(value or "").strip()[:maximum]


def validate_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Érvénytelen profil.")
    experience = value.get("experience", "középhaladó")
    goal = value.get("goal", "Hibrid teljesítmény")
    preference = value.get("preference", "kiegyensúlyozott")
    training_days = [day for day in value.get("trainingDays", []) if day in DAYS]
    rest_day = value.get("restDay", "V")
    if experience not in EXPERIENCE or goal not in GOALS or preference not in PREFERENCES or rest_day not in DAYS:
        raise ValueError("A profil választott értéke érvénytelen.")
    avatar_preset = value.get("avatarPreset", "athlete")
    avatar_image = str(value.get("avatarImage") or "")
    if avatar_preset not in AVATAR_PRESETS:
        raise ValueError("Érvénytelen profilavatar.")
    if avatar_image and (len(avatar_image) > 220_000 or not avatar_image.startswith(("data:image/webp;base64,", "data:image/png;base64,", "data:image/jpeg;base64,"))):
        raise ValueError("A profilkép formátuma vagy mérete érvénytelen.")
    return {
        "name": _text(value.get("name"), 80) or "Sportoló",
        "experience": experience,
        "goal": goal,
        "eventName": _text(value.get("eventName"), 120),
        "eventDate": _text(value.get("eventDate"), 10),
        "weeklyHours": max(1, min(30, int(value.get("weeklyHours", 8)))),
        "strengthRatio": max(0, min(100, int(value.get("strengthRatio", 30)))),
        "trainingDays": list(dict.fromkeys(training_days)) or ["H", "K", "Sze", "Cs", "P", "Szo"],
        "restDay": rest_day,
        "limitations": _text(value.get("limitations"), 1000),
        "preference": preference,
        "avatarPreset": avatar_preset,
        "avatarImage": avatar_image,
    }


def validate_checkin(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Érvénytelen check-in.")
    def scale(key: str, default: int) -> int:
        return max(1, min(5, int(value.get(key, default))))
    return {
        "soreness": scale("soreness", 2), "fatigue": scale("fatigue", 2),
        "motivation": scale("motivation", 4), "stress": scale("stress", 2),
        "pain": bool(value.get("pain", False)), "illness": bool(value.get("illness", False)),
        "note": _text(value.get("note"), 1000), "savedAt": _text(value.get("savedAt"), 40),
    }


def validate_feedback(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Érvénytelen edzés-visszajelzés.")
    feeling = value.get("feeling", "rendben")
    if feeling not in {"kiváló", "rendben", "nehéz", "rossz"}:
        raise ValueError("Érvénytelen közérzet.")
    return {"rpe": max(1, min(10, int(value.get("rpe", 5)))), "feeling": feeling, "note": _text(value.get("note"), 2000), "savedAt": _text(value.get("savedAt"), 40)}


def validate_plan(value: Any, plan_id: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Érvénytelen edzésterv.")
    planned_date = _text(value.get("date"), 10)
    date.fromisoformat(planned_date)
    plan_type = value.get("type", "Kardió")
    intensity = value.get("intensity", "közepes")
    if plan_type not in PLAN_TYPES or intensity not in PLAN_INTENSITIES:
        raise ValueError("Az edzésterv választott értéke érvénytelen.")
    clean_id = _text(plan_id or value.get("id"), 80)
    if not clean_id:
        clean_id = f"plan-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    return {
        "id": clean_id,
        "date": planned_date,
        "type": plan_type,
        "title": _text(value.get("title"), 160) or f"{plan_type} edzés",
        "duration": max(0 if plan_type == "Pihenő" else 10, min(600, int(value.get("duration", 60)))),
        "intensity": intensity,
        "rpe": max(1, min(10, int(value.get("rpe", 5)))),
        "purpose": _text(value.get("purpose"), 500),
        "note": _text(value.get("note"), 2000),
        "matchedActivityId": _text(value.get("matchedActivityId"), 120),
        "status": "planned",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def load_state(user_id: str | None = None) -> dict[str, Any]:
    stored = (load_user_json(user_id, STATE_KEY) if user_id else load_json(STATE_KEY)) or {}
    return {**empty_state(), **stored, "version": 2, "checkins": stored.get("checkins") or {}, "feedback": stored.get("feedback") or {}, "plans": stored.get("plans") or []}


def apply_patch(patch: Any, user_id: str | None = None) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("Érvénytelen módosítás.")
    state = load_state(user_id)
    if "profile" in patch:
        state["profile"] = validate_profile(patch["profile"])
    if "accent" in patch:
        if patch["accent"] not in ACCENTS:
            raise ValueError("Érvénytelen akcentusszín.")
        state["accent"] = patch["accent"]
    if "checkin" in patch:
        item = patch["checkin"]
        day = _text(item.get("date") if isinstance(item, dict) else "", 10)
        date.fromisoformat(day)
        state["checkins"][day] = validate_checkin(item.get("value"))
    if "checkins" in patch:
        if not isinstance(patch["checkins"], dict) or len(patch["checkins"]) > 730:
            raise ValueError("Érvénytelen check-in előzmény.")
        for day, value in patch["checkins"].items():
            date.fromisoformat(_text(day, 10))
            state["checkins"][_text(day, 10)] = validate_checkin(value)
    if "feedback" in patch:
        item = patch["feedback"]
        activity_id = _text(item.get("activityId") if isinstance(item, dict) else "", 120)
        if not activity_id:
            raise ValueError("Hiányzó aktivitásazonosító.")
        state["feedback"][activity_id] = validate_feedback(item.get("value"))
    if "feedbackMap" in patch:
        if not isinstance(patch["feedbackMap"], dict) or len(patch["feedbackMap"]) > 5000:
            raise ValueError("Érvénytelen RPE-előzmény.")
        for activity_id, value in patch["feedbackMap"].items():
            clean_id = _text(activity_id, 120)
            if clean_id:
                state["feedback"][clean_id] = validate_feedback(value)
    if "plan" in patch:
        item = patch["plan"]
        plan_id = _text(item.get("id") if isinstance(item, dict) else "", 80)
        validated = validate_plan(item, plan_id or None)
        state["plans"] = [plan for plan in state["plans"] if plan.get("id") != validated["id"]]
        state["plans"].append(validated)
        state["plans"].sort(key=lambda plan: (plan["date"], plan["id"]))
    if "plans" in patch:
        if not isinstance(patch["plans"], list) or len(patch["plans"]) > 366:
            raise ValueError("Érvénytelen heti terv.")
        replace_dates = patch.get("replacePlanDates", [])
        if not isinstance(replace_dates, list) or len(replace_dates) > 366:
            raise ValueError("Érvénytelen lecserélendő tervdátum.")
        clean_replace_dates = set()
        for value in replace_dates:
            clean_date = _text(value, 10)
            date.fromisoformat(clean_date)
            clean_replace_dates.add(clean_date)
        existing = {plan.get("id"): plan for plan in state["plans"] if plan.get("date") not in clean_replace_dates}
        for item in patch["plans"]:
            validated = validate_plan(item)
            existing[validated["id"]] = validated
        state["plans"] = sorted(existing.values(), key=lambda plan: (plan["date"], plan["id"]))
    if "deletePlan" in patch:
        plan_id = _text(patch["deletePlan"], 80)
        if not plan_id:
            raise ValueError("Hiányzó tervazonosító.")
        state["plans"] = [plan for plan in state["plans"] if plan.get("id") != plan_id]
    if user_id:
        save_user_json(user_id, STATE_KEY, state)
    else:
        save_json(STATE_KEY, state)
    return state
