"""Durable, client-driven Garmin backfill for short-lived serverless functions.

The job record only holds progress metadata. Fetched Garmin records are upserted one by
one into a staging table, so a step writes only what it fetched instead of rewriting the
whole multi-year history; the finalize step merges them into the raw cache once.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cloud_cache import SCHEMA_READY, load_user_json, save_user_json, sync_lock
from cloud_dashboard import DASHBOARD_KEY, RAW_CACHE_KEY
from dashboard_api import build_dashboard_payload
from garmin_profile import fetch_profile_metrics, strength_set_candidates, summarize_exercise_sets
from garmin_sync import GarminSync, GarminSyncError, _first_number, _sleep_score
from garmin_connection import load_tokenstore, mark_reauth_required, refresh_tokenstore


SYNC_JOB_KEY = "garmin_sync_job_v2"
ACTIVITY_PAGE_SIZE = 100
HR_ZONE_CHUNK = 8
STRENGTH_SET_CHUNK = 8
WELLNESS_CHUNK = 5


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class SyncStore:
    """Per-run staging area for fetched Garmin records, backed by Postgres."""

    def __init__(self, db: Any, user_id: str, run_id: str) -> None:
        self.db, self.user_id, self.run_id = db, user_id, run_id
        self._initialize()

    def _initialize(self) -> None:
        if "sync_items" in SCHEMA_READY:
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS hybrid_sync_items (
                user_id UUID NOT NULL,
                run_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                item_key TEXT NOT NULL,
                payload JSONB NOT NULL,
                PRIMARY KEY (user_id, run_id, kind, item_key)
            )
        """)
        self.db.commit()
        SCHEMA_READY.add("sync_items")

    def base_raw(self) -> dict[str, Any]:
        return load_user_json(self.user_id, RAW_CACHE_KEY, self.db) or {}

    def stage(self, kind: str, items: dict[str, dict[str, Any]]) -> None:
        """Upsert records; fields of an existing staged record are merged, not replaced."""
        if not items:
            return
        with self.db.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO hybrid_sync_items (user_id, run_id, kind, item_key, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (user_id, run_id, kind, item_key)
                DO UPDATE SET payload = hybrid_sync_items.payload || EXCLUDED.payload
            """, [
                (self.user_id, self.run_id, kind, key, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
                for key, value in items.items()
            ])
        self.db.commit()

    def staged(self, kind: str) -> dict[str, dict[str, Any]]:
        rows = self.db.execute(
            "SELECT item_key, payload FROM hybrid_sync_items WHERE user_id = %s AND run_id = %s AND kind = %s",
            (self.user_id, self.run_id, kind),
        ).fetchall()
        return {str(key): payload for key, payload in rows}

    def known_wellness_dates(self, start: str, end: str) -> set[str]:
        """Dates in [start, end] already present in the raw cache or staged in this run."""
        rows = self.db.execute("""
            SELECT item ->> 'date' FROM hybrid_user_state, jsonb_array_elements(payload -> 'wellness') AS item
            WHERE user_id = %s AND state_key = %s AND item ->> 'date' BETWEEN %s AND %s
            UNION
            SELECT item_key FROM hybrid_sync_items
            WHERE user_id = %s AND run_id = %s AND kind = 'wellness' AND item_key BETWEEN %s AND %s
        """, (self.user_id, RAW_CACHE_KEY, start, end, self.user_id, self.run_id, start, end)).fetchall()
        return {str(row[0]) for row in rows}

    def clear(self, all_runs: bool = False) -> None:
        if all_runs:
            self.db.execute("DELETE FROM hybrid_sync_items WHERE user_id = %s", (self.user_id,))
        else:
            self.db.execute("DELETE FROM hybrid_sync_items WHERE user_id = %s AND run_id = %s", (self.user_id, self.run_id))
        self.db.commit()


def _public(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"status": "idle", "phase": "idle", "progress": 0, "message": "Még nem indult szinkron."}
    return {key: job.get(key) for key in (
        "run_id", "status", "phase", "progress", "message", "activities_fetched",
        "activity_offset", "hr_zones_done", "hr_zones_total", "strength_sets_done", "strength_sets_total", "wellness_done",
        "wellness_total", "started_at", "updated_at", "completed_at", "partial_errors",
    ) if job.get(key) is not None}


def sync_status(user_id: str) -> dict[str, Any]:
    return _public(load_user_json(user_id, SYNC_JOB_KEY))


def _new_job() -> dict[str, Any]:
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


def _merged_activities(store: SyncStore, base: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Cached activities overlaid with this run's staged fields (None never overwrites a cached value)."""
    base = store.base_raw() if base is None else base
    merged = {str(item["activityId"]): item for item in base.get("activities", []) if isinstance(item, dict) and item.get("activityId") is not None}
    for key, payload in store.staged("activity").items():
        merged[key] = {**merged.get(key, {"activityId": key}), **{field: value for field, value in payload.items() if value is not None}}
    return list(merged.values())


def _advance_activities(job: dict[str, Any], sync: GarminSync, store: SyncStore) -> None:
    client = sync.client
    assert client is not None
    offset = int(job.get("activity_offset", 0))
    page = client.get_activities(offset, ACTIVITY_PAGE_SIZE)
    if not isinstance(page, list):
        raise GarminSyncError("A Garmin aktivitáslistája ismeretlen formátumban érkezett.")
    store.stage("activity", {str(item["activityId"]): item for item in page if isinstance(item, dict) and item.get("activityId") is not None})
    job["activity_offset"] = offset + len(page)
    job["activities_fetched"] = job["activity_offset"]
    if page and len(page) >= ACTIVITY_PAGE_SIZE:
        job.update(progress=min(30, 2 + (offset // ACTIVITY_PAGE_SIZE + 1) * 2), message=f"{job['activities_fetched']} aktivitás betöltve; folytatás a régebbi adatokkal…")
        return
    activities = _merged_activities(store)
    candidates = [item for item in activities if _is_cardio(item) and item.get("activityId") and item.get("hr_zone_minutes") is None]
    job.update(phase="hr_zones", hr_zone_ids=[str(item["activityId"]) for item in candidates], hr_zones_total=len(candidates), hr_zones_done=0, earliest_date=_earliest_activity_date(activities).isoformat(), progress=32, message="Pulzuszóna-részletek kiegészítése…")


def _advance_hr_zones(job: dict[str, Any], sync: GarminSync, store: SyncStore) -> None:
    client = sync.client
    assert client is not None
    ids = job.get("hr_zone_ids", [])
    start = int(job.get("hr_zones_done", 0))
    errors = job.setdefault("partial_errors", [])
    zones = {
        activity_id: {"hr_zone_minutes": sync._safe_call(lambda value=activity_id: client.get_activity_hr_in_timezones(value), {}, errors, f"hr-zones:{activity_id}")}
        for activity_id in ids[start:start + HR_ZONE_CHUNK]
    }
    store.stage("activity", zones)
    done = min(len(ids), start + HR_ZONE_CHUNK)
    job["hr_zones_done"] = done
    if done < len(ids):
        job.update(progress=32 + round(12 * done / max(1, len(ids))), message=f"Pulzuszónák: {done}/{len(ids)} aktivitás.")
        return
    job.pop("hr_zone_ids", None)
    candidates = strength_set_candidates(_merged_activities(store))
    job.update(phase="strength_sets", strength_set_ids=candidates, strength_sets_total=len(candidates), strength_sets_done=0, progress=44, message="Erőedzés-sorozatok betöltése…")


def _advance_strength_sets(job: dict[str, Any], sync: GarminSync, store: SyncStore) -> None:
    client = sync.client
    assert client is not None
    ids = job.get("strength_set_ids", [])
    start = int(job.get("strength_sets_done", 0))
    errors = job.setdefault("partial_errors", [])
    store.stage("activity", {
        activity_id: {"exercise_sets": summarize_exercise_sets(sync._safe_call(lambda value=activity_id: client.get_activity_exercise_sets(value), {}, errors, f"exercise-sets:{activity_id}"))}
        for activity_id in ids[start:start + STRENGTH_SET_CHUNK]
    })
    done = min(len(ids), start + STRENGTH_SET_CHUNK)
    job["strength_sets_done"] = done
    if done < len(ids):
        job.update(progress=44 + round(6 * done / max(1, len(ids))), message=f"Erőedzés-sorozatok: {done}/{len(ids)} edzés.")
        return
    job.pop("strength_set_ids", None)
    job.update(phase="profile", progress=50, message="VO2max, testösszetétel és sportprofil lekérése…")


def _advance_profile(job: dict[str, Any], sync: GarminSync, store: SyncStore) -> None:
    client = sync.client
    assert client is not None
    store.stage("profile", {"latest": fetch_profile_metrics(client, sync._safe_call, job.setdefault("partial_errors", []))})
    start_date = date.fromisoformat(job["earliest_date"])
    total = (date.today() - start_date).days + 1
    job.update(phase="wellness", wellness_cursor=start_date.isoformat(), wellness_total=total, wellness_done=0, progress=52, message="Napi HRV-, alvás- és pulzusadatok visszatöltése…")


def _advance_wellness(job: dict[str, Any], sync: GarminSync, store: SyncStore) -> None:
    client = sync.client
    assert client is not None
    cursor, end = date.fromisoformat(job["wellness_cursor"]), date.today()
    chunk_end = min(end, cursor + timedelta(days=WELLNESS_CHUNK - 1))
    known = store.known_wellness_dates(cursor.isoformat(), chunk_end.isoformat())
    errors = job.setdefault("partial_errors", [])
    fetched: dict[str, dict[str, Any]] = {}
    processed = 0
    while cursor <= end and processed < WELLNESS_CHUNK:
        iso = cursor.isoformat()
        if iso not in known:
            hrv = sync._safe_call(lambda d=iso: client.get_hrv_data(d), {}, errors, f"hrv:{iso}")
            sleep = sync._safe_call(lambda d=iso: client.get_sleep_data(d), {}, errors, f"sleep:{iso}")
            heart = sync._safe_call(lambda d=iso: client.get_heart_rates(d), {}, errors, f"heart:{iso}")
            hrv_summary = hrv.get("hrvSummary", hrv) if isinstance(hrv, dict) else {}
            sleep_daily = sleep.get("dailySleepDTO", sleep) if isinstance(sleep, dict) else {}
            sleep_seconds = _first_number(sleep_daily, "sleepTimeSeconds", "sleepTime")
            fetched[iso] = {"date": iso, "hrv": _first_number(hrv_summary, "lastNightAvg", "weeklyAvg", "lastNight5MinHigh"), "sleep_score": _sleep_score(sleep_daily) or _sleep_score(sleep), "sleep_hours": sleep_seconds / 3600 if sleep_seconds else None, "resting_hr": _first_number(heart, "restingHeartRate", "restingHeartRateValue"), "spo2": _first_number(sleep_daily, "averageSpO2Value", "averageSpo2", "avgSpO2")}
        cursor += timedelta(days=1)
        processed += 1
    store.stage("wellness", fetched)
    if len(errors) > 100:
        del errors[:-100]
    total = int(job["wellness_total"])
    done = min(total, int(job.get("wellness_done", 0)) + processed)
    job.update(wellness_cursor=cursor.isoformat(), wellness_done=done, progress=52 + round(43 * done / max(1, total)), message=f"Napi adatok: {done}/{total} nap.")
    if cursor > end:
        job.update(phase="finalize", progress=96, message="Elemzések és dashboard újraszámítása…")


def _finalize(job: dict[str, Any], store: SyncStore) -> None:
    raw = store.base_raw()
    wellness = {str(item.get("date")): item for item in raw.get("wellness", []) if item.get("date")}
    wellness.update(store.staged("wellness"))
    profile = store.staged("profile").get("latest")
    if profile:
        raw["profile"] = profile
    raw.update(
        activities=_merged_activities(store, raw),
        wellness=sorted(wellness.values(), key=lambda item: item["date"]),
        synced_at=_now(), days="all", partial_errors=job.get("partial_errors", [])[:20], backfill_in_progress=False,
    )
    with tempfile.TemporaryDirectory(prefix="hybrid-garmin-") as directory:
        cache_dir = Path(directory)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "garmin_cache.json").write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        dashboard = build_dashboard_payload(cache_dir)
    save_user_json(store.user_id, RAW_CACHE_KEY, raw, store.db)
    save_user_json(store.user_id, DASHBOARD_KEY, dashboard, store.db)
    store.clear()
    job.update(status="completed", phase="completed", progress=100, message="A teljes Garmin-előzmény szinkronizálása elkészült.", completed_at=_now(), updated_at=_now())


REAUTH_MARKERS = ("hitelesítési hiba", "mfa szükséges")


def _authenticated_sync(user_id: str, run_id: str) -> GarminSync:
    """Log in with the stored, encrypted Garmin session; no Garmin password is kept."""
    tokenstore = load_tokenstore(user_id)
    sync = GarminSync(Path(tempfile.gettempdir()) / f"hybrid-sync-{run_id}", tokenstore=tokenstore)
    try:
        sync.authenticate()
    except GarminSyncError as exc:
        if any(marker in str(exc).lower() for marker in REAUTH_MARKERS):
            mark_reauth_required(user_id)  # rate limits and outages keep the session
        raise
    refreshed = sync.export_tokens()
    if refreshed and refreshed != tokenstore:
        refresh_tokenstore(user_id, refreshed)
    return sync


def advance_sync(user_id: str, run_id: str | None = None) -> tuple[dict[str, Any], int]:
    with sync_lock(user_id) as db:
        if db is None:
            raise GarminSyncError("Már fut egy szinkronlépés. Rövidesen automatikusan újrapróbáljuk.")
        current = load_user_json(user_id, SYNC_JOB_KEY, db)
        if run_id and (not current or current.get("run_id") != run_id):
            raise GarminSyncError("A szinkron munkamenete már nem érvényes. Indíts új szinkront.")
        # Jobs written by the previous format carried the raw payload inline; restart those.
        resumable = current and current.get("status") == "running" and "raw" not in current
        job = current if resumable else _new_job()
        store = SyncStore(db, user_id, job["run_id"])
        if not resumable:
            store.clear(all_runs=True)
        try:
            if job["phase"] == "finalize":
                _finalize(job, store)
            else:
                sync = _authenticated_sync(user_id, job["run_id"])
                if job["phase"] == "activities":
                    _advance_activities(job, sync, store)
                elif job["phase"] == "hr_zones":
                    _advance_hr_zones(job, sync, store)
                elif job["phase"] == "strength_sets":
                    _advance_strength_sets(job, sync, store)
                elif job["phase"] == "profile":
                    _advance_profile(job, sync, store)
                elif job["phase"] == "wellness":
                    _advance_wellness(job, sync, store)
                job["updated_at"] = _now()
        except Exception as exc:
            db.rollback()
            _fail(job, exc)
        save_user_json(user_id, SYNC_JOB_KEY, job, db)
        public = _public(job)
        return public, 200 if job["status"] == "completed" else 202 if job["status"] == "running" else 409
