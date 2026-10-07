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

from garmin_profile import fetch_profile_metrics, strength_set_candidates, summarize_exercise_sets


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
    email: str | None = None
    password: str | None = None
    tokenstore: str | None = None

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
        email, password = self.email or os.getenv("GARMIN_EMAIL"), self.password or os.getenv("GARMIN_PASSWORD")
        tokenstore = self.tokenstore or os.getenv("GARMINTOKENS")
        if not tokenstore and (not email or not password):
            raise GarminSyncError("Nincs érvényes Garmin-munkamenet. Csatlakoztasd újra a fiókot a Beállításokban.")
        try:
            client = Garmin(email, password)
            # Serialized session tokens (cloud sync) take precedence over the on-disk token store.
            client.login(tokenstore or str(self.token_dir))
        except Exception as exc:
            message = str(exc).lower()
            if "429" in message or "rate limit" in message or "ratelimit" in message or "too many requests" in message:
                reason = "Garmin rate limit. Várj, majd próbáld újra; az utolsó cache használható."
            elif any(marker in message for marker in ("timeout", "timed out", "connection reset", "connection aborted",
                                                      "connection error", "remote end closed", "502", "503", "504")):
                reason = "A Garmin átmenetileg nem elérhető. Az eddigi szinkronizálási előrehaladás megmarad."
            elif "mfa" in message or "challenge" in message:
                reason = "Garmin MFA szükséges. Csatlakoztasd újra a fiókot a Beállításokban."
            else:
                reason = "Garmin hitelesítési hiba. Csatlakoztasd újra a fiókot a Beállításokban."
            raise GarminSyncError(reason) from exc
        self.client = client
        return client

    def export_tokens(self) -> str | None:
        """Serialized session tokens of the authenticated client, for encrypted reuse."""
        try:
            return self.client.client.dumps() if self.client else None
        except Exception:
            return None

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

    def _all_activities(self, client: Garmin, errors: list[str], page_size: int = 100) -> list[dict[str, Any]]:
        """Read every activity through Garmin's paginated read-only endpoint."""
        activities: list[dict[str, Any]] = []
        offset = 0
        for _ in range(10000):
            page = self._safe_call(lambda start=offset: client.get_activities(start, page_size), [], errors, f"activities-page:{offset}")
            if not isinstance(page, list) or not page:
                break
            activities.extend(item for item in page if isinstance(item, dict))
            offset += len(page)
            if len(page) < page_size:
                break
        return activities

    @staticmethod
    def _merge_records(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        merged = {str(item.get(key)): item for item in existing if item.get(key) is not None}
        for item in incoming:
            if item.get(key) is None:
                continue
            record_key = str(item[key])
            previous = merged.get(record_key, {})
            merged[record_key] = {**previous, **{field: value for field, value in item.items() if value is not None}}
        return list(merged.values())

    def sync(self, days: int | None = 90) -> dict[str, Any]:
        if days is not None and days < 30:
            raise ValueError("days must be at least 30, or None for full history")
        client = self.client or self.authenticate()
        end = date.today()
        start = end - timedelta(days=(days or 30) - 1)
        errors: list[str] = []
        cached = self.load_cache() or {}
        if days is None:
            fetched_activities = self._all_activities(client, errors)
        else:
            fetched_activities = self._safe_call(lambda: client.get_activities_by_date(start.isoformat(), end.isoformat(), sortorder="asc"), [], errors, "activities")
        activities = self._merge_records(cached.get("activities", []), fetched_activities, "activityId")
        if days is None and activities:
            parsed_dates = []
            for item in activities:
                raw_date = item.get("startTimeLocal") or item.get("startTimeGMT")
                try:
                    parsed_dates.append(datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).date())
                except (TypeError, ValueError):
                    continue
            if parsed_dates:
                start = min(parsed_dates)
        cardio_terms = {"run", "running", "trail", "walk", "walking", "hike", "hiking", "trek", "cycling", "bike", "swim", "rowing", "elliptical", "cardio"}
        for activity in activities:
            if not isinstance(activity, dict):
                continue
            raw_type = activity.get("activityType", {})
            kind = str(raw_type.get("typeKey", "") if isinstance(raw_type, dict) else raw_type).lower()
            activity_id = activity.get("activityId")
            if activity_id and any(term in kind for term in cardio_terms) and activity.get("hr_zone_minutes") is None:
                activity["hr_zone_minutes"] = self._safe_call(
                    lambda value=str(activity_id): client.get_activity_hr_in_timezones(value),
                    {}, errors, f"hr-zones:{activity_id}",
                )
        strength_ids = set(strength_set_candidates(activities))
        for activity in activities:
            if str(activity.get("activityId")) in strength_ids:
                activity["exercise_sets"] = summarize_exercise_sets(self._safe_call(
                    lambda value=str(activity["activityId"]): client.get_activity_exercise_sets(value), {}, errors, f"exercise-sets:{activity['activityId']}",
                ))
        profile = fetch_profile_metrics(client, self._safe_call, errors)
        cached_wellness = {str(item.get("date")): item for item in cached.get("wellness", []) if item.get("date")}
        wellness: list[dict[str, Any]] = list(cached_wellness.values())
        total_days = (end - start).days + 1
        for offset in range(total_days):
            day, iso = start + timedelta(days=offset), (start + timedelta(days=offset)).isoformat()
            if iso in cached_wellness:
                continue
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
                "spo2": _first_number(sleep_daily, "averageSpO2Value", "averageSpo2", "avgSpO2"),
            })
            if days is None and len(wellness) % 30 == 0:
                self.save_cache({"synced_at": datetime.now().astimezone().isoformat(), "days": "all", "activities": activities, "wellness": sorted(wellness, key=lambda item: item["date"]), "partial_errors": errors[:20], "backfill_in_progress": True})
        if not activities and all(not any(v for k, v in day.items() if k != "date") for day in wellness):
            cached = self.load_cache()
            if cached:
                cached["fallback_reason"] = "A szinkron nem adott használható adatot; az utolsó érvényes cache látható."
                return cached
            raise GarminSyncError("A Garmin nem adott használható adatot, és nincs korábbi cache.")
        payload = {"synced_at": datetime.now().astimezone().isoformat(), "days": "all" if days is None else days, "activities": activities, "wellness": sorted(wellness, key=lambda item: item["date"]), "profile": profile, "partial_errors": errors[:20], "backfill_in_progress": False}
        self.save_cache(payload)
        return payload


def _demo_sets(index: int, kind: str) -> list[dict[str, Any]] | None:
    if "strength" not in kind:
        return None
    progress = index / 30
    return [
        {"category": "SQUAT", "exercise": "BARBELL_BACK_SQUAT", "reps": 5, "weight_kg": round(95 + progress * 2.5, 1)},
        {"category": "BENCH_PRESS", "exercise": "BARBELL_BENCH_PRESS", "reps": 5, "weight_kg": round(72.5 + progress * 1.5, 1)},
        {"category": "DEADLIFT", "exercise": "BARBELL_DEADLIFT", "reps": 3, "weight_kg": round(125 + progress * 3, 1)},
    ]


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
        wellness.append({"date": day.isoformat(), "hrv": round(58 + rng.gauss(0, 3.5) - fatigue, 1), "sleep_score": round(max(45, min(96, 82 + rng.gauss(0, 6) - fatigue)), 0), "sleep_hours": round(max(5, min(9, 7.6 + rng.gauss(0, .55) - fatigue / 10)), 1), "resting_hr": round(51 + rng.gauss(0, 1.5) + fatigue / 2, 0), "spo2": round(96 + rng.gauss(0, .7), 1)})
        if i % 2 == 0 or i % 7 == 5:
            kind = kinds[(i // 2) % len(kinds)]
            duration_min = int(rng.randint(35, 95) * deload)
            if kind == "hiking" and i % 14 == 12:
                duration_min = 180
            activity_id = str(10000 + i)
            zone_weights = [0.12, 0.58, 0.20, 0.08, 0.02] if kind in {"running", "hiking"} else [0.18, 0.30, 0.28, 0.18, 0.06]
            zone_payload = [{"zoneNumber": zone, "secsInZone": round(duration_min * 60 * weight)} for zone, weight in enumerate(zone_weights, 1)] if kind in {"running", "hiking"} else None
            activities.append({"activityId": activity_id, "activityName": kind.replace("_", " ").title(), "startTimeLocal": f"{day.isoformat()} 07:00:00", "activityType": {"typeKey": kind}, "duration": duration_min * 60, "calories": round(duration_min * rng.uniform(6.5, 10)), "averageHR": rng.randint(118, 148), "maxHR": rng.randint(155, 185), "distance": rng.randint(5000, 18000) if kind in {"running", "hiking"} else 0, "elevationGain": rng.randint(100, 1100) if kind == "hiking" else rng.randint(0, 180), "elevationLoss": rng.randint(100, 1000) if kind == "hiking" else rng.randint(0, 150), "hr_zone_minutes": zone_payload, "exercise_sets": _demo_sets(i, kind)})
            feedback[activity_id] = {"rpe": 7 if i % 6 == 0 else 5, "feeling": "planned", "focus": "lower body" if kind != "running" else "cardio", "pack_kg": 10 if kind == "hiking" else None}
        if i % 4 == 0 or illness:
            checkins[day.isoformat()] = {"soreness": 4 if i == days - 5 else 2, "stress": 3, "motivation": 4, "fatigue": 4 if fatigue else 2, "pain": "mild" if i == days - 5 else "none", "illness": illness, "note": "Deterministic demo check-in"}
    return {"synced_at": datetime.now().astimezone().isoformat(), "days": days, "activities": activities, "wellness": wellness, "profile": demo_profile(end), "demo_checkins": checkins, "demo_feedback": feedback, "demo": True}


def demo_profile(today: date | None = None) -> dict[str, Any]:
    """Deterministic athlete profile matching the demo activities (35-year-old hybrid athlete)."""
    today = today or date.today()
    months = [today - timedelta(days=30 * index) for index in range(11, -1, -1)]
    weeks = [today - timedelta(days=today.weekday() + 7 * index) for index in range(11, -1, -1)]
    return {
        "version": 1, "fetched_at": datetime.now().astimezone().isoformat(), "demo": True,
        "sex": "male", "birth_date": date(today.year - 35, 3, 14).isoformat(), "height_cm": 180.0, "weight_kg": 78.4,
        "vo2max_running": 51.0, "vo2max_cycling": None,
        "vo2max_history": [{"date": day.isoformat(), "running": round(47.5 + index * 0.32, 1)} for index, day in enumerate(months)],
        "fitness_age": 29.0, "chronological_age": 35.0, "achievable_fitness_age": 27.0,
        "body_history": [{"date": day.isoformat(), "weight_kg": round(80.6 - index * 0.2, 1), "bmi": round((80.6 - index * 0.2) / 3.24, 1), "body_fat_pct": round(18.4 - index * 0.15, 1), "muscle_mass_kg": None} for index, day in enumerate(months)],
        "body_weight_kg": 78.4, "bmi": 24.2, "body_fat_pct": 16.7,
        "intensity_weeks": [{"week_start": day.isoformat(), "moderate": 150 + (index % 3) * 20, "vigorous": 45 + (index % 4) * 10, "equivalent": 150 + (index % 3) * 20 + 2 * (45 + (index % 4) * 10), "goal": 150} for index, day in enumerate(weeks)],
        "daily_steps": [{"date": (today - timedelta(days=index)).isoformat(), "steps": 8200 + (index * 937) % 5200, "goal": 10000} for index in range(27, -1, -1)],
        "personal_records": [{"type_id": 3, "activity_type": "running", "label": "5 km", "value": 1335.0, "date": (today - timedelta(days=40)).isoformat(), "activity_id": None},
                             {"type_id": 4, "activity_type": "running", "label": "10 km", "value": 2856.0, "date": (today - timedelta(days=75)).isoformat(), "activity_id": None}],
        "race_predictions": {"5k": 1310.0, "10k": 2790.0, "half_marathon": 6240.0, "marathon": 13380.0},
        "endurance_score": 6420.0, "endurance_classification": 4,
        "sources": {name: "ok" for name in ("user_profile", "max_metrics", "fitness_age", "body_composition", "intensity_minutes", "daily_steps", "personal_records", "race_predictions", "endurance_score")},
    }
