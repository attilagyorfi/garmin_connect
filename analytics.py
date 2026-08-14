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
    for column in ["hrv", "sleep_score", "resting_hr", "sleep_hours"]:
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


def tsb_zone(value: float) -> tuple[str, str]:
    return ("Friss", "#54D6A0") if value > 5 else ("Optimális terhelés", "#F5C451") if value >= -20 else ("Túlterhelési kockázat", "#FF6B6B")


def coach_insight(frame: pd.DataFrame, score: float | None, recommendation: str) -> str:
    result = explainable_readiness(frame)
    return training_decision(result, frame)["rationale"] if not frame.empty else "Szinkronizálj adatokat az ajánláshoz."


def readiness_dict(result: ReadinessResult) -> dict[str, Any]:
    return asdict(result)
