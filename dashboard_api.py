"""Read-only JSON API for the React dashboard."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from analytics import build_daily_frames, explainable_readiness, red_flags, training_decision, weekly_summary
from garmin_sync import GarminSync, GarminSyncError, demo_data
from storage import Database

load_dotenv(Path(__file__).with_name(".env.local"), override=False)
load_dotenv(Path(__file__).with_name(".env.garmin.local"), override=True)


def _number(value: Any, default: float | None = 0.0) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _sport_name(kind: Any) -> str:
    value = str(kind or "").lower()
    if "run" in value:
        return "Futás"
    if any(term in value for term in ("strength", "weight", "functional")):
        return "Erő"
    if any(term in value for term in ("hike", "walk", "trek")):
        return "Túrázás"
    if any(term in value for term in ("cycl", "bike")):
        return "Kerékpár"
    if any(term in value for term in ("mobility", "yoga", "pilates")):
        return "Mobilitás"
    return "Egyéb"


def build_dashboard_payload(cache_dir: str | Path = "data", *, allow_demo: bool = False) -> dict[str, Any]:
    cache_dir = Path(cache_dir)
    payload = GarminSync(cache_dir).load_cache()
    source = "garmin"
    if not payload:
        if not allow_demo:
            raise ValueError("Nincs szinkronizált Garmin-adat. Nem készül demóösszesítés.")
        payload, source = demo_data(365), "demo"
    db = Database(cache_dir / "training.sqlite3")
    feedback = {**payload.get("demo_feedback", {}), **db.list_feedback()}
    checkins = {**payload.get("demo_checkins", {}), **db.list_checkins()}
    wellness, activities = build_daily_frames(payload, feedback)
    if wellness.empty:
        raise ValueError("Nincs megjeleníthető wellness-adat.")
    today = str(wellness.index[-1].date())
    result = explainable_readiness(wellness, checkins.get(today))
    latest = wellness.iloc[-1]
    official_readiness = latest.get("training_readiness") if isinstance(latest.get("training_readiness"), dict) else None
    official_score = _number(official_readiness.get("score"), None) if official_readiness else None
    if official_score is not None and not 0 <= official_score <= 100:
        official_score = None
    readiness_score = official_score if official_score is not None else result.score
    readiness_source = "garmin_training_readiness" if official_score is not None else "hybrid_estimate"
    flags = red_flags(wellness, checkins.get(today), 0)
    decision = training_decision(result, wellness, checkins.get(today), flags, score_override=readiness_score)
    summary = weekly_summary(wellness, activities, flags)
    decision_source = "hybrid_rules_using_garmin_readiness" if readiness_source == "garmin_training_readiness" else "hybrid_rules"
    decision_rationale = decision.get("rationale", "A regenerációs jelek alapján.")
    if readiness_source == "garmin_training_readiness":
        decision_rationale = f"A Garmin Training Readiness pontszámát saját, óvatossági edzésválasztási szabályainkkal értelmeztük. {decision_rationale}"
    metric_definitions = [
        ("HRV (éjszakai átlag)", "hrv", ".0f", " ms", None),
        ("Garmin alváspontszám", "sleep_score", ".0f", " / 100", "value"),
        ("Alvásidő", "sleep_hours", ".1f", " ó", None),
        ("Nyugalmi pulzus", "resting_hr", ".0f", " bpm", None),
        ("Hybrid TSB", "hybrid_tsb", "+.1f", "", None),
    ]
    metrics = []
    missing_metrics = []
    for name, column, format_spec, unit, score_mode in metric_definitions:
        value = _number(latest.get(column), None)
        if value is None:
            missing_metrics.append(name)
            continue
        metrics.append({"name": name, "value": f"{value:{format_spec}}{unit}", "score": round(value) if score_mode == "value" else None, "source": "garmin" if not name.startswith("Hybrid") else "hybrid"})
    recent_load = wellness["hybrid_load"].tail(84).fillna(0)
    peak = max(1.0, _number(recent_load.max(), 1.0))
    heat = [min(3, round(_number(value) / peak * 3)) for value in recent_load]
    heat = ([0] * (84 - len(heat)) + heat)[-84:]
    weekly = wellness[["ctl", "atl", "tsb"]].resample("W-MON").mean().tail(52)
    trends = [
        {"date": stamp.date().isoformat(), "ctl": round(_number(row["ctl"]), 1), "atl": round(_number(row["atl"]), 1), "tsb": round(_number(row["tsb"]), 1)}
        for stamp, row in weekly.iterrows()
    ]
    all_sessions = activities.sort_values("date", ascending=False)
    sessions = [
        {
            "id": str(row["activity_id"]), "date": row["date"].date().isoformat(), "type": _sport_name(row["type"]),
            "name": str(row["name"]), "durationMin": round(_number(row["duration_min"])),
            "avgHr": round(_number(row["avg_hr"])) or None,
            "load": round(_number(row.get("official_activity_load"), None) if _number(row.get("official_activity_load"), None) is not None else _number(row["cardio_load"]) + _number(row["strength_load"])),
            "loadSource": "garmin_activity_training_load" if _number(row.get("official_activity_load"), None) is not None else "hybrid_estimate",
            "aerobicTrainingEffect": _number(row.get("aerobic_training_effect"), None),
            "anaerobicTrainingEffect": _number(row.get("anaerobic_training_effect"), None),
            "trainingEffectLabel": row.get("training_effect_label"),
            "vo2Max": _number(row.get("vo2_max"), None),
            "distanceKm": round(_number(row["distance_km"]), 1),
        }
        for _, row in all_sessions.iterrows()
    ]
    zone_totals = [0.0] * 5
    week_activities = activities[activities["date"] >= wellness.index[-1] - timedelta(days=6)]
    for values in week_activities["hr_zone_minutes"].dropna():
        if isinstance(values, list):
            for index, value in enumerate(values[:5]):
                zone_totals[index] += _number(value)
    return {
        "source": source,
        "generatedAt": datetime.now().astimezone().isoformat(),
        "today": today,
        "readiness": None if readiness_score is None else round(readiness_score),
        "readinessSource": readiness_source,
        "garminTrainingReadiness": official_readiness,
        "hybridReadiness": result.score,
        "band": "terhelhető" if (readiness_score or 0) >= 70 else "óvatosan" if (readiness_score or 0) >= 45 else "regeneráció",
        "confidence": "Garmin által számított" if readiness_source == "garmin_training_readiness" else result.confidence,
        "decision": {
            "title": decision.get("title") or decision.get("recommendation") or "Regeneráló edzés",
            "duration": decision.get("duration") or decision.get("duration_min") or "30–45 perc",
            "intensity": decision.get("intensity") or decision.get("max_intensity") or "könnyű",
            "rationale": decision_rationale,
            "source": decision_source,
        },
        "metrics": metrics,
        "dataQuality": {
            "referenceDate": today,
            "missingMetrics": missing_metrics,
            "unscoredMetrics": [item["name"] for item in metrics if item["score"] is None],
            "activityCount": len(sessions),
            "activityDateFrom": sessions[-1]["date"] if sessions else None,
            "activityDateTo": sessions[0]["date"] if sessions else None,
            "hrvSource": latest.get("hrv_source"),
            "hrvStatus": latest.get("hrv_status"),
            "hrvWeeklyAverage": _number(latest.get("hrv_weekly_avg"), None),
            "hrvBaselineLow": _number(latest.get("hrv_baseline_low"), None),
            "hrvBaselineHigh": _number(latest.get("hrv_baseline_high"), None),
            "loadSource": summary.get("load_source"),
            "officialLoadCoveragePct": summary.get("official_load_coverage_pct"),
        },
        "heat": heat,
        "week": summary,
        "trends": trends,
        "trendSource": "hybrid_pmc_from_garmin_activity_load" if not activities.empty and activities["official_activity_load"].notna().all() else "hybrid_pmc_mixed_load_inputs",
        "sessions": sessions,
        "zones": [round(value) for value in zone_totals],
    }


def sync_dashboard(cache_dir: str | Path = "data") -> dict[str, Any]:
    """Fetch the complete available Garmin history, then return derived values."""
    GarminSync(cache_dir).sync(None)
    return build_dashboard_payload(cache_dir)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/api/dashboard":
            self.send_error(404)
            return
        try:
            body = json.dumps(build_dashboard_payload(os.getenv("CACHE_DIR", "data")), ensure_ascii=False).encode()
            status = 200
        except Exception as exc:
            body, status = json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), 500
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/sync":
            self.send_error(404)
            return
        try:
            body = json.dumps(sync_dashboard(os.getenv("CACHE_DIR", "data")), ensure_ascii=False).encode()
            status = 200
        except GarminSyncError as exc:
            body, status = json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), 409
        except Exception:
            body, status = json.dumps({"error": "A Garmin-szinkron váratlan hiba miatt megszakadt."}, ensure_ascii=False).encode(), 500
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", int(os.getenv("DASHBOARD_API_PORT", "8765"))), DashboardHandler)
    print("Dashboard API: http://127.0.0.1:8765/api/dashboard")
    server.serve_forever()
