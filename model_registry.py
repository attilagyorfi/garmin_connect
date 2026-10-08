"""Per-user recovery-model registry and scheduled retraining orchestration."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from typing import Any

from analytics import (
    build_daily_frames,
    feature_drift_audit,
    model_promotion_decision,
    recovery_model_data_readiness,
    retraining_recommendation,
    validate_recovery_model,
)
from cloud_cache import connect


RAW_CACHE_KEY = "garmin_raw_cache_v1"
USER_STATE_KEY = "user_state_v1"
DEFAULT_BATCH_SIZE = 10
DEFAULT_TIME_BUDGET_SECONDS = 240
CRON_HOUR_UTC = 3
CRON_MINUTE_UTC = 15


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def next_scheduled_check(now: datetime | None = None) -> str:
    """Return the next daily cron time in UTC for transparent UI display."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    candidate = datetime.combine(
        current.date(),
        datetime_time(CRON_HOUR_UTC, CRON_MINUTE_UTC),
        tzinfo=timezone.utc,
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate.isoformat()


def initialize_model_registry(db: Any) -> None:
    """Create the durable, user-isolated model registry if it is missing."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS hybrid_model_versions (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            data_start DATE NOT NULL,
            data_end DATE NOT NULL,
            samples INTEGER NOT NULL,
            model_mae DOUBLE PRECISION NOT NULL,
            baseline_mae DOUBLE PRECISION NOT NULL,
            eligible BOOLEAN NOT NULL DEFAULT FALSE,
            active BOOLEAN NOT NULL DEFAULT FALSE,
            promotion_reason TEXT NOT NULL DEFAULT '',
            metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
            artifact JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS hybrid_model_versions_one_active_idx
        ON hybrid_model_versions(user_id) WHERE active
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS hybrid_model_versions_user_trained_idx
        ON hybrid_model_versions(user_id, trained_at DESC)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS hybrid_retraining_runs (
            user_id UUID PRIMARY KEY REFERENCES hybrid_users(id) ON DELETE CASCADE,
            checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status TEXT NOT NULL,
            due BOOLEAN NOT NULL DEFAULT FALSE,
            reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
            current_data_end DATE,
            candidate_model_id BIGINT REFERENCES hybrid_model_versions(id) ON DELETE SET NULL,
            message TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.commit()


def _row_version(row: Any) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "trained_at": row[1],
        "data_start": str(row[2]),
        "data_end": str(row[3]),
        "samples": int(row[4]),
        "model_mae": float(row[5]),
        "baseline_mae": float(row[6]),
        "eligible": bool(row[7]),
        "active": bool(row[8]),
        "promotion_reason": row[9] or "",
        "metrics": row[10] if isinstance(row[10], dict) else {},
    }


def list_model_versions(user_id: str, db: Any, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, trained_at, data_start, data_end, samples, model_mae,
               baseline_mae, eligible, active, promotion_reason, metrics
        FROM hybrid_model_versions
        WHERE user_id = %s
        ORDER BY trained_at DESC, id DESC
        LIMIT %s
        """,
        (user_id, max(1, min(100, int(limit)))),
    ).fetchall()
    return [_row_version(row) for row in rows]


def evaluate_retraining(
    raw_payload: dict[str, Any],
    user_state: dict[str, Any] | None,
    versions: list[dict[str, Any]],
    *,
    today: date | str | None = None,
) -> dict[str, Any]:
    """Evaluate one user's current data without writing or activating anything."""
    feedback = (user_state or {}).get("feedback") or {}
    frame, activities = build_daily_frames(raw_payload, feedback)
    if frame.empty:
        return {
            "status": "insufficient",
            "due": False,
            "reasons": ["nincs elemezhető napi adat"],
            "current_data_end": None,
            "message": "Nincs elemezhető napi adat az újratanításhoz.",
        }

    current_data_end = str(frame.index.max().date())
    # The target is next-day recovery, so the final observed day cannot yet be
    # part of a labeled training set. Match duplicates against the last day
    # that can actually appear in validate_recovery_model().
    evaluatable_data_end = str(frame.index[-2].date()) if len(frame) > 1 else current_data_end
    drift = feature_drift_audit(frame, activities, feedback)
    recommendation = retraining_recommendation(
        versions, drift, current_data_end, today=today
    )
    already_evaluated = next(
        (item for item in versions if str(item.get("data_end")) == evaluatable_data_end),
        None,
    )
    if already_evaluated:
        return {
            "status": "unchanged",
            "due": False,
            "reasons": ["ehhez az adatállapothoz már készült modelljelölt"],
            "current_data_end": current_data_end,
            "drift": drift,
            "message": "Nem érkezett a legutóbbi modelljelölt óta új adat.",
        }
    latest_attempt = versions[0] if versions else None
    if latest_attempt:
        days_since_attempt = max(
            0, (_as_date(today or date.today()) - _as_date(latest_attempt["trained_at"])).days
        )
        new_labeled_days = max(
            0,
            (_as_date(evaluatable_data_end) - _as_date(latest_attempt["data_end"])).days,
        )
        cooldown_days = 7 if int(drift.get("alerts", 0)) > 0 else 30
        if days_since_attempt < cooldown_days and new_labeled_days < cooldown_days:
            return {
                "status": "not_due",
                "due": False,
                "reasons": [
                    f"az utolsó modelljelölt óta még csak {new_labeled_days} új címkézett adatnap érkezett"
                ],
                "current_data_end": current_data_end,
                "drift": drift,
                "message": (
                    "A rendszer naponta ellenőriz, de változatlan vagy alig bővült "
                    "adatokon nem tanít újra feleslegesen."
                ),
            }
    if not recommendation["due"]:
        return {
            "status": "not_due",
            "due": False,
            "reasons": recommendation["reasons"],
            "current_data_end": current_data_end,
            "drift": drift,
            "message": "Jelenleg nincs szükség új modelljelöltre.",
        }

    validation = validate_recovery_model(frame, activities, feedback)
    if validation.get("status") != "validated":
        return {
            "status": "insufficient",
            "due": True,
            "reasons": recommendation["reasons"],
            "current_data_end": current_data_end,
            "drift": drift,
            "validation": validation,
            "message": validation.get("message", "Még nincs elég adat az újratanításhoz."),
        }

    promotion = model_promotion_decision(validation, versions)
    return {
        "status": "candidate_ready",
        "due": True,
        "reasons": recommendation["reasons"],
        "current_data_end": current_data_end,
        "drift": drift,
        "validation": validation,
        "promotion": promotion,
        "message": promotion["reason"],
    }


def _save_candidate(user_id: str, evaluation: dict[str, Any], db: Any) -> int:
    validation = evaluation["validation"]
    promotion = evaluation["promotion"]
    if promotion["promote"]:
        db.execute(
            "UPDATE hybrid_model_versions SET active = FALSE WHERE user_id = %s AND active",
            (user_id,),
        )
    metrics = {key: value for key, value in validation.items() if key != "artifact"}
    row = db.execute(
        """
        INSERT INTO hybrid_model_versions (
            user_id, data_start, data_end, samples, model_mae, baseline_mae,
            eligible, active, promotion_reason, metrics, artifact
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            user_id,
            validation["data_start"],
            validation["data_end"],
            int(validation["samples"]),
            float(validation["model_mae"]),
            float(validation["baseline_mae"]),
            bool(validation["eligible"]),
            bool(promotion["promote"]),
            promotion["reason"],
            json.dumps(metrics, ensure_ascii=False, separators=(",", ":")),
            json.dumps(validation.get("artifact") or {}, ensure_ascii=False, separators=(",", ":")),
        ),
    ).fetchone()
    return int(row[0])


def _save_run(
    user_id: str, evaluation: dict[str, Any], db: Any, candidate_id: int | None = None
) -> None:
    db.execute(
        """
        INSERT INTO hybrid_retraining_runs (
            user_id, checked_at, status, due, reasons, current_data_end,
            candidate_model_id, message
        ) VALUES (%s, NOW(), %s, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            checked_at = NOW(), status = EXCLUDED.status, due = EXCLUDED.due,
            reasons = EXCLUDED.reasons, current_data_end = EXCLUDED.current_data_end,
            candidate_model_id = EXCLUDED.candidate_model_id,
            message = EXCLUDED.message
        """,
        (
            user_id,
            evaluation.get("status", "error"),
            bool(evaluation.get("due")),
            json.dumps(evaluation.get("reasons") or [], ensure_ascii=False),
            evaluation.get("current_data_end"),
            candidate_id,
            str(evaluation.get("message") or "")[:1000],
        ),
    )


def run_scheduled_retraining(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    time_budget_seconds: int = DEFAULT_TIME_BUDGET_SECONDS,
) -> dict[str, Any]:
    """Evaluate a fair batch of users and persist only validated candidates."""
    started = time.monotonic()
    result = {"processed": 0, "trained": 0, "activated": 0, "skipped": 0, "errors": 0}
    db = connect()
    acquired = False
    try:
        initialize_model_registry(db)
        acquired = bool(
            db.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s))",
                ("hybrid-athlete-scheduled-retraining",),
            ).fetchone()[0]
        )
        if not acquired:
            return {**result, "status": "already_running"}
        rows = db.execute(
            """
            SELECT raw.user_id, raw.payload, state.payload
            FROM hybrid_user_state raw
            LEFT JOIN hybrid_user_state state
              ON state.user_id = raw.user_id AND state.state_key = %s
            LEFT JOIN hybrid_retraining_runs run ON run.user_id = raw.user_id
            WHERE raw.state_key = %s
            ORDER BY run.checked_at ASC NULLS FIRST, raw.updated_at ASC
            LIMIT %s
            """,
            (USER_STATE_KEY, RAW_CACHE_KEY, max(1, min(100, int(batch_size)))),
        ).fetchall()
        for user_id, raw_payload, user_state in rows:
            if time.monotonic() - started >= max(30, time_budget_seconds):
                break
            try:
                versions = list_model_versions(str(user_id), db)
                evaluation = evaluate_retraining(raw_payload or {}, user_state or {}, versions)
                candidate_id = None
                if evaluation["status"] == "candidate_ready":
                    candidate_id = _save_candidate(str(user_id), evaluation, db)
                    result["trained"] += 1
                    if evaluation["promotion"]["promote"]:
                        result["activated"] += 1
                else:
                    result["skipped"] += 1
                _save_run(str(user_id), evaluation, db, candidate_id)
                db.commit()
                result["processed"] += 1
            except Exception as exc:
                db.rollback()
                result["processed"] += 1
                result["errors"] += 1
                error_evaluation = {
                    "status": "error",
                    "due": False,
                    "reasons": ["a kiértékelés technikai hiba miatt megszakadt"],
                    "message": f"Az automatikus kiértékelés sikertelen ({type(exc).__name__}).",
                }
                try:
                    _save_run(str(user_id), error_evaluation, db)
                    db.commit()
                except Exception:
                    db.rollback()
        return {**result, "status": "completed"}
    finally:
        if acquired:
            try:
                db.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s))",
                    ("hybrid-athlete-scheduled-retraining",),
                )
            except Exception:
                pass
        db.close()


def model_status(user_id: str) -> dict[str, Any]:
    """Return an artifact-free status view for the signed-in user."""
    db = connect()
    try:
        initialize_model_registry(db)
        versions = list_model_versions(user_id, db)
        active = next((item for item in versions if item["active"]), None)
        latest = versions[0] if versions else None
        run = db.execute(
            """
            SELECT checked_at, status, due, reasons, current_data_end, message
            FROM hybrid_retraining_runs WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()

        source = db.execute(
            """
            SELECT raw.payload, state.payload
            FROM hybrid_user_state raw
            LEFT JOIN hybrid_user_state state
              ON state.user_id = raw.user_id AND state.state_key = %s
            WHERE raw.user_id = %s AND raw.state_key = %s
            """,
            (USER_STATE_KEY, user_id, RAW_CACHE_KEY),
        ).fetchone()
        readiness = None
        if source:
            frame, activities = build_daily_frames(
                source[0] or {}, (source[1] or {}).get("feedback") or {}
            )
            readiness = recovery_model_data_readiness(
                frame, activities, (source[1] or {}).get("feedback") or {}
            )

        def public_version(value: dict[str, Any] | None) -> dict[str, Any] | None:
            if not value:
                return None
            public = {
                key: (item.isoformat() if isinstance(item, datetime) else item)
                for key, item in value.items()
                if key != "metrics"
            }
            metrics = value.get("metrics") if isinstance(value.get("metrics"), dict) else {}
            folds = metrics.get("folds") if isinstance(metrics.get("folds"), list) else []
            public["validation"] = {
                "improvementPct": metrics.get("improvement_pct"),
                "windowsWon": sum(
                    1
                    for fold in folds
                    if float(fold.get("model_mae", float("inf")))
                    < float(fold.get("baseline_mae", float("-inf")))
                ),
                "windowCount": len(folds),
            }
            return public

        return {
            "active": public_version(active),
            "latest": public_version(latest),
            "readiness": readiness,
            "schedule": {
                "nextCheckAt": next_scheduled_check(),
                "frequency": "daily",
            },
            "lastRun": None
            if not run
            else {
                "checkedAt": run[0].isoformat(),
                "status": run[1],
                "due": bool(run[2]),
                "reasons": run[3] if isinstance(run[3], list) else [],
                "dataEnd": str(run[4]) if run[4] else None,
                "message": run[5] or "",
            },
        }
    finally:
        db.close()
