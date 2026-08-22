"""Read-only JSON API for the React dashboard."""
from __future__ import annotations

import json
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


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result else default
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


def build_dashboard_payload(cache_dir: str | Path = "data") -> dict[str, Any]:
    cache_dir = Path(cache_dir)
    payload = GarminSync(cache_dir).load_cache()
    source = "garmin"
    if not payload:
        payload, source = demo_data(365), "demo"
    db = Database(cache_dir / "training.sqlite3")
    feedback = {**payload.get("demo_feedback", {}), **db.list_feedback()}
    checkins = {**payload.get("demo_checkins", {}), **db.list_checkins()}
    wellness, activities = build_daily_frames(payload, feedback)
    if wellness.empty:
        raise ValueError("Nincs megjeleníthető wellness-adat.")
    today = str(wellness.index[-1].date())
    result = explainable_readiness(wellness, checkins.get(today))
    flags = red_flags(wellness, checkins.get(today), 0)
    decision = training_decision(result, wellness, checkins.get(today), flags)
    summary = weekly_summary(wellness, activities, flags)
    latest = wellness.iloc[-1]
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
            "load": round(_number(row["cardio_load"]) + _number(row["strength_load"])),
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
        "readiness": round(_number(result.score)),
        "band": "terhelhető" if _number(result.score) >= 70 else "óvatosan" if _number(result.score) >= 45 else "regeneráció",
        "confidence": result.confidence,
        "decision": {
            "title": decision.get("title") or decision.get("recommendation") or "Regeneráló edzés",
            "duration": decision.get("duration") or decision.get("duration_min") or "30–45 perc",
            "intensity": decision.get("intensity") or decision.get("max_intensity") or "könnyű",
            "rationale": decision.get("rationale", "A regenerációs jelek alapján."),
        },
        "metrics": [
            {"name": "HRV (éjszakai)", "value": f"{_number(latest.get('hrv')):.0f} ms", "score": 68},
            {"name": "Alvás", "value": f"{_number(latest.get('sleep_hours')):.1f} ó", "score": round(_number(latest.get('sleep_score')))},
            {"name": "Nyugalmi pulzus", "value": f"{_number(latest.get('resting_hr')):.0f} bpm", "score": 82},
            {"name": "Hibrid TSB", "value": f"{_number(latest.get('tsb')):+.1f}", "score": round(max(5, min(100, 50 + _number(latest.get('tsb')) * 3)))},
        ],
        "heat": heat,
        "week": summary,
        "trends": trends,
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
