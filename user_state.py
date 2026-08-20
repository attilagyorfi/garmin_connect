"""Validation and persistence for the single-user desktop application state."""
from __future__ import annotations

from datetime import date
from typing import Any

from cloud_cache import load_json, save_json


STATE_KEY = "user_state_v1"
ACCENTS = {"teal", "blue", "violet", "orange", "rose"}
EXPERIENCE = {"kezdő", "középhaladó", "haladó"}
GOALS = {"Hibrid teljesítmény", "Futóteljesítmény", "Erőfejlesztés", "Hegyi állóképesség", "Általános egészség"}
PREFERENCES = {"kiegyensúlyozott", "teljesítmény", "regeneráció"}
DAYS = {"H", "K", "Sze", "Cs", "P", "Szo", "V"}


def empty_state() -> dict[str, Any]:
    return {"version": 1, "profile": None, "accent": "teal", "checkins": {}, "feedback": {}}


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


def load_state() -> dict[str, Any]:
    stored = load_json(STATE_KEY) or {}
    return {**empty_state(), **stored, "checkins": stored.get("checkins") or {}, "feedback": stored.get("feedback") or {}}


def apply_patch(patch: Any) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("Érvénytelen módosítás.")
    state = load_state()
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
    save_json(STATE_KEY, state)
    return state
