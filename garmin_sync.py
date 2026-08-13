"""Read-only Garmin Connect synchronization with a local JSON cache."""

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
    """Raised when authentication or synchronization cannot complete."""


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
    """Handle both legacy and current nested Garmin sleep-score shapes."""
    if not isinstance(payload, dict):
        return None
    direct = _first_number(payload, "sleepScoresOverall", "overallScore", "sleepScore")
    if direct is not None:
        return direct
    scores = payload.get("sleepScores")
    if isinstance(scores, dict):
        overall = scores.get("overall")
        if isinstance(overall, dict):
            return _first_number(overall, "value", "score")
        return _number(overall)
    return None


@dataclass
class GarminSync:
    cache_dir: Path = Path(os.getenv("CACHE_DIR", "data"))

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.token_dir = self.cache_dir / ".garmin_tokens"
        self.token_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.client: Garmin | None = None

    @property
    def cache_file(self) -> Path:
        return self.cache_dir / "garmin_cache.json"

    def authenticate(self) -> Garmin:
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not email or not password:
            raise GarminSyncError("GARMIN_EMAIL and GARMIN_PASSWORD must be configured.")
        try:
            client = Garmin(email, password)
            client.login(str(self.token_dir))
        except Exception as exc:
            raise GarminSyncError(
                "Garmin login failed. Check credentials, MFA requirements, or cached tokens."
            ) from exc
        self.client = client
        return client

    def load_cache(self) -> dict[str, Any] | None:
        if not self.cache_file.exists():
            return None
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save_cache(self, payload: dict[str, Any]) -> None:
        temporary = self.cache_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.cache_file)

    def _safe_call(self, call: Callable[[], Any], default: Any) -> Any:
        try:
            result = call()
            return default if result is None else result
        except Exception:
            return default

    def sync(self, days: int = 60) -> dict[str, Any]:
        if days not in (30, 60):
            raise ValueError("days must be 30 or 60")
        client = self.client or self.authenticate()
        end = date.today()
        start = end - timedelta(days=days - 1)

        activities = self._safe_call(
            lambda: client.get_activities_by_date(start.isoformat(), end.isoformat()), []
        )
        wellness: list[dict[str, Any]] = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            iso = day.isoformat()
            hrv = self._safe_call(lambda d=iso: client.get_hrv_data(d), {})
            sleep = self._safe_call(lambda d=iso: client.get_sleep_data(d), {})
            heart = self._safe_call(lambda d=iso: client.get_heart_rates(d), {})

            hrv_summary = hrv.get("hrvSummary", hrv) if isinstance(hrv, dict) else {}
            sleep_daily = sleep.get("dailySleepDTO", sleep) if isinstance(sleep, dict) else {}
            wellness.append(
                {
                    "date": iso,
                    "hrv": _first_number(
                        hrv_summary,
                        "lastNightAvg",
                        "weeklyAvg",
                        "lastNight5MinHigh",
                    ),
                    "sleep_score": _sleep_score(sleep_daily) or _sleep_score(sleep),
                    "resting_hr": _first_number(
                        heart, "restingHeartRate", "restingHeartRateValue"
                    ),
                }
            )

        payload = {
            "synced_at": datetime.now().astimezone().isoformat(),
            "days": days,
            "activities": activities,
            "wellness": wellness,
        }
        self.save_cache(payload)
        return payload


def demo_data(days: int = 60, seed: int = 23) -> dict[str, Any]:
    """Deterministic realistic data for first-run UI evaluation."""
    rng = random.Random(seed)
    end = date.today()
    start = end - timedelta(days=days - 1)
    wellness: list[dict[str, Any]] = []
    activities: list[dict[str, Any]] = []
    types = ["running", "strength_training", "functional_strength_training", "hiking"]
    for i in range(days):
        day = start + timedelta(days=i)
        fatigue = 6 if i > days - 9 else 0
        wellness.append(
            {
                "date": day.isoformat(),
                "hrv": round(56 + rng.gauss(0, 4) - fatigue, 1),
                "sleep_score": round(max(45, min(96, 81 + rng.gauss(0, 7) - fatigue)), 0),
                "resting_hr": round(52 + rng.gauss(0, 2) + fatigue / 2, 0),
            }
        )
        if i % 2 == 0 or rng.random() > 0.72:
            kind = types[(i // 2) % len(types)]
            duration = rng.randint(35, 105) * 60
            activities.append(
                {
                    "activityId": i + 1,
                    "activityName": kind.replace("_", " ").title(),
                    "startTimeLocal": f"{day.isoformat()} 07:00:00",
                    "activityType": {"typeKey": kind},
                    "duration": duration,
                    "calories": round(duration / 60 * rng.uniform(6.5, 11.5)),
                }
            )
    return {
        "synced_at": datetime.now().astimezone().isoformat(),
        "days": days,
        "activities": activities,
        "wellness": wellness,
        "demo": True,
    }
