"""Durable, client-driven Garmin backfill for short-lived serverless functions."""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cloud_cache import load_user_json, save_user_json, sync_lock
from cloud_dashboard import DASHBOARD_KEY, RAW_CACHE_KEY
from dashboard_api import build_dashboard_payload
from garmin_sync import GarminSync, GarminSyncError, _first_number, _sleep_score
from garmin_connection import load_credentials


SYNC_JOB_KEY = "garmin_sync_job_v2"
ACTIVITY_PAGE_SIZE = 100
HR_ZONE_CHUNK = 8
WELLNESS_CHUNK = 5


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _public(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"status": "idle", "phase": "idle", "progress": 0, "message": "Még nem indult szinkron."}
    return {key: job.get(key) for key in (
        "run_id", "status", "phase", "progress", "message", "activities_fetched",
        "activity_offset", "hr_zones_done", "hr_zones_total", "wellness_done",
        "wellness_total", "started_at", "updated_at", "completed_at", "partial_errors",
    ) if job.get(key) is not None}


def sync_status(user_id: str) -> dict[str, Any]:
    return _public(load_user_json(user_id, SYNC_JOB_KEY))


def _new_job(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": uuid.uuid4().hex,
        "status": "running",
        "phase": "activities",
        "progress": 1,
        "message": "A teljes aktivitástörténet lekérése…",
        "activity_offset": 0,
        "activities_fetched": 0,
        "hr_zones_done": 0,
        "wellness_done": 0,
        "partial_errors": [],
        "raw": raw,
        "started_at": _now(),
        "updated_at": _now(),
    }


def _fail(job: dict[str, Any], exc: Exception) -> dict[str, Any]:
    job.update(status="failed", phase="failed", message=str(exc) or "A szinkron megszakadt.", updated_at=_now())
    return job


def _activity_kind(activity: dict[str, Any]) -> str:
    raw_type = activity.get("activityType", {})
    return str(raw_type.get("typeKey", "") if isinstance(raw_type, dict) else raw_type).lower()


def _is_cardio(activity: dict[str, Any]) -> bool:
    terms = {"run", "running", "trail", "walk", "walking", "hike", "hiking", "trek", "cycling", "bike", "swim", "rowing", "elliptical", "cardio"}
    return any(term in _activity_kind(activity) for term in terms)


def _earliest_activity_date(activities: list[dict[str, Any]]) -> date:
    parsed: list[date] = []
    for item in activities:
        raw = item.get("startTimeLocal") or item.get("startTimeGMT")
        try:
            parsed.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date())
        except (TypeError, ValueError):
            continue
    return min(parsed) if parsed else date.today() - timedelta(days=29)


def _advance_activities(job: dict[str, Any], sync: GarminSync) -> None:
    client = sync.client
    assert client is not None
    offset = int(job.get("activity_offset", 0))
    page = client.get_activities(offset, ACTIVITY_PAGE_SIZE)
    if not isinstance(page, list):
        raise GarminSyncError("A Garmin aktivitáslistája ismeretlen formátumban érkezett.")
    raw = job["raw"]
    activities = sync._merge_records(raw.get("activities", []), [item for item in page if isinstance(item, dict)], "activityId")
    raw["activities"] = activities
    job["activities_fetched"] = len(activities)
    job["activity_offset"] = offset + len(page)
    if page and len(page) >= ACTIVITY_PAGE_SIZE:
        job.update(progress=min(30, 2 + (offset // ACTIVITY_PAGE_SIZE + 1) * 2), message=f"{len(activities)} aktivitás betöltve; folytatás a régebbi adatokkal…")
        return
    candidates = [item for item in activities if _is_cardio(item) and item.get("activityId") and item.get("hr_zone_minutes") is None]
    job.update(phase="hr_zones", hr_zone_ids=[str(item["activityId"]) for item in candidates], hr_zones_total=len(candidates), hr_zones_done=0, earliest_date=_earliest_activity_date(activities).isoformat(), progress=32, message="Pulzuszóna-részletek kiegészítése…")


def _advance_hr_zones(job: dict[str, Any], sync: GarminSync) -> None:
    client = sync.client
    assert client is not None
    ids = job.get("hr_zone_ids", [])
    start = int(job.get("hr_zones_done", 0))
    errors = job.setdefault("partial_errors", [])
    activities = job["raw"].get("activities", [])
    by_id = {str(item.get("activityId")): item for item in activities if item.get("activityId") is not None}
    for activity_id in ids[start:start + HR_ZONE_CHUNK]:
        by_id[activity_id]["hr_zone_minutes"] = sync._safe_call(lambda value=activity_id: client.get_activity_hr_in_timezones(value), {}, errors, f"hr-zones:{activity_id}")
    done = min(len(ids), start + HR_ZONE_CHUNK)
    job["hr_zones_done"] = done
    if done < len(ids):
        job.update(progress=32 + round(18 * done / max(1, len(ids))), message=f"Pulzuszónák: {done}/{len(ids)} aktivitás.")
        return
    start_date = date.fromisoformat(job["earliest_date"])
    total = (date.today() - start_date).days + 1
    job.update(phase="wellness", wellness_cursor=start_date.isoformat(), wellness_total=total, wellness_done=0, progress=52, message="Napi HRV-, alvás- és pulzusadatok visszatöltése…")


def _advance_wellness(job: dict[str, Any], sync: GarminSync) -> None:
    client = sync.client
    assert client is not None
    raw = job["raw"]
    cached = {str(item.get("date")): item for item in raw.get("wellness", []) if item.get("date")}
    cursor, end = date.fromisoformat(job["wellness_cursor"]), date.today()
    errors = job.setdefault("partial_errors", [])
    processed = 0
    while cursor <= end and processed < WELLNESS_CHUNK:
        iso = cursor.isoformat()
        if iso not in cached:
            hrv = sync._safe_call(lambda d=iso: client.get_hrv_data(d), {}, errors, f"hrv:{iso}")
            sleep = sync._safe_call(lambda d=iso: client.get_sleep_data(d), {}, errors, f"sleep:{iso}")
            heart = sync._safe_call(lambda d=iso: client.get_heart_rates(d), {}, errors, f"heart:{iso}")
            hrv_summary = hrv.get("hrvSummary", hrv) if isinstance(hrv, dict) else {}
            sleep_daily = sleep.get("dailySleepDTO", sleep) if isinstance(sleep, dict) else {}
            sleep_seconds = _first_number(sleep_daily, "sleepTimeSeconds", "sleepTime")
            cached[iso] = {"date": iso, "hrv": _first_number(hrv_summary, "lastNightAvg", "weeklyAvg", "lastNight5MinHigh"), "sleep_score": _sleep_score(sleep_daily) or _sleep_score(sleep), "sleep_hours": sleep_seconds / 3600 if sleep_seconds else None, "resting_hr": _first_number(heart, "restingHeartRate", "restingHeartRateValue"), "spo2": _first_number(sleep_daily, "averageSpO2Value", "averageSpo2", "avgSpO2")}
        cursor += timedelta(days=1)
        processed += 1
    raw["wellness"] = sorted(cached.values(), key=lambda item: item["date"])
    if len(errors) > 100:
        del errors[:-100]
    total = int(job["wellness_total"])
    done = min(total, int(job.get("wellness_done", 0)) + processed)
    job.update(wellness_cursor=cursor.isoformat(), wellness_done=done, progress=52 + round(43 * done / max(1, total)), message=f"Napi adatok: {done}/{total} nap.")
    if cursor > end:
        job.update(phase="finalize", progress=96, message="Elemzések és dashboard újraszámítása…")


def _finalize(job: dict[str, Any], db: Any, user_id: str) -> None:
    raw = job["raw"]
    raw.update(synced_at=_now(), days="all", partial_errors=job.get("partial_errors", [])[:20], backfill_in_progress=False)
    with tempfile.TemporaryDirectory(prefix="hybrid-garmin-") as directory:
        cache_dir = Path(directory)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "garmin_cache.json").write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        dashboard = build_dashboard_payload(cache_dir)
    save_user_json(user_id, RAW_CACHE_KEY, raw, db)
    save_user_json(user_id, DASHBOARD_KEY, dashboard, db)
    job.pop("raw", None)
    job.pop("hr_zone_ids", None)
    job.update(status="completed", phase="completed", progress=100, message="A teljes Garmin-előzmény szinkronizálása elkészült.", completed_at=_now(), updated_at=_now())


def advance_sync(user_id: str, run_id: str | None = None) -> tuple[dict[str, Any], int]:
    with sync_lock(user_id) as db:
        if db is None:
            raise GarminSyncError("Már fut egy szinkronlépés. Rövidesen automatikusan újrapróbáljuk.")
        current = load_user_json(user_id, SYNC_JOB_KEY, db)
        if run_id and (not current or current.get("run_id") != run_id):
            raise GarminSyncError("A szinkron munkamenete már nem érvényes. Indíts új szinkront.")
        job = current if current and current.get("status") == "running" else _new_job(load_user_json(user_id, RAW_CACHE_KEY, db) or {})
        try:
            if job["phase"] == "finalize":
                _finalize(job, db, user_id)
            else:
                email, password = load_credentials(user_id)
                sync = GarminSync(Path(tempfile.gettempdir()) / f"hybrid-sync-{job['run_id']}", email=email, password=password)
                sync.authenticate()
                if job["phase"] == "activities":
                    _advance_activities(job, sync)
                elif job["phase"] == "hr_zones":
                    _advance_hr_zones(job, sync)
                elif job["phase"] == "wellness":
                    _advance_wellness(job, sync)
                job["updated_at"] = _now()
        except Exception as exc:
            _fail(job, exc)
        save_user_json(user_id, SYNC_JOB_KEY, job, db)
        public = _public(job)
        return public, 200 if job["status"] == "completed" else 202 if job["status"] == "running" else 409
