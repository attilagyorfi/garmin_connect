"""Durable, client-driven Garmin backfill for short-lived serverless functions."""
from __future__ import annotations

import json
import math
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from cloud_cache import load_user_json, save_user_json, sync_lock
from cloud_dashboard import DASHBOARD_KEY, RAW_CACHE_KEY
from dashboard_api import build_dashboard_payload
from garmin_sync import GarminSync, GarminSyncError, _wellness_record
from garmin_connection import load_tokenstore, mark_reauth_required, refresh_tokenstore


SYNC_JOB_KEY = "garmin_sync_job_v2"
ACTIVITY_PAGE_SIZE = 100
HR_ZONE_CHUNK = 8
WELLNESS_CHUNK = 5
MAX_TRANSIENT_RETRIES = 6


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = (
        "429", "rate limit", "too many requests", "timeout", "timed out",
        "temporarily", "átmenetileg", "connection reset", "connection aborted",
        "connection error", "remote end closed", "service unavailable", "502", "503", "504",
    )
    return any(marker in message for marker in markers)


def _retry_delay(attempt: int) -> int:
    return min(60, 2 ** max(1, attempt))


def _public(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"status": "idle", "phase": "idle", "progress": 0, "message": "Még nem indult szinkron."}
    return {key: job.get(key) for key in (
        "run_id", "status", "phase", "progress", "message", "activities_fetched",
        "activity_offset", "hr_zones_done", "hr_zones_total", "wellness_done",
        "wellness_total", "started_at", "updated_at", "completed_at", "partial_errors",
        "retry_count", "retry_after_seconds", "next_retry_at", "last_error",
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
    phase = job.get("phase")
    if phase and phase != "failed":
        job["resume_phase"] = phase
    message = str(exc) if isinstance(exc, GarminSyncError) else "A szinkron váratlan hiba miatt megszakadt."
    job.update(
        status="failed", phase="failed",
        message=message,
        last_error=type(exc).__name__, retry_after_seconds=0,
        next_retry_at=None, updated_at=_now(),
    )
    return job


def _schedule_retry(job: dict[str, Any], exc: Exception) -> dict[str, Any]:
    attempt = int(job.get("retry_count", 0)) + 1
    if attempt > MAX_TRANSIENT_RETRIES:
        return _fail(job, GarminSyncError(
            "A Garmin többszöri automatikus próbálkozás után sem válaszolt. "
            "Az eddigi előrehaladás megmaradt; később folytathatod a szinkront."
        ))
    delay = _retry_delay(attempt)
    job.update(
        status="running", retry_count=attempt, retry_after_seconds=delay,
        next_retry_at=(datetime.now().astimezone() + timedelta(seconds=delay)).isoformat(),
        last_error="garmin_temporarily_unavailable",
        message=f"A Garmin átmenetileg nem elérhető. Automatikus újrapróbálás {delay} másodperc múlva…",
        updated_at=_now(),
    )
    return job


def _resume_failed_job(job: dict[str, Any]) -> dict[str, Any]:
    phase = job.get("resume_phase")
    if not phase:
        raise GarminSyncError("Ez a szinkron nem folytatható. Indíts új szinkront.")
    job.update(
        status="running", phase=phase, retry_count=0, retry_after_seconds=0,
        next_retry_at=None, last_error=None,
        message="A korábbi szinkron folytatása…", updated_at=_now(),
    )
    return job


def _retry_wait_remaining(job: dict[str, Any]) -> int:
    raw = job.get("next_retry_at")
    if not raw:
        return 0
    try:
        remaining = (datetime.fromisoformat(str(raw)) - datetime.now().astimezone()).total_seconds()
        return max(0, math.ceil(remaining))
    except (TypeError, ValueError):
        return 0


def _optional_call(call: Callable[[], Any], default: Any, errors: list[str], label: str) -> Any:
    try:
        result = call()
        return default if result is None else result
    except Exception as exc:
        if _is_retryable_error(exc):
            raise GarminSyncError(
                "A Garmin átmenetileg korlátozta vagy megszakította az adatlekérést."
            ) from exc
        errors.append(f"{label}: {type(exc).__name__}")
        return default


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
        by_id[activity_id]["hr_zone_minutes"] = _optional_call(
            lambda value=activity_id: client.get_activity_hr_in_timezones(value),
            {}, errors, f"hr-zones:{activity_id}",
        )
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
        if iso not in cached or cached[iso].get("metric_schema_version") != 2 or cursor == end:
            hrv = _optional_call(lambda d=iso: client.get_hrv_data(d), {}, errors, f"hrv:{iso}")
            sleep = _optional_call(lambda d=iso: client.get_sleep_data(d), {}, errors, f"sleep:{iso}")
            heart = _optional_call(lambda d=iso: client.get_heart_rates(d), {}, errors, f"heart:{iso}")
            readiness = _optional_call(lambda d=iso: client.get_morning_training_readiness(d), {}, errors, f"training-readiness:{iso}") if cursor == end else None
            cached[iso] = _wellness_record(iso, hrv, sleep, heart, readiness)
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
        if current and current.get("status") == "running":
            job = current
        elif current and current.get("status") == "failed" and run_id:
            job = _resume_failed_job(current)
        else:
            job = _new_job(load_user_json(user_id, RAW_CACHE_KEY, db) or {})

        wait = _retry_wait_remaining(job)
        if wait:
            job["retry_after_seconds"] = wait
            save_user_json(user_id, SYNC_JOB_KEY, job, db)
            return _public(job), 202
        try:
            if job["phase"] == "finalize":
                _finalize(job, db, user_id)
            else:
                tokenstore = load_tokenstore(user_id)
                sync = GarminSync(
                    Path(tempfile.gettempdir()) / f"hybrid-sync-{job['run_id']}",
                    tokenstore=tokenstore,
                )
                try:
                    sync.authenticate()
                    refresh_tokenstore(user_id, sync.dump_tokenstore())
                except Exception as exc:
                    message = str(exc).lower()
                    if any(marker in message for marker in ("hitelesítési", "munkamenet", "újra kell")):
                        mark_reauth_required(user_id)
                    raise
                if job["phase"] == "activities":
                    _advance_activities(job, sync)
                elif job["phase"] == "hr_zones":
                    _advance_hr_zones(job, sync)
                elif job["phase"] == "wellness":
                    _advance_wellness(job, sync)
                job.update(retry_count=0, retry_after_seconds=0, next_retry_at=None, last_error=None)
                job["updated_at"] = _now()
        except Exception as exc:
            if _is_retryable_error(exc):
                _schedule_retry(job, exc)
            else:
                _fail(job, exc)
        save_user_json(user_id, SYNC_JOB_KEY, job, db)
        public = _public(job)
        return public, 200 if job["status"] == "completed" else 202 if job["status"] == "running" else 409
