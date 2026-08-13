"""Read-only Garmin Connect synchronization with resilient local caching."""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from garminconnect import Garmin


class GarminSyncError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _first_number(payload: Any, *keys: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = _number(payload.get(key))
        if value is not None:
            return value
    return None


def _sleep_score(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    direct = _first_number(payload, "sleepScoresOverall", "overallScore", "sleepScore")
    if direct is not None:
        return direct
    scores = payload.get("sleepScores")
    if isinstance(scores, dict):
        overall = scores.get("overall")
        return _first_number(overall, "value", "score") if isinstance(overall, dict) else _number(overall)
    return None


@dataclass
class GarminSync:
    cache_dir: Path | str | None = None
    ttl_hours: float | None = None

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir or os.getenv("CACHE_DIR", "data"))
        self.ttl_hours = float(self.ttl_hours or os.getenv("CACHE_TTL_HOURS", "12"))
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.token_dir = self.cache_dir / ".garmin_tokens"
        self.token_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.client: Garmin | None = None

    @property
    def cache_file(self) -> Path:
        return self.cache_dir / "garmin_cache.json"

    def authenticate(self) -> Garmin:
        email, password = os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")
        if not email or not password:
            raise GarminSyncError("Hiányzik a GARMIN_EMAIL vagy GARMIN_PASSWORD. Használd a demo módot, vagy állítsd be mindkettőt.")
        try:
            client = Garmin(email, password)
            client.login(str(self.token_dir))
        except Exception as exc:
            message = str(exc).lower()
            if "429" in message or "rate" in message:
                reason = "Garmin rate limit. Várj, majd próbáld újra; az utolsó cache használható."
            elif "mfa" in message or "challenge" in message:
                reason = "Garmin MFA szükséges. Az első belépést interaktív környezetben végezd el."
            else:
                reason = "Garmin hitelesítési hiba. Ellenőrizd a környezeti változókat és a cache-elt tokent."
            raise GarminSyncError(reason) from exc
        self.client = client
        return client

    def load_cache(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8")) if self.cache_file.exists() else None
        except (OSError, json.JSONDecodeError):
            return None

    def cache_age_hours(self) -> float:
        payload = self.load_cache()
        if not payload or not payload.get("synced_at"):
            return float("inf")
        try:
            stamp = datetime.fromisoformat(payload["synced_at"])
            return max(0.0, (datetime.now().astimezone() - stamp).total_seconds() / 3600)
        except (TypeError, ValueError):
            return float("inf")

    def cache_is_fresh(self) -> bool:
        return self.cache_age_hours() <= float(self.ttl_hours or 12)

    def save_cache(self, payload: dict[str, Any]) -> None:
        temporary = self.cache_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.cache_file)

    @staticmethod
    def _safe_call(call: Callable[[], Any], default: Any, errors: list[str], label: str) -> Any:
        try:
            result = call()
            return default if result is None else result
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}")
            return default

    def sync(self, days: int = 90) -> dict[str, Any]:
        if not 30 <= days <= 180:
            raise ValueError("days must be between 30 and 180")
        client = self.client or self.authenticate()
        end, start = date.today(), date.today() - timedelta(days=days - 1)
        errors: list[str] = []
        activities = self._safe_call(lambda: client.get_activities_by_date(start.isoformat(), end.isoformat(), sortorder="asc"), [], errors, "activities")
        wellness: list[dict[str, Any]] = []
        for offset in range(days):
            day, iso = start + timedelta(days=offset), (start + timedelta(days=offset)).isoformat()
            hrv = self._safe_call(lambda d=iso: client.get_hrv_data(d), {}, errors, f"hrv:{iso}")
            sleep = self._safe_call(lambda d=iso: client.get_sleep_data(d), {}, errors, f"sleep:{iso}")
            heart = self._safe_call(lambda d=iso: client.get_heart_rates(d), {}, errors, f"heart:{iso}")
            hrv_summary = hrv.get("hrvSummary", hrv) if isinstance(hrv, dict) else {}
            sleep_daily = sleep.get("dailySleepDTO", sleep) if isinstance(sleep, dict) else {}
            sleep_seconds = _first_number(sleep_daily, "sleepTimeSeconds", "sleepTime")
            wellness.append({
                "date": iso,
                "hrv": _first_number(hrv_summary, "lastNightAvg", "weeklyAvg", "lastNight5MinHigh"),
                "sleep_score": _sleep_score(sleep_daily) or _sleep_score(sleep),
                "sleep_hours": sleep_seconds / 3600 if sleep_seconds else None,
                "resting_hr": _first_number(heart, "restingHeartRate", "restingHeartRateValue"),
            })
        if not activities and all(not any(v for k, v in day.items() if k != "date") for day in wellness):
            cached = self.load_cache()
            if cached:
                cached["fallback_reason"] = "A szinkron nem adott használható adatot; az utolsó érvényes cache látható."
                return cached
            raise GarminSyncError("A Garmin nem adott használható adatot, és nincs korábbi cache.")
        payload = {"synced_at": datetime.now().astimezone().isoformat(), "days": days, "activities": activities, "wellness": wellness, "partial_errors": errors[:20]}
        self.save_cache(payload)
        return payload


def demo_data(days: int = 90, seed: int = 23) -> dict[str, Any]:
    """Deterministic 90+ day hybrid dataset with recovery and mountain scenarios."""
    days = max(90, days)
    rng = random.Random(seed)
    end, start = date.today(), date.today() - timedelta(days=days - 1)
    wellness, activities, checkins, feedback = [], [], {}, {}
    kinds = ["running", "strength_training", "functional_strength_training", "hiking"]
    for i in range(days):
        day = start + timedelta(days=i)
        deload = 0.72 if 42 <= i < 49 else 1.0
        fatigue = 8 if days - 8 <= i < days - 4 else 0
        illness = i == days - 3
        wellness.append({"date": day.isoformat(), "hrv": round(58 + rng.gauss(0, 3.5) - fatigue, 1), "sleep_score": round(max(45, min(96, 82 + rng.gauss(0, 6) - fatigue)), 0), "sleep_hours": round(max(5, min(9, 7.6 + rng.gauss(0, .55) - fatigue / 10)), 1), "resting_hr": round(51 + rng.gauss(0, 1.5) + fatigue / 2, 0)})
        if i % 2 == 0 or i % 7 == 5:
            kind = kinds[(i // 2) % len(kinds)]
            duration_min = int(rng.randint(35, 95) * deload)
            if kind == "hiking" and i % 14 == 12:
                duration_min = 180
            activity_id = str(10000 + i)
            activities.append({"activityId": activity_id, "activityName": kind.replace("_", " ").title(), "startTimeLocal": f"{day.isoformat()} 07:00:00", "activityType": {"typeKey": kind}, "duration": duration_min * 60, "calories": round(duration_min * rng.uniform(6.5, 10)), "averageHR": rng.randint(118, 148), "maxHR": rng.randint(155, 185), "distance": rng.randint(5000, 18000) if kind in {"running", "hiking"} else 0, "elevationGain": rng.randint(100, 1100) if kind == "hiking" else rng.randint(0, 180), "elevationLoss": rng.randint(100, 1000) if kind == "hiking" else rng.randint(0, 150)})
            feedback[activity_id] = {"rpe": 7 if i % 6 == 0 else 5, "feeling": "planned", "focus": "lower body" if kind != "running" else "cardio", "pack_kg": 10 if kind == "hiking" else None}
        if i % 4 == 0 or illness:
            checkins[day.isoformat()] = {"soreness": 4 if i == days - 5 else 2, "stress": 3, "motivation": 4, "fatigue": 4 if fatigue else 2, "pain": "mild" if i == days - 5 else "none", "illness": illness, "note": "Deterministic demo check-in"}
    return {"synced_at": datetime.now().astimezone().isoformat(), "days": days, "activities": activities, "wellness": wellness, "demo_checkins": checkins, "demo_feedback": feedback, "demo": True}
