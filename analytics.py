"""Pure analysis functions for training load, readiness, and modality."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


CARDIO_TERMS = {
    "run", "running", "trail", "walk", "walking", "hike", "hiking", "trek",
    "cycling", "bike", "swim", "rowing", "elliptical", "cardio",
}
STRENGTH_TERMS = {
    "strength", "functional", "crossfit", "hiit", "weight", "gym", "calisthenics",
}


def activity_type(activity: dict[str, Any]) -> str:
    raw = activity.get("activityType", {})
    if isinstance(raw, dict):
        raw = raw.get("typeKey") or raw.get("typeId") or ""
    return str(raw or activity.get("activityName", "unknown")).lower()


def modality(kind: str) -> str:
    normalized = kind.lower().replace("_", " ")
    if any(term in normalized for term in STRENGTH_TERMS):
        return "Strength / Functional"
    if any(term in normalized for term in CARDIO_TERMS):
        return "Cardio"
    return "Other"


def build_daily_frames(payload: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    wellness = pd.DataFrame(payload.get("wellness", []))
    if wellness.empty:
        wellness = pd.DataFrame(columns=["date", "hrv", "sleep_score", "resting_hr"])
    wellness["date"] = pd.to_datetime(wellness["date"], errors="coerce").dt.normalize()
    wellness = wellness.dropna(subset=["date"]).set_index("date").sort_index()
    for col in ["hrv", "sleep_score", "resting_hr"]:
        wellness[col] = pd.to_numeric(wellness.get(col), errors="coerce")

    rows = []
    for item in payload.get("activities", []):
        started = item.get("startTimeLocal") or item.get("startTimeGMT")
        parsed = pd.to_datetime(started, errors="coerce")
        if pd.isna(parsed):
            continue
        calories = pd.to_numeric(item.get("calories"), errors="coerce")
        duration_seconds = pd.to_numeric(item.get("duration"), errors="coerce")
        duration_min = float(duration_seconds / 60) if pd.notna(duration_seconds) else 0.0
        # Calories are a transparent stress proxy; duration is a fallback only.
        stress = float(calories) if pd.notna(calories) and calories > 0 else float(duration_min * 8)
        kind = activity_type(item)
        rows.append(
            {
                "date": parsed.normalize(),
                "name": item.get("activityName", kind.replace("_", " ").title()),
                "type": kind,
                "modality": modality(kind),
                "duration_min": duration_min,
                "calories": calories if pd.notna(calories) else np.nan,
                "stress": stress,
            }
        )
    activities = pd.DataFrame(rows)

    if wellness.empty and activities.empty:
        return wellness, activities
    starts = [frame.index.min() if frame is wellness else frame["date"].min()
              for frame in (wellness, activities) if not frame.empty]
    ends = [frame.index.max() if frame is wellness else frame["date"].max()
            for frame in (wellness, activities) if not frame.empty]
    index = pd.date_range(min(starts), max(ends), freq="D")
    wellness = wellness.reindex(index)
    daily_stress = activities.groupby("date")["stress"].sum() if not activities.empty else pd.Series(dtype=float)
    wellness["stress"] = daily_stress.reindex(index, fill_value=0.0)
    wellness["atl"] = wellness["stress"].ewm(span=7, adjust=False).mean()
    wellness["ctl"] = wellness["stress"].ewm(span=42, adjust=False).mean()
    wellness["tsb"] = wellness["ctl"] - wellness["atl"]
    return wellness, activities


def readiness(frame: pd.DataFrame) -> tuple[float | None, dict[str, float], str]:
    if frame.empty:
        return None, {}, "No wellness data"
    latest = frame.iloc[-1]
    history = frame.iloc[:-1].tail(28)
    components: dict[str, float] = {}
    if pd.notna(latest.get("hrv")):
        baseline = history["hrv"].median()
        if pd.notna(baseline) and baseline > 0:
            components["HRV"] = float(np.clip(70 + 100 * (latest["hrv"] / baseline - 1), 0, 100))
    if pd.notna(latest.get("sleep_score")):
        components["Sleep"] = float(np.clip(latest["sleep_score"], 0, 100))
    if pd.notna(latest.get("resting_hr")):
        baseline = history["resting_hr"].median()
        if pd.notna(baseline) and baseline > 0:
            components["RHR"] = float(np.clip(75 - 5 * (latest["resting_hr"] - baseline), 0, 100))
    if not components:
        return None, {}, "Insufficient wellness data"
    weights = {"HRV": 0.4, "Sleep": 0.4, "RHR": 0.2}
    total_weight = sum(weights[key] for key in components)
    score = sum(components[key] * weights[key] for key in components) / total_weight
    recommendation = "High Intensity" if score >= 80 else "Zone 2 Base" if score >= 60 else "Active Recovery"
    return round(score, 0), components, recommendation


def tsb_zone(value: float) -> tuple[str, str]:
    if value > 5:
        return "Fresh", "#54D6A0"
    if value >= -20:
        return "Optimal Training", "#F5C451"
    return "Overreaching", "#FF6B6B"


def coach_insight(frame: pd.DataFrame, score: float | None, recommendation: str) -> str:
    if frame.empty:
        return "Sync Garmin data to generate a recommendation."
    latest = frame.iloc[-1]
    tsb = float(latest["tsb"])
    hrv = latest.get("hrv")
    baseline = frame.iloc[:-1].tail(28)["hrv"].median()
    hrv_low = pd.notna(hrv) and pd.notna(baseline) and hrv < baseline * 0.92
    if tsb < -20 and hrv_low:
        return "Fatigue and suppressed HRV agree: take a full rest day or keep movement genuinely easy."
    if tsb < -20:
        return "Load is in the overreaching zone. Avoid adding intensity; choose recovery or easy aerobic work."
    if hrv_low:
        return "HRV is materially below baseline. Keep today's session low intensity even if training load looks acceptable."
    if tsb > 5 and (score or 0) >= 75:
        return "You are fresh and physiologically ready. This is a strong day for quality intervals or heavy strength work."
    return f"Load and recovery are compatible with {recommendation.lower()}. Reassess tomorrow after sleep and HRV update."
