"""Deterministic, explainable hybrid-training analytics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


CARDIO_TERMS = {"run", "running", "trail", "walk", "hike", "hiking", "trek", "cycling", "bike", "swim", "row", "elliptical", "cardio"}
STRENGTH_TERMS = {"strength", "functional", "crossfit", "hiit", "weight", "gym", "calisthenics"}
TREK_TERMS = {"hike", "hiking", "trek", "mountain", "trail"}


def number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
        return result if np.isfinite(result) else default
    except (TypeError, ValueError):
        return default


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


def robust_z_score(value: float, samples: pd.Series) -> float | None:
    clean = pd.to_numeric(samples, errors="coerce").dropna()
    if clean.empty:
        return None
    median = float(clean.median())
    mad = float((clean - median).abs().median())
    if mad == 0:
        return 0.0 if value == median else float(np.sign(value - median) * 3.5)
    return float(0.6745 * (value - median) / mad)


def personal_baseline(series: pd.Series, window: int = 28) -> dict[str, Any]:
    if not 21 <= window <= 60:
        raise ValueError("baseline window must be between 21 and 60 days")
    clean = pd.to_numeric(series.tail(window), errors="coerce").dropna()
    result: dict[str, Any] = {"valid_days": int(clean.size), "stable": clean.size >= 14}
    if clean.empty:
        return {**result, "median": None, "iqr": None, "mad": None, "trend": None}
    x = np.arange(clean.size, dtype=float)
    trend = float(np.polyfit(x, clean.to_numpy(), 1)[0]) if clean.size >= 2 else 0.0
    return {
        **result,
        "median": float(clean.median()),
        "iqr": float(clean.quantile(0.75) - clean.quantile(0.25)),
        "mad": float((clean - clean.median()).abs().median()),
        "trend": trend,
    }


def cardio_load(activity: dict[str, Any]) -> tuple[float, str, str]:
    duration = max(0.0, number(activity.get("duration_min"), 0.0) or 0.0)
    zones = activity.get("hr_zone_minutes")
    if isinstance(zones, (list, tuple)) and any(number(v, 0) for v in zones):
        values = [(number(v, 0) or 0.0) for v in zones[:5]]
        return float(sum((i + 1) * value for i, value in enumerate(values))), "hr_zones_edwards", "high"
    avg_hr, max_hr = number(activity.get("avg_hr")), number(activity.get("max_hr"))
    if avg_hr and max_hr and max_hr > 0:
        return duration * float(np.clip(avg_hr / max_hr, 0.45, 1.0)) * 10, "heart_rate_duration", "medium"
    intensity = number(activity.get("intensity_factor"))
    if intensity:
        return duration * float(np.clip(intensity, 0.3, 1.5)) * 8, "duration_intensity", "medium"
    calories = number(activity.get("calories"))
    if calories and calories > 0:
        return calories, "calorie_proxy", "low"
    return duration * 5, "duration_proxy", "low"


def extract_hr_zone_minutes(payload: Any) -> list[float]:
    """Normalize Garmin HR-zone payload variants to five minute values.

    Garmin's unofficial response shape has changed over time. Known variants
    include a list of zone dictionaries, a nested ``zones`` list and mappings
    such as ``zone1``. Unknown or malformed values safely become zero.
    """
    zones = [0.0] * 5
    candidate = payload
    if isinstance(candidate, dict):
        for key in ("hrTimeInZones", "heartRateZones", "zones", "zoneData"):
            if isinstance(candidate.get(key), (list, dict)):
                candidate = candidate[key]
                break
    if isinstance(candidate, dict):
        for key, raw in candidate.items():
            digits = "".join(character for character in str(key) if character.isdigit())
            if not digits:
                continue
            zone_number = int(digits)
            if not 1 <= zone_number <= 5:
                continue
            if isinstance(raw, dict):
                seconds = number(raw.get("secsInZone") or raw.get("seconds") or raw.get("duration"))
                minutes = number(raw.get("minutes"))
            else:
                seconds, minutes = number(raw), None
            zones[zone_number - 1] = max(0.0, minutes if minutes is not None else (seconds or 0.0) / 60)
        return zones
    if not isinstance(candidate, list):
        return zones
    for position, item in enumerate(candidate[:5], start=1):
        if isinstance(item, dict):
            zone_number = int(number(item.get("zoneNumber") or item.get("zone") or item.get("zoneIndex"), position) or position)
            seconds = number(item.get("secsInZone") or item.get("seconds") or item.get("duration") or item.get("value"))
            minutes = number(item.get("minutes"))
        else:
            zone_number, seconds, minutes = position, number(item), None
        if 1 <= zone_number <= 5:
            zones[zone_number - 1] = max(0.0, minutes if minutes is not None else (seconds or 0.0) / 60)
    return zones


def strength_load(activity: dict[str, Any], feedback: dict[str, Any] | None = None) -> tuple[float, str, str]:
    duration = max(0.0, number(activity.get("duration_min"), 0.0) or 0.0)
    feedback = feedback or {}
    rpe = number(feedback.get("rpe") or activity.get("rpe"))
    if rpe:
        return duration * float(np.clip(rpe, 1, 10)), "session_rpe", "high"
    volume = number(feedback.get("volume_kg") or activity.get("volume_kg"))
    if volume and volume > 0:
        return duration * 4 + np.sqrt(volume) * 10, "volume_duration", "medium"
    calories = number(activity.get("calories"))
    if calories and calories > 0:
        return calories * 0.8, "calorie_proxy", "low"
    return duration * 6, "duration_proxy", "low"


def musculoskeletal_load(activity: dict[str, Any], feedback: dict[str, Any] | None = None) -> float:
    duration = max(0.0, number(activity.get("duration_min"), 0.0) or 0.0)
    distance_km = max(0.0, number(activity.get("distance_km"), 0.0) or 0.0)
    ascent = max(0.0, number(activity.get("ascent_m"), 0.0) or 0.0)
    descent = max(0.0, number(activity.get("descent_m"), 0.0) or 0.0)
    pack = max(0.0, number((feedback or {}).get("pack_kg"), 0.0) or 0.0)
    kind = activity.get("type", "")
    load = distance_km * 8 + ascent / 20 + descent / 30 + max(0, duration - 90) * 0.5
    if any(term in kind for term in TREK_TERMS):
        load *= 1 + min(pack, 25) / 50
    if modality(kind) == "Strength / Functional" and "upper" not in str((feedback or {}).get("focus", "")).lower():
        load += duration * 3
    return float(load)


def exponential_load(values: pd.Series, time_constant: float, initial: float | None = None) -> pd.Series:
    """Banister-style recursion where alpha=1-exp(-1/tau), not pandas span."""
    values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if values.empty:
        return values.astype(float)
    alpha = 1 - np.exp(-1 / time_constant)
    state = float(values.iloc[0] if initial is None else initial)
    output = []
    for value in values:
        state = state + alpha * (float(value) - state)
        output.append(state)
    return pd.Series(output, index=values.index, dtype=float)


def performance_management(load: pd.Series, atl_tau: float = 7, ctl_tau: float = 42) -> pd.DataFrame:
    atl = exponential_load(load, atl_tau)
    ctl = exponential_load(load, ctl_tau)
    # Today's form is based only on loads known before today.
    tsb = ctl.shift(1).fillna(ctl.iloc[0]) - atl.shift(1).fillna(atl.iloc[0])
    return pd.DataFrame({"atl": atl, "ctl": ctl, "tsb": tsb})


def build_daily_frames(payload: dict[str, Any], feedback: dict[str, dict[str, Any]] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    feedback = feedback or {}
    wellness = pd.DataFrame(payload.get("wellness", []))
    if wellness.empty:
        wellness = pd.DataFrame(columns=["date", "hrv", "sleep_score", "resting_hr"])
    wellness["date"] = pd.to_datetime(wellness.get("date"), errors="coerce").dt.normalize()
    wellness = wellness.dropna(subset=["date"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    for column in ["hrv", "sleep_score", "resting_hr", "sleep_hours", "spo2"]:
        wellness[column] = pd.to_numeric(wellness.get(column), errors="coerce")

    rows: list[dict[str, Any]] = []
    for item in payload.get("activities", []):
        parsed = pd.to_datetime(item.get("startTimeLocal") or item.get("startTimeGMT"), errors="coerce")
        if pd.isna(parsed):
            continue
        activity_id = str(item.get("activityId") or f"{parsed.isoformat()}-{len(rows)}")
        duration_min = (number(item.get("duration"), 0.0) or 0.0) / 60
        kind = activity_type(item)
        row = {
            "activity_id": activity_id, "date": parsed.normalize(), "name": item.get("activityName", kind.title()),
            "type": kind, "modality": modality(kind), "duration_min": duration_min,
            "calories": number(item.get("calories")), "avg_hr": number(item.get("averageHR") or item.get("averageHeartRate")),
            "max_hr": number(item.get("maxHR") or item.get("maxHeartRate")),
            "distance_km": (number(item.get("distance"), 0.0) or 0.0) / 1000,
            "ascent_m": number(item.get("elevationGain") or item.get("totalElevationGain"), 0.0) or 0.0,
            "descent_m": number(item.get("elevationLoss") or item.get("totalElevationLoss"), 0.0) or 0.0,
            "hr_zone_minutes": item.get("hr_zone_minutes"),
        }
        zone_minutes = extract_hr_zone_minutes(row["hr_zone_minutes"])
        has_zones = any(zone_minutes)
        row["hr_zone_minutes"] = zone_minutes if has_zones else None
        row["zone2_min"] = zone_minutes[1] if has_zones else np.nan
        row["high_intensity_min"] = sum(zone_minutes[3:5]) if has_zones else np.nan
        if row["modality"] == "Cardio":
            row["cardio_load"], row["load_method"], row["load_confidence"] = cardio_load(row)
            row["strength_load"] = 0.0
        elif row["modality"] == "Strength / Functional":
            row["strength_load"], row["load_method"], row["load_confidence"] = strength_load(row, feedback.get(activity_id))
            row["cardio_load"] = 0.0
        else:
            row["cardio_load"] = duration_min * 3
            row["strength_load"] = 0.0
            row["load_method"], row["load_confidence"] = "duration_proxy", "low"
        row["musculoskeletal_load"] = musculoskeletal_load(row, feedback.get(activity_id))
        row["session_load"] = duration_min * (number(feedback.get(activity_id, {}).get("rpe"), 0) or 0)
        focus = str(feedback.get(activity_id, {}).get("focus", "")).lower()
        naturally_lower_body = any(term in kind for term in {"run", "hike", "trek", "walk", "cycling", "bike"})
        row["lower_body"] = naturally_lower_body or any(term in focus for term in {"lower", "leg", "láb", "alsótest"})
        row["lower_body_load"] = row["musculoskeletal_load"] if row["lower_body"] else 0.0
        rows.append(row)
    activities = pd.DataFrame(rows)
    if wellness.empty and activities.empty:
        return wellness, activities
    starts = ([wellness.index.min()] if not wellness.empty else []) + ([activities["date"].min()] if not activities.empty else [])
    ends = ([wellness.index.max()] if not wellness.empty else []) + ([activities["date"].max()] if not activities.empty else [])
    index = pd.date_range(min(starts), max(ends), freq="D")
    wellness = wellness.reindex(index)
    for column in ["cardio_load", "strength_load", "musculoskeletal_load", "lower_body_load"]:
        daily = activities.groupby("date")[column].sum() if not activities.empty else pd.Series(dtype=float)
        wellness[column] = daily.reindex(index, fill_value=0.0)
        baseline = wellness[column].rolling(28, min_periods=7).median().replace(0, np.nan)
        wellness[f"{column}_normalized"] = (wellness[column] / baseline).clip(0, 4).fillna(0)
    wellness["hybrid_load"] = 100 * (
        0.45 * wellness["cardio_load_normalized"] + 0.35 * wellness["strength_load_normalized"] + 0.20 * wellness["musculoskeletal_load_normalized"]
    )
    for column in ["zone2_min", "high_intensity_min"]:
        daily = activities.groupby("date")[column].sum(min_count=1) if not activities.empty else pd.Series(dtype=float)
        wellness[column] = daily.reindex(index)
    for prefix in ["cardio", "strength", "hybrid"]:
        pmc = performance_management(wellness[f"{prefix}_load"])
        wellness[f"{prefix}_atl"] = pmc["atl"]
        wellness[f"{prefix}_ctl"] = pmc["ctl"]
        wellness[f"{prefix}_tsb"] = pmc["tsb"]
    # Backwards-compatible aliases.
    wellness["stress"] = wellness["hybrid_load"]
    wellness["atl"], wellness["ctl"], wellness["tsb"] = wellness["hybrid_atl"], wellness["hybrid_ctl"], wellness["hybrid_tsb"]
    return wellness, activities


def data_quality(latest: pd.Series, baseline_days: int, has_checkin: bool, sync_age_hours: float) -> dict[str, Any]:
    checks = {
        "HRV": pd.notna(latest.get("hrv")), "alvás": pd.notna(latest.get("sleep_score")),
        "nyugalmi pulzus": pd.notna(latest.get("resting_hr")), "aktivitási előzmény": latest.get("hybrid_ctl", 0) > 0,
        "stabil baseline": baseline_days >= 14, "napi check-in": has_checkin, "friss szinkron": sync_age_hours <= 36,
    }
    weights = {"HRV": 20, "alvás": 20, "nyugalmi pulzus": 15, "aktivitási előzmény": 10, "stabil baseline": 15, "napi check-in": 10, "friss szinkron": 10}
    score = sum(weights[key] for key, ok in checks.items() if ok)
    level = "magas" if score >= 80 else "közepes" if score >= 55 else "alacsony"
    return {"score": score, "level": level, "available": [k for k, v in checks.items() if v], "missing": [k for k, v in checks.items() if not v]}


@dataclass
class ReadinessResult:
    score: float | None
    confidence: str
    components: list[dict[str, Any]]
    positives: list[str]
    negatives: list[str]
    missing: list[str]


def explainable_readiness(frame: pd.DataFrame, checkin: dict[str, Any] | None = None, window: int = 28) -> ReadinessResult:
    if frame.empty:
        return ReadinessResult(None, "alacsony", [], [], [], ["napi adatok"])
    latest, history = frame.iloc[-1], frame.iloc[:-1]
    definitions = []
    hrv_base = personal_baseline(history["hrv"], window)
    rhr_base = personal_baseline(history["resting_hr"], window)
    if pd.notna(latest.get("hrv")) and hrv_base["median"]:
        deviation = 100 * (latest["hrv"] / hrv_base["median"] - 1)
        definitions.append(("HRV", np.clip(70 + deviation * 2.5, 0, 100), 0.25, latest["hrv"], hrv_base["median"], deviation))
    if pd.notna(latest.get("sleep_score")):
        recent_sleep = pd.to_numeric(frame["sleep_score"].tail(3), errors="coerce")
        debt = max(0.0, 80 - float(recent_sleep.mean())) if recent_sleep.notna().any() else 0
        definitions.append(("Alvás", np.clip(float(latest["sleep_score"]) - debt, 0, 100), 0.25, latest["sleep_score"], 80, latest["sleep_score"] - 80))
    if pd.notna(latest.get("resting_hr")) and rhr_base["median"]:
        deviation = float(latest["resting_hr"] - rhr_base["median"])
        definitions.append(("RHR", np.clip(75 - deviation * 6, 0, 100), 0.15, latest["resting_hr"], rhr_base["median"], deviation))
    if pd.notna(latest.get("hybrid_tsb")):
        tsb = float(latest["hybrid_tsb"])
        definitions.append(("Terhelés / TSB", np.clip(75 + tsb * 2, 0, 100), 0.15, tsb, 0, tsb))
    previous_load = float(frame["hybrid_load"].iloc[-2]) if len(frame) > 1 else 0
    hard_days = int((frame["hybrid_load"].tail(4).iloc[:-1] > frame["hybrid_load"].quantile(0.7)).sum()) if len(frame) > 3 else 0
    definitions.append(("Előző terhelés", np.clip(85 - previous_load / 4 - max(0, hard_days - 1) * 12, 0, 100), 0.10, previous_load, None, None))
    if checkin:
        manual = 100 - (checkin["soreness"] - 1) * 8 - (checkin["stress"] - 1) * 7 - (checkin["fatigue"] - 1) * 8 + (checkin["motivation"] - 3) * 6
        if checkin.get("pain") == "significant" or checkin.get("illness"):
            manual = min(manual, 20)
        definitions.append(("Manuális wellness", np.clip(manual, 0, 100), 0.10, manual, None, None))
    components, positives, negatives = [], [], []
    total_weight = sum(item[2] for item in definitions)
    score = sum(float(item[1]) * item[2] for item in definitions) / total_weight if total_weight else None
    for name, points, weight, current, baseline, deviation in definitions:
        interpretation = "támogató" if points >= 70 else "semleges" if points >= 50 else "korlátozó"
        components.append({"name": name, "score": round(float(points)), "weight": round(weight / total_weight * 100), "current": current, "baseline": baseline, "deviation": deviation, "interpretation": interpretation})
        (positives if points >= 70 else negatives if points < 50 else []).append(f"{name}: {interpretation}")
    expected = {"HRV", "Alvás", "RHR", "Terhelés / TSB", "Előző terhelés", "Manuális wellness"}
    missing = sorted(expected - {c["name"] for c in components})
    confidence = "magas" if total_weight >= 0.9 and hrv_base["stable"] else "közepes" if total_weight >= 0.65 else "alacsony"
    return ReadinessResult(round(score) if score is not None else None, confidence, components, positives, negatives, missing)


def readiness(frame: pd.DataFrame) -> tuple[float | None, dict[str, float], str]:
    result = explainable_readiness(frame)
    recommendation = "Magas intenzitás" if (result.score or 0) >= 80 else "Zone 2 alapozás" if (result.score or 0) >= 60 else "Aktív regeneráció"
    return result.score, {c["name"]: c["score"] for c in result.components}, recommendation


def red_flags(frame: pd.DataFrame, checkin: dict[str, Any] | None = None, sync_age_hours: float = 0) -> list[dict[str, str]]:
    if frame.empty:
        return [{"severity": "high", "title": "Nincs adat", "trigger": "üres adatsor", "action": "Szinkronizálj vagy használd a demo módot."}]
    flags: list[dict[str, str]] = []
    latest, history = frame.iloc[-1], frame.iloc[:-1]
    hrv_base = personal_baseline(history["hrv"])
    rhr_base = personal_baseline(history["resting_hr"])
    if hrv_base["median"] and (frame["hrv"].tail(3) < hrv_base["median"] * 0.92).all():
        flags.append({"severity": "medium", "title": "HRV három napja alacsony", "trigger": "< baseline −8%, 3 nap", "action": "Csökkentsd az intenzitást és figyeld az alvást."})
    if rhr_base["median"] and (frame["resting_hr"].tail(3) >= rhr_base["median"] + 6).all():
        flags.append({"severity": "medium", "title": "Tartósan magas RHR", "trigger": ">= baseline +6 bpm, 3 nap", "action": "Tervezz könnyű napot és ellenőrizd a közérzetet."})
    current7 = frame["hybrid_load"].tail(7).sum()
    prior7 = frame["hybrid_load"].iloc[-14:-7].sum()
    if prior7 > 0 and current7 > prior7 * 1.2:
        flags.append({"severity": "medium", "title": "Gyors volumenemelkedés", "trigger": f"+{(current7/prior7-1)*100:.0f}% / 7 nap", "action": "Ne emeld tovább a terhelést ezen a héten."})
    threshold = frame["hybrid_load"].quantile(0.7)
    if len(frame) >= 3 and (frame["hybrid_load"].tail(3) > threshold).all():
        flags.append({"severity": "medium", "title": "Három kemény nap egymás után", "trigger": "> saját 70. percentilis", "action": "A következő nap legyen regeneráló."})
    if "lower_body_load" in frame and len(frame) >= 2:
        positive_lower = frame.loc[frame["lower_body_load"] > 0, "lower_body_load"]
        lower_threshold = positive_lower.quantile(0.70) if not positive_lower.empty else 0
        recent_lower = frame["lower_body_load"].tail(2)
        if lower_threshold > 0 and (recent_lower >= lower_threshold).all():
            flags.append({"severity": "medium", "title": "Kevés regeneráció két alsótest-terhelés között", "trigger": "két egymást követő nap a saját 70. percentilis felett", "action": "Legalább 24–48 óra könnyű, felsőtest- vagy mobilitási munka javasolt."})
    if checkin and checkin.get("pain") == "significant":
        flags.append({"severity": "high", "title": "Jelentős fájdalom", "trigger": "manuális check-in", "action": "Ne végezz magas intenzitású edzést; szükség esetén kérj szakmai segítséget."})
    if checkin and checkin.get("illness"):
        flags.append({"severity": "high", "title": "Betegségérzet", "trigger": "manuális check-in", "action": "Pihenés vagy nagyon könnyű átmozgatás."})
    if sync_age_hours > 36:
        flags.append({"severity": "low", "title": "Elavult adat", "trigger": f"utolsó szinkron {sync_age_hours:.0f} órája", "action": "Frissítsd az adatokat döntés előtt."})
    return flags


def training_decision(result: ReadinessResult, frame: pd.DataFrame, checkin: dict[str, Any] | None = None, flags: list[dict[str, str]] | None = None) -> dict[str, Any]:
    score = result.score or 0
    flags = flags or []
    rules: list[str] = []
    if checkin and checkin.get("illness"):
        choice = ("Teljes pihenő", "0–20 perc", "nagyon könnyű", "Z1", "1–2", "intenzív cardio és strength", "könnyű séta, ha jól esik")
        rules.append("illness_override")
    elif checkin and checkin.get("pain") == "significant":
        choice = ("Mobilitás / prehab", "15–30 perc", "fájdalommentes", "Z1", "1–3", "magas intenzitás és fájdalmas mozgás", "teljes pihenő")
        rules.append("significant_pain_override")
    elif result.confidence == "alacsony":
        choice = ("Aktív regeneráció", "20–45 perc", "könnyű", "Z1–Z2", "2–4", "VO2max és nehéz strength", "mobilitás")
        rules.append("low_confidence_guardrail")
    elif any(f["title"] == "Három kemény nap egymás után" for f in flags) or score < 45:
        choice = ("Aktív regeneráció", "25–45 perc", "könnyű", "Z1–Z2", "2–3", "küszöb, intervallum és nehéz láb", "mobilitás / prehab")
        rules.append("fatigue_recovery")
    elif score >= 80 and float(frame.iloc[-1].get("hybrid_tsb", 0)) > -10:
        choice = ("Minőségi hibrid edzés", "45–75 perc", "kemény, kontrollált", "Z2–Z5", "7–8", "maximális volumen", "nehéz strength vagy intervallum, de nem mindkettő")
        rules.append("high_readiness_quality")
    elif score >= 60:
        choice = ("Zone 2 alapozás", "45–70 perc", "közepes", "Z2", "4–6", "VO2max és nagy excentrikus lábterhelés", "közepes felsőtest-strength")
        rules.append("moderate_readiness_base")
    else:
        choice = ("Könnyű technikai strength", "30–50 perc", "könnyű–közepes", "Z1–Z2", "3–5", "bukásig végzett sorozatok", "könnyű Zone 2")
        rules.append("conservative_training")
    return {"type": choice[0], "duration": choice[1], "max_intensity": choice[2], "heart_rate_zone": choice[3], "rpe": choice[4], "avoid": choice[5], "alternative": choice[6], "confidence": result.confidence, "rules": rules, "rationale": "; ".join((result.positives[:2] + result.negatives[:2])) or "A rendelkezésre álló adatok konzervatív értékelése."}


def weekly_summary(frame: pd.DataFrame, activities: pd.DataFrame, flags: list[dict[str, str]]) -> dict[str, Any]:
    current = frame.tail(7)
    prior = frame.iloc[-14:-7]
    total, previous = current["hybrid_load"].sum(), prior["hybrid_load"].sum()
    change = ((total / previous - 1) * 100) if previous > 0 else None
    recent_activities = activities[activities["date"] >= current.index.min()] if not activities.empty else activities
    strength_sessions = int((recent_activities.get("modality", pd.Series(dtype=str)) == "Strength / Functional").sum())
    recommendations = []
    if change is not None and change > 20:
        recommendations.append("Stabilizáld a terhelést; ne növeld tovább a következő héten.")
    if strength_sessions < 2:
        recommendations.append("Ha a célod engedi, tervezz két strength/functional alkalmat.")
    if flags:
        recommendations.append("A hét elején kezeld a kiemelt red flageket.")
    zone2 = current["zone2_min"].sum(min_count=1) if "zone2_min" in current else np.nan
    high_intensity = current["high_intensity_min"].sum(min_count=1) if "high_intensity_min" in current else np.nan
    return {"total_load": round(total), "change_pct": None if change is None else round(change), "strength_sessions": strength_sessions, "recovery_days": int((current["hybrid_load"] < 10).sum()), "zone2_min": None if pd.isna(zone2) else round(float(zone2)), "high_intensity_min": None if pd.isna(high_intensity) else round(float(high_intensity)), "flags": len(flags), "recommendations": recommendations[:4] or ["Tartsd a jelenlegi, kiegyensúlyozott struktúrát."]}


def plan_completion_status(planned_minutes: float, actual_minutes: float) -> str:
    if actual_minutes <= 0:
        return "elmaradt"
    ratio = actual_minutes / max(planned_minutes, 1)
    if ratio < 0.75:
        return "részben teljesült"
    if ratio <= 1.25:
        return "teljesült"
    return "túlteljesült"


def evaluate_training_plans(plans: list[dict[str, Any]], activities: pd.DataFrame) -> list[dict[str, Any]]:
    """Match plans manually first, otherwise by same-day modality."""
    output: list[dict[str, Any]] = []
    used_activity_ids: set[str] = set()
    for plan in sorted(plans, key=lambda item: (str(item["planned_date"]), int(item.get("id", 0)))):
        plan_day = pd.Timestamp(plan["planned_date"]).normalize()
        matched = pd.DataFrame()
        manual_id = str(plan.get("matched_activity_id") or "")
        if manual_id and not activities.empty:
            matched = activities[activities["activity_id"].astype(str) == manual_id]
        if matched.empty and not activities.empty:
            candidates = activities[
                (activities["date"] == plan_day)
                & (activities["modality"] == plan["modality"])
                & (~activities["activity_id"].astype(str).isin(used_activity_ids))
            ]
            if not candidates.empty:
                matched = candidates.iloc[[0]]
        actual_minutes = float(matched["duration_min"].sum()) if not matched.empty else 0.0
        activity_id = str(matched.iloc[0]["activity_id"]) if not matched.empty else None
        if activity_id:
            used_activity_ids.add(activity_id)
        output.append({
            **plan,
            "actual_duration_min": round(actual_minutes),
            "actual_activity_id": activity_id,
            "status": plan_completion_status(float(plan["duration_min"]), actual_minutes),
            "duration_deviation_min": round(actual_minutes - float(plan["duration_min"])),
            "match_method": "kézi" if manual_id and activity_id == manual_id else "automatikus" if activity_id else "nincs párosítás",
        })
    return output


def plan_adjustment_message(evaluated_plans: list[dict[str, Any]]) -> str:
    completed = [plan for plan in evaluated_plans if pd.Timestamp(plan["planned_date"]) <= pd.Timestamp.today().normalize()]
    if not completed:
        return "Még nincs értékelhető korábbi terv."
    recent = completed[-3:]
    if any(plan["status"] == "túlteljesült" and plan["intensity"] == "magas" for plan in recent):
        return "A közelmúltban magas intenzitású tervet túlteljesítettél; a következő ajánlás legyen konzervatívabb."
    missed = sum(plan["status"] == "elmaradt" for plan in recent)
    if missed >= 2:
        return "Több edzés elmaradt. Ne próbáld egyszerre bepótolni őket; tervezz újra reális heti kerettel."
    if all(plan["status"] == "teljesült" for plan in recent):
        return "A legutóbbi tervek megfelelően teljesültek; nincs szükség automatikus korrekcióra."
    return "A terv részben tért el a tényleges terheléstől; a következő edzésnél a friss readiness legyen az elsődleges."


def deload_taper_recommendation(frame: pd.DataFrame, goals: list[dict[str, Any]], checkins: dict[str, dict[str, Any]] | None = None, feedback: dict[str, dict[str, Any]] | None = None, today: Any | None = None) -> dict[str, Any]:
    """Return a conservative, explainable deload or event-taper recommendation."""
    if frame.empty:
        return {"type": "nincs elég adat", "reduction_pct": 0, "duration_days": 0, "rules": ["missing_data"], "rationale": "Terhelési adatok nélkül nem adható megbízható javaslat."}
    now = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    rules: list[str] = []
    recent, previous = frame.tail(7), frame.iloc[-14:-7]
    if len(recent) >= 4 and (recent.get("hybrid_tsb", pd.Series(dtype=float)) < -20).sum() >= 4:
        rules.append("tartósan_alacsony_tsb")
    if len(previous) and recent["hybrid_load"].sum() > previous["hybrid_load"].sum() * 1.2:
        rules.append("gyors_terhelésnövekedés")
    for column, rule, direction, threshold in [("hrv", "csökkenő_hrv", -1, 2), ("resting_hr", "emelkedő_nyugalmi_pulzus", 1, 3), ("sleep_score", "romló_alvás", -1, 3)]:
        values = recent.get(column, pd.Series(dtype=float)).dropna()
        if len(values) >= 5 and direction * (values.tail(3).mean() - values.head(3).mean()) > threshold:
            rules.append(rule)
    recent_checkins = [value for day, value in (checkins or {}).items() if pd.Timestamp(day) >= now - pd.Timedelta(days=7)]
    if sum(int(item.get("motivation", 5)) <= 2 for item in recent_checkins) >= 2:
        rules.append("alacsony_motiváció")
    recent_feedback = [value for value in (feedback or {}).values() if value.get("rpe") is not None]
    if sum(int(item["rpe"]) >= 8 for item in recent_feedback[-5:]) >= 3:
        rules.append("ismételt_magas_rpe")
    event_days = [(pd.Timestamp(goal["event_date"]).normalize() - now).days for goal in goals if goal.get("event_date")]
    days_to_event = min((days for days in event_days if days >= 0), default=None)
    if days_to_event is not None and days_to_event <= 14:
        rules.append("közelgő_esemény")
        return {"type": "taper", "reduction_pct": 40 if days_to_event <= 7 else 25, "duration_days": max(3, min(14, days_to_event)), "rules": rules, "rationale": f"A legközelebbi esemény {days_to_event} nap múlva lesz; az intenzitás röviden fenntartható, a volumen csökkentendő."}
    if len(rules) >= 2:
        return {"type": "deload", "reduction_pct": 35, "duration_days": 7, "rules": rules, "rationale": f"{len(rules)} egymást erősítő fáradtsági jel aktív; egy hétig csökkentett volumen javasolt."}
    return {"type": "normál terhelés", "reduction_pct": 0, "duration_days": 0, "rules": rules or ["nincs_deload_jel"], "rationale": "Nincs legalább két, egymást erősítő deload-jel és nincs 14 napon belüli esemény."}


def event_preparation_analysis(goal: dict[str, Any], activities: pd.DataFrame, today: Any | None = None) -> dict[str, Any]:
    """Assess recent event-specific work without predicting race performance."""
    now = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    event_day = pd.Timestamp(goal["event_date"]).normalize() if goal.get("event_date") else None
    days_left = (event_day - now).days if event_day is not None else None
    recent = activities[activities["date"] >= now - pd.Timedelta(days=28)] if not activities.empty else activities
    modalities = recent.get("modality", pd.Series(index=recent.index, dtype=str))
    cardio = recent[modalities == "Cardio"]
    strength_count = int((modalities == "Strength / Functional").sum())
    distance = float(cardio.get("distance_km", pd.Series(dtype=float)).sum())
    ascent = float(cardio.get("ascent_m", pd.Series(dtype=float)).sum())
    longest = float(cardio.get("duration_min", pd.Series(dtype=float)).max()) if not cardio.empty else 0.0
    gaps: list[str] = []
    event_type = str(goal.get("event_type", "")).lower()
    target_distance, target_ascent = float(goal.get("distance_km") or 0), float(goal.get("elevation_m") or 0)
    if target_distance and distance < target_distance * 1.5:
        gaps.append("kevés eseményspecifikus táv az utóbbi 4 héten")
    if target_distance >= 20 and longest < 90:
        gaps.append("hiányzik a hosszú állóképességi edzés")
    if any(term in event_type for term in ("terep", "trek", "hegy")) and target_ascent and ascent < target_ascent * 1.5:
        gaps.append("kevés szintemelkedés az utóbbi 4 héten")
    if any(term in event_type for term in ("trek", "hibrid")) and strength_count < 4:
        gaps.append("kevés erő/functional alkalom az utóbbi 4 héten")
    status = "lejárt" if days_left is not None and days_left < 0 else "taper" if days_left is not None and days_left <= 14 else "hiányos" if gaps else "irányban"
    return {"days_left": days_left, "status": status, "distance_28d_km": round(distance, 1), "ascent_28d_m": round(ascent), "longest_session_min": round(longest), "strength_sessions_28d": strength_count, "gaps": gaps or ["nincs egyértelmű eseményspecifikus hiány a rendelkezésre álló adatokban"]}


def weekly_plan_template(goal: dict[str, Any], week_start: Any) -> list[dict[str, Any]]:
    """Create a weekly structure constrained by time, ratio, and rest day."""
    start = pd.Timestamp(week_start).normalize() - pd.Timedelta(days=pd.Timestamp(week_start).weekday())
    day_names = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
    rest_index = day_names.index(goal.get("rest_day", "vasárnap")) if goal.get("rest_day") in day_names else 6
    total_minutes = max(60, round(float(goal.get("weekly_hours") or 7) * 60))
    cardio_share = float(goal.get("cardio_target_pct") or 60) / 100
    cardio_sessions, strength_sessions = (3 if cardio_share >= .5 else 2), (2 if cardio_share <= .75 else 1)
    available = [index for index in range(7) if index != rest_index]
    session_count = cardio_sessions + strength_sessions
    base_duration = max(20, total_minutes // session_count)
    plans = []
    for position, day_index in enumerate(available[:session_count]):
        is_cardio = position < cardio_sessions
        plans.append({"planned_date": str((start + pd.Timedelta(days=day_index)).date()), "modality": "Cardio" if is_cardio else "Strength / Functional", "duration_min": base_duration, "intensity": "magas" if is_cardio and position == cardio_sessions - 1 else "közepes", "purpose": "Eseményspecifikus állóképesség" if is_cardio else "Teljes testes erő", "target_rpe": 7 if is_cardio and position == cardio_sessions - 1 else 5, "note": "Heti sablonból generálva"})
    return plans


def mountain_readiness(activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, goal: dict[str, Any] | None = None, today: Any | None = None) -> dict[str, Any]:
    """Explain mountain-specific preparation from the last 28 days."""
    now, feedback, goal = pd.Timestamp(today or pd.Timestamp.today()).normalize(), feedback or {}, goal or {}
    if activities.empty:
        return {"score": None, "confidence": "alacsony", "components": [], "metrics": {}, "gaps": ["nincs aktivitási adat"]}
    recent = activities[(activities["date"] >= now - pd.Timedelta(days=27)) & (activities["date"] <= now)].copy()
    cardio = recent[recent["modality"] == "Cardio"]
    daily = cardio.groupby("date").agg(distance_km=("distance_km", "sum"), ascent_m=("ascent_m", "sum"), duration_min=("duration_min", "sum")) if not cardio.empty else pd.DataFrame()
    back_to_back = int(sum((daily.index[index] - daily.index[index - 1]).days == 1 and daily.iloc[index - 1].duration_min >= 60 and daily.iloc[index].duration_min >= 60 for index in range(1, len(daily))))
    packs = [float(feedback.get(str(row.activity_id), {}).get("pack_kg") or 0) for _, row in recent.iterrows()]
    pack_sessions = sum(value > 0 for value in packs)
    distance, ascent = float(cardio["distance_km"].sum()), float(cardio["ascent_m"].sum())
    descent = float(cardio["descent_m"].sum())
    longest = float(daily["duration_min"].max()) if not daily.empty else 0
    strength_sessions = int((recent["modality"] == "Strength / Functional").sum())
    target_distance, target_ascent = float(goal.get("distance_km") or 25), float(goal.get("elevation_m") or 1000)
    definitions = [
        ("Táv", min(100, distance / max(target_distance * 1.5, 1) * 100), 20),
        ("Szintemelkedés", min(100, ascent / max(target_ascent * 1.5, 1) * 100), 25),
        ("Hosszú nap", min(100, longest / 180 * 100), 20),
        ("Back-to-back", min(100, back_to_back / 2 * 100), 15),
        ("Lejtmeneti kitettség", min(100, descent / max(target_ascent * 1.5, 1) * 100), 10),
        ("Erőalap", min(100, strength_sessions / 4 * 100), 10),
    ]
    score = round(sum(points * weight for _, points, weight in definitions) / 100)
    components = [{"name": name, "score": round(points), "weight": weight} for name, points, weight in definitions]
    gaps = [name for name, points, _ in definitions if points < 50]
    if any(term in str(goal.get("event_type", "")).lower() for term in ("trek", "hegy")) and pack_sessions < 2:
        gaps.append("Hátizsákos gyakorlás")
    valid_signals = sum([len(cardio) >= 4, ascent > 0, descent > 0, strength_sessions > 0, bool(goal)])
    confidence = "magas" if valid_signals >= 5 and len(recent) >= 8 else "közepes" if valid_signals >= 3 else "alacsony"
    return {"score": score, "confidence": confidence, "components": components, "metrics": {"distance_28d_km": round(distance, 1), "ascent_28d_m": round(ascent), "descent_28d_m": round(descent), "longest_day_min": round(longest), "back_to_back_pairs": back_to_back, "strength_sessions": strength_sessions, "pack_sessions": pack_sessions, "max_pack_kg": max(packs, default=0)}, "gaps": gaps or ["nincs egyértelmű hegyi felkészülési hiány"]}


def mountain_weekly_trends(activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, weeks: int = 8) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Aggregate mountain-relevant weekly exposure and flag abrupt progression."""
    columns = ["week", "distance_km", "ascent_m", "descent_m", "duration_min", "pack_kg_max"]
    if activities.empty:
        return pd.DataFrame(columns=columns), []
    data = activities.copy().sort_values("date")
    data = data[data["date"] >= data["date"].max() - pd.Timedelta(weeks=weeks)]
    data["week"] = data["date"].dt.to_period("W-MON").astype(str)
    data["pack_kg"] = [float((feedback or {}).get(str(activity_id), {}).get("pack_kg") or 0) for activity_id in data["activity_id"]]
    weekly = data.groupby("week", as_index=False).agg(distance_km=("distance_km", "sum"), ascent_m=("ascent_m", "sum"), descent_m=("descent_m", "sum"), duration_min=("duration_min", "sum"), pack_kg_max=("pack_kg", "max")).tail(weeks)
    warnings: list[dict[str, str]] = []
    if len(weekly) >= 2:
        previous, current = weekly.iloc[-2], weekly.iloc[-1]
        labels = {"distance_km": "heti táv", "ascent_m": "heti szintemelkedés", "descent_m": "heti lejtmenet", "duration_min": "heti idő"}
        for metric, label in labels.items():
            if previous[metric] > 0 and current[metric] > previous[metric] * 1.25:
                change = round((current[metric] / previous[metric] - 1) * 100)
                warnings.append({"metric": metric, "title": f"Gyors {label}növekedés", "detail": f"+{change}% az előző héthez képest", "action": "A következő héten stabilizáld ezt a terhelési dimenziót."})
        if previous["pack_kg_max"] > 0 and current["pack_kg_max"] > previous["pack_kg_max"] + 2:
            warnings.append({"metric": "pack_kg_max", "title": "Gyors hátizsák-terhelés növekedés", "detail": f"{previous['pack_kg_max']:g} kg → {current['pack_kg_max']:g} kg", "action": "Tartsd a zsák tömegét, és előbb a tolerált időt növeld."})
    return weekly, warnings


def multiday_readiness(activities: pd.DataFrame, wellness: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, today: Any | None = None) -> dict[str, Any]:
    """Estimate preparation for consecutive long days from observable training exposure."""
    now = pd.Timestamp(today or (activities["date"].max() if not activities.empty else pd.Timestamp.today())).normalize()
    recent = activities[(activities["date"] >= now - pd.Timedelta(days=55)) & (activities["date"] <= now)].copy() if not activities.empty else activities
    daily = recent.groupby("date").agg(duration_min=("duration_min", "sum"), distance_km=("distance_km", "sum"), ascent_m=("ascent_m", "sum")) if not recent.empty else pd.DataFrame()
    long_days = int((daily.get("duration_min", pd.Series(dtype=float)) >= 120).sum())
    consecutive_pairs = int(sum((daily.index[i] - daily.index[i - 1]).days == 1 and daily.iloc[i - 1].duration_min >= 90 and daily.iloc[i].duration_min >= 90 for i in range(1, len(daily))))
    feedback = feedback or {}
    stability = sum(float(item.get("stability_min") or 0) for item in feedback.values())
    single_leg = sum(float(item.get("single_leg_min") or 0) for item in feedback.values())
    components = [
        {"name": "Hosszú napok", "score": round(min(100, long_days / 4 * 100)), "weight": 35},
        {"name": "Egymást követő napok", "score": round(min(100, consecutive_pairs / 2 * 100)), "weight": 35},
        {"name": "Stabilitási munka", "score": round(min(100, stability / 60 * 100)), "weight": 15},
        {"name": "Egylábas munka", "score": round(min(100, single_leg / 60 * 100)), "weight": 15},
    ]
    score = round(sum(item["score"] * item["weight"] for item in components) / 100)
    spo2_values = wellness.get("spo2", pd.Series(dtype=float)).tail(14).dropna() if not wellness.empty else pd.Series(dtype=float)
    spo2_context = "nincs adat" if spo2_values.empty else f"14 napos medián: {spo2_values.median():.1f}%"
    confidence = "magas" if len(recent) >= 12 and long_days >= 2 else "közepes" if len(recent) >= 6 else "alacsony"
    gaps = [item["name"] for item in components if item["score"] < 50]
    return {"score": score, "confidence": confidence, "components": components, "metrics": {"long_days_56d": long_days, "consecutive_pairs_56d": consecutive_pairs, "stability_min": round(stability), "single_leg_min": round(single_leg)}, "gaps": gaps or ["nincs egyértelmű többnapos felkészülési hiány"], "spo2_context": spo2_context}


def personal_patterns(frame: pd.DataFrame, activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, minimum_days: int = 60) -> dict[str, Any]:
    """Explore non-causal personal associations with next-day recovery."""
    required = ["hrv", "resting_hr", "sleep_score", "hybrid_load", "hybrid_tsb"]
    if frame.empty:
        return {"status": "insufficient", "valid_days": 0, "minimum_days": minimum_days, "associations": [], "modalities": [], "quality": {"missing_pct": {}, "outliers": {}}, "message": "Nincs elemezhető adat."}
    data = frame.copy().sort_index()
    valid_days = int(data[["hrv", "resting_hr"]].dropna().shape[0])
    missing_pct = {column: round(float(data.get(column, pd.Series(index=data.index, dtype=float)).isna().mean() * 100), 1) for column in required}
    outliers: dict[str, int] = {}
    for column in required:
        values = data.get(column, pd.Series(dtype=float)).dropna()
        if values.empty:
            outliers[column] = 0
            continue
        q1, q3 = values.quantile(.25), values.quantile(.75)
        iqr = q3 - q1
        outliers[column] = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    quality = {"missing_pct": missing_pct, "outliers": outliers}
    if valid_days < minimum_days:
        return {"status": "insufficient", "valid_days": valid_days, "minimum_days": minimum_days, "associations": [], "modalities": [], "quality": quality, "message": f"Még {minimum_days - valid_days} érvényes nap szükséges a retrospektív elemzéshez."}
    hrv = data["hrv"]
    rhr = data["resting_hr"]
    hrv_scale = max(float((hrv - hrv.median()).abs().median()), 1.0)
    rhr_scale = max(float((rhr - rhr.median()).abs().median()), 1.0)
    data["next_recovery"] = (((hrv - hrv.median()) / hrv_scale) - ((rhr - rhr.median()) / rhr_scale)).shift(-1)
    daily_rpe = pd.Series(index=data.index, dtype=float)
    daily_modality = pd.Series(index=data.index, dtype=object)
    if not activities.empty:
        enriched = activities.copy()
        enriched["rpe"] = [number((feedback or {}).get(str(activity_id), {}).get("rpe")) for activity_id in enriched["activity_id"]]
        daily_rpe = enriched.groupby("date")["rpe"].max().reindex(data.index)
        daily_modality = enriched.sort_values("duration_min").groupby("date").tail(1).set_index("date")["modality"].reindex(data.index)
    data["session_rpe"] = daily_rpe
    feature_labels = {"sleep_score": "Alváspontszám", "hrv": "HRV", "hybrid_tsb": "TSB", "hybrid_load": "Hibrid terhelés", "session_rpe": "Edzés-RPE"}
    associations = []
    for column, label in feature_labels.items():
        pairs = data[[column, "next_recovery"]].dropna()
        if len(pairs) < 20 or pairs[column].nunique() < 3:
            continue
        rho = float(pairs[column].rank().corr(pairs["next_recovery"].rank()))
        strength = "erős" if abs(rho) >= .5 else "mérsékelt" if abs(rho) >= .3 else "gyenge"
        confidence = "magas" if len(pairs) >= 90 else "közepes" if len(pairs) >= 60 else "alacsony"
        direction = "jobb" if rho > 0 else "gyengébb"
        associations.append({"factor": label, "rho": round(rho, 2), "sample_size": len(pairs), "strength": strength, "confidence": confidence, "statement": f"A magasabb {label.lower()} {direction} következő napi regenerációval járt együtt ebben az adatsorban."})
    modality_frame = pd.DataFrame({"modality": daily_modality, "next_recovery": data["next_recovery"]}).dropna()
    modalities = []
    for modality_name, group in modality_frame.groupby("modality"):
        if len(group) >= 3:
            modalities.append({"modality": modality_name, "sample_size": len(group), "next_recovery_median": round(float(group["next_recovery"].median()), 2), "confidence": "közepes" if len(group) >= 10 else "alacsony"})
    return {"status": "ready", "valid_days": valid_days, "minimum_days": minimum_days, "associations": sorted(associations, key=lambda item: abs(item["rho"]), reverse=True), "modalities": modalities, "quality": quality, "message": "A megállapítások retrospektív kapcsolatok, nem bizonyított ok-okozati hatások."}


def pattern_uncertainty(frame: pd.DataFrame, activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, windows: tuple[int, ...] = (60, 90, 120), bootstrap_samples: int = 300) -> list[dict[str, Any]]:
    """Check window sensitivity and deterministic bootstrap intervals for associations."""
    if frame.empty:
        return []
    window_results: dict[int, dict[str, float]] = {}
    for window in windows:
        subset = frame.tail(window)
        cutoff = subset.index.min()
        subset_activities = activities[activities["date"] >= cutoff] if not activities.empty else activities
        result = personal_patterns(subset, subset_activities, feedback, minimum_days=min(60, window))
        if result["status"] == "ready":
            window_results[window] = {item["factor"]: float(item["rho"]) for item in result["associations"]}
    data = frame.copy().sort_index()
    hrv, rhr = data["hrv"], data["resting_hr"]
    hrv_scale = max(float((hrv - hrv.median()).abs().median()), 1.0)
    rhr_scale = max(float((rhr - rhr.median()).abs().median()), 1.0)
    data["next_recovery"] = (((hrv - hrv.median()) / hrv_scale) - ((rhr - rhr.median()) / rhr_scale)).shift(-1)
    data["session_rpe"] = np.nan
    if not activities.empty:
        enriched = activities.copy()
        enriched["rpe"] = [number((feedback or {}).get(str(activity_id), {}).get("rpe")) for activity_id in enriched["activity_id"]]
        data["session_rpe"] = enriched.groupby("date")["rpe"].max().reindex(data.index)
    labels = {"sleep_score": "Alváspontszám", "hrv": "HRV", "hybrid_tsb": "TSB", "hybrid_load": "Hibrid terhelés", "session_rpe": "Edzés-RPE"}
    rng = np.random.default_rng(23)
    output = []
    for column, label in labels.items():
        pairs = data[[column, "next_recovery"]].dropna()
        if len(pairs) < 20 or pairs[column].nunique() < 3:
            continue
        correlations = []
        for _ in range(bootstrap_samples):
            sample = pairs.iloc[rng.integers(0, len(pairs), len(pairs))]
            rho = sample[column].rank().corr(sample["next_recovery"].rank())
            if pd.notna(rho):
                correlations.append(float(rho))
        low, high = np.quantile(correlations, [.025, .975]) if correlations else (np.nan, np.nan)
        estimates = {window: values[label] for window, values in window_results.items() if label in values}
        signs = {int(np.sign(value)) for value in estimates.values() if value != 0}
        stable = bool(correlations) and not (low <= 0 <= high) and len(signs) <= 1 and len(estimates) >= 2
        output.append({"factor": label, "ci_low": round(float(low), 2), "ci_high": round(float(high), 2), "stable": stable, "window_estimates": estimates, "window_count": len(estimates), "message": "stabil kapcsolat" if stable else "bizonytalan vagy időablak-érzékeny kapcsolat"})
    return output


def validate_recovery_model(frame: pd.DataFrame, activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Validate a small ridge model with expanding, strictly chronological folds."""
    feature_columns = ["sleep_score", "hrv", "resting_hr", "hybrid_tsb", "hybrid_load", "session_rpe"]
    if frame.empty:
        return {"status": "insufficient", "eligible": False, "samples": 0, "folds": [], "message": "Nincs elemezhető adat."}
    data = frame.copy().sort_index()
    hrv_history = data["hrv"].shift(1).rolling(28, min_periods=14)
    rhr_history = data["resting_hr"].shift(1).rolling(28, min_periods=14)
    hrv_scale = hrv_history.std().clip(lower=1)
    rhr_scale = rhr_history.std().clip(lower=1)
    daily_recovery = (data["hrv"] - hrv_history.median()) / hrv_scale - (data["resting_hr"] - rhr_history.median()) / rhr_scale
    data["target"] = daily_recovery.shift(-1)
    data["session_rpe"] = np.nan
    if not activities.empty:
        enriched = activities.copy()
        enriched["rpe"] = [number((feedback or {}).get(str(activity_id), {}).get("rpe")) for activity_id in enriched["activity_id"]]
        data["session_rpe"] = enriched.groupby("date")["rpe"].max().reindex(data.index)
    labeled = data[feature_columns + ["target"]].dropna(subset=["target"])
    if len(labeled) < 132:
        return {"status": "insufficient", "eligible": False, "samples": len(labeled), "folds": [], "message": f"Legalább 132 célértékes nap kell; jelenleg {len(labeled)} áll rendelkezésre."}

    def fit_predict(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, float, dict[str, Any]]:
        medians = train[feature_columns].median().fillna(0)
        train_x = train[feature_columns].fillna(medians).to_numpy(dtype=float)
        test_x = test[feature_columns].fillna(medians).to_numpy(dtype=float)
        means, scales = train_x.mean(axis=0), train_x.std(axis=0)
        scales[scales < 1e-9] = 1
        train_x, test_x = (train_x - means) / scales, (test_x - means) / scales
        train_y = train["target"].to_numpy(dtype=float)
        y_mean = float(train_y.mean())
        coefficients = np.linalg.solve(train_x.T @ train_x + np.eye(len(feature_columns)) * 3.0, train_x.T @ (train_y - y_mean))
        return y_mean + test_x @ coefficients, float(np.median(train_y)), {"medians": medians, "means": means, "scales": scales, "coefficients": coefficients, "intercept": y_mean}

    test_size = min(30, max(14, (len(labeled) - 90) // 3))
    first_test = len(labeled) - 3 * test_size
    predictions, baselines, actuals, folds, fold_coefficients = [], [], [], [], []
    for fold_index in range(3):
        test_start = first_test + fold_index * test_size
        train, test = labeled.iloc[:test_start], labeled.iloc[test_start:test_start + test_size]
        model_pred, baseline, fitted_fold = fit_predict(train, test)
        fold_coefficients.append(fitted_fold["coefficients"])
        actual = test["target"].to_numpy(dtype=float)
        model_mae = float(np.mean(np.abs(actual - model_pred)))
        baseline_mae = float(np.mean(np.abs(actual - baseline)))
        folds.append({"fold": fold_index + 1, "train_days": len(train), "test_days": len(test), "test_start": str(test.index.min().date()), "test_end": str(test.index.max().date()), "model_mae": round(model_mae, 3), "baseline_mae": round(baseline_mae, 3)})
        predictions.extend(model_pred.tolist()); baselines.extend([baseline] * len(test)); actuals.extend(actual.tolist())
    actual_array, prediction_array, baseline_array = np.array(actuals), np.array(predictions), np.array(baselines)
    model_mae = float(np.mean(np.abs(actual_array - prediction_array)))
    baseline_mae = float(np.mean(np.abs(actual_array - baseline_array)))
    improvement = (baseline_mae - model_mae) / baseline_mae * 100 if baseline_mae > 0 else 0
    eligible = improvement >= 5 and sum(fold["model_mae"] < fold["baseline_mae"] for fold in folds) >= 2
    _, _, fitted = fit_predict(labeled, labeled.tail(1))
    latest = data[feature_columns].tail(1).copy()
    latest_x = latest.fillna(fitted["medians"]).to_numpy(dtype=float)
    latest_x = (latest_x - fitted["means"]) / fitted["scales"]
    forecast = float((fitted["intercept"] + latest_x @ fitted["coefficients"])[0])
    residuals = actual_array - prediction_array
    low, high = forecast + np.quantile(residuals, [.1, .9])
    coefficient_matrix = np.vstack(fold_coefficients)
    feature_audit = []
    for index, feature in enumerate(feature_columns):
        values = coefficient_matrix[:, index]
        nonzero_signs = {int(np.sign(value)) for value in values if abs(value) > .01}
        feature_audit.append({"feature": feature, "coefficient_median": round(float(np.median(values)), 3), "coefficient_range": f"{values.min():+.3f} … {values.max():+.3f}", "sign_stable": len(nonzero_signs) <= 1, "available_pct": round(float(labeled[feature].notna().mean() * 100), 1)})
    artifact = {"feature_names": feature_columns, "coefficients": [round(float(value), 8) for value in fitted["coefficients"]], "medians": [round(float(value), 8) for value in fitted["medians"].to_numpy()], "means": [round(float(value), 8) for value in fitted["means"]], "scales": [round(float(value), 8) for value in fitted["scales"]], "intercept": round(float(fitted["intercept"]), 8), "residual_q10": round(float(np.quantile(residuals, .1)), 8), "residual_q90": round(float(np.quantile(residuals, .9)), 8)}
    return {"status": "validated", "eligible": eligible, "samples": len(labeled), "data_start": str(labeled.index.min().date()), "data_end": str(labeled.index.max().date()), "folds": folds, "model_mae": round(model_mae, 3), "baseline_mae": round(baseline_mae, 3), "improvement_pct": round(improvement, 1), "forecast": round(forecast, 2) if eligible else None, "forecast_interval": [round(float(low), 2), round(float(high), 2)] if eligible else None, "feature_audit": sorted(feature_audit, key=lambda item: abs(item["coefficient_median"]), reverse=True), "artifact": artifact, "message": "A modell engedélyezhető: idősorosan felülmúlta a baseline-t." if eligible else "A modell nem jelenít meg előrejelzést: nem teljesítette az 5%-os és a legalább 2/3 foldos kaput."}


def model_promotion_decision(validation: dict[str, Any], versions: list[dict[str, Any]]) -> dict[str, Any]:
    """Promote only eligible candidates with better chronological validation MAE."""
    if validation.get("status") != "validated" or not validation.get("eligible"):
        return {"promote": False, "reason": "A jelölt nem teljesítette az idősoros validációs kaput."}
    active = next((version for version in versions if version.get("active")), None)
    if active is None:
        return {"promote": True, "reason": "Nincs korábbi aktív modell; a validált jelölt aktiválható."}
    candidate_mae, active_mae = float(validation["model_mae"]), float(active.get("model_mae", float("inf")))
    if candidate_mae < active_mae:
        return {"promote": True, "reason": f"A jelölt MAE-je jobb: {candidate_mae:.3f} < {active_mae:.3f}."}
    return {"promote": False, "reason": f"Az aktív modell MAE-je nem rosszabb: {active_mae:.3f} ≤ {candidate_mae:.3f}."}


def feature_drift_audit(frame: pd.DataFrame, activities: pd.DataFrame, feedback: dict[str, dict[str, Any]] | None = None, window: int = 60) -> dict[str, Any]:
    """Compare recent feature distributions with the directly preceding window."""
    features = ["sleep_score", "hrv", "resting_hr", "hybrid_tsb", "hybrid_load", "session_rpe"]
    if len(frame) < window * 2:
        return {"status": "insufficient", "window": window, "features": [], "alerts": 0, "message": f"Legalább {window * 2} nap szükséges a drift-audithoz."}
    data = frame.copy().sort_index()
    data["session_rpe"] = np.nan
    if not activities.empty:
        enriched = activities.copy()
        enriched["rpe"] = [number((feedback or {}).get(str(activity_id), {}).get("rpe")) for activity_id in enriched["activity_id"]]
        data["session_rpe"] = enriched.groupby("date")["rpe"].max().reindex(data.index)
    previous, recent = data.iloc[-window * 2:-window], data.iloc[-window:]
    rows = []
    for feature in features:
        old, new = previous[feature].dropna(), recent[feature].dropna()
        missing_delta = float((recent[feature].isna().mean() - previous[feature].isna().mean()) * 100)
        if len(old) < 10 or len(new) < 10:
            rows.append({"feature": feature, "psi": None, "median_shift_iqr": None, "missing_delta_pp": round(missing_delta, 1), "severity": "magas" if missing_delta >= 20 else "alacsony", "message": "Kevés érvényes adat az eloszlás összevetéséhez."})
            continue
        q1, q3 = old.quantile(.25), old.quantile(.75)
        iqr = max(float(q3 - q1), 1e-9)
        shift = abs(float(new.median() - old.median())) / iqr
        edges = np.unique(np.quantile(old, [0, .2, .4, .6, .8, 1]))
        if len(edges) >= 3:
            edges[0], edges[-1] = -np.inf, np.inf
            old_dist = pd.cut(old, edges, include_lowest=True).value_counts(normalize=True, sort=False).to_numpy() + 1e-6
            new_dist = pd.cut(new, edges, include_lowest=True).value_counts(normalize=True, sort=False).to_numpy() + 1e-6
            psi = float(np.sum((new_dist - old_dist) * np.log(new_dist / old_dist)))
        else:
            psi = 0.0
        severity = "magas" if psi >= .25 or shift >= 1 or missing_delta >= 20 else "közepes" if psi >= .1 or shift >= .5 or missing_delta >= 10 else "alacsony"
        rows.append({"feature": feature, "psi": round(psi, 3), "median_shift_iqr": round(shift, 2), "missing_delta_pp": round(missing_delta, 1), "severity": severity, "message": "jelentős eloszlásváltozás" if severity == "magas" else "figyelendő változás" if severity == "közepes" else "stabil eloszlás"})
    alerts = sum(row["severity"] == "magas" for row in rows)
    return {"status": "ready", "window": window, "features": rows, "alerts": alerts, "message": "Jelentős drift miatt az előrejelzést fokozott óvatossággal kezeld." if alerts else "Nem látható jelentős feature-drift az utolsó két ablak között."}


def tsb_zone(value: float) -> tuple[str, str]:
    return ("Friss", "#54D6A0") if value > 5 else ("Optimális terhelés", "#F5C451") if value >= -20 else ("Túlterhelési kockázat", "#FF6B6B")


def coach_insight(frame: pd.DataFrame, score: float | None, recommendation: str) -> str:
    result = explainable_readiness(frame)
    return training_decision(result, frame)["rationale"] if not frame.empty else "Szinkronizálj adatokat az ajánláshoz."


def readiness_dict(result: ReadinessResult) -> dict[str, Any]:
    return asdict(result)
