"""Audited, user-approved actions proposed by the AI assistant."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cloud_cache import connect
from user_state import apply_patch, load_state, validate_plan


ACTION_TYPES = {"upsert_plan", "delete_plan"}


def _initialize(db: Any) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_assistant_actions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            action_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            summary TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            before_payload JSONB,
            after_payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            decided_at TIMESTAMPTZ
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_assistant_actions_user_idx ON hybrid_assistant_actions(user_id, created_at DESC)")
    db.commit()


def _text(value: Any, maximum: int) -> str:
    return str(value or "").strip()[:maximum]


def _normalize(action: Any, user_id: str) -> tuple[str, dict[str, Any], str, str, dict[str, Any] | None]:
    if not isinstance(action, dict) or action.get("action") not in ACTION_TYPES:
        raise ValueError("Az asszisztens javaslata nem támogatott műveletet tartalmaz.")
    action_type = action["action"]
    summary = _text(action.get("summary"), 300)
    reason = _text(action.get("reason"), 1000)
    state = load_state(user_id)
    if action_type == "upsert_plan":
        plan = validate_plan(action.get("plan"))
        existing = next((item for item in state["plans"] if item.get("id") == plan["id"]), None)
        if action.get("plan", {}).get("id") and not existing:
            raise ValueError("A módosítandó edzésterv már nem található.")
        payload = {"plan": plan}
        summary = summary or f"{plan['title']} mentése {plan['date']} napra"
    else:
        plan_id = _text(action.get("targetPlanId"), 80)
        existing = next((item for item in state["plans"] if item.get("id") == plan_id), None)
        if not existing:
            raise ValueError("A törlendő edzésterv már nem található.")
        payload = {"deletePlan": plan_id}
        summary = summary or f"{existing['title']} törlése"
    return action_type, payload, summary, reason or "A felhasználó kérésére készített AI-javaslat.", existing


def create_action(user_id: str, action: Any) -> dict[str, Any]:
    action_type, payload, summary, reason, before = _normalize(action, user_id)
    action_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    db = connect()
    try:
        _initialize(db)
        db.execute("""
            INSERT INTO hybrid_assistant_actions
              (id, user_id, action_type, payload, summary, reason, before_payload, expires_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
        """, (action_id, user_id, action_type, json.dumps(payload, ensure_ascii=False), summary, reason, json.dumps(before, ensure_ascii=False), expires_at))
        db.commit()
    finally:
        db.close()
    return {"id": action_id, "action": action_type, "payload": payload, "summary": summary, "reason": reason, "status": "pending", "expiresAt": expires_at.isoformat()}


def decide_action(user_id: str, action_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ValueError("Érvénytelen döntés.")
    try:
        uuid.UUID(action_id)
    except (ValueError, TypeError) as exc:
        raise ValueError("Érvénytelen javaslatazonosító.") from exc
    db = connect()
    try:
        _initialize(db)
        row = db.execute("""
            SELECT action_type, payload, summary, reason, status, expires_at, before_payload
            FROM hybrid_assistant_actions WHERE id = %s AND user_id = %s
        """, (action_id, user_id)).fetchone()
        if not row:
            raise ValueError("A javaslat nem található.")
        if row[4] != "pending":
            raise ValueError("Erről a javaslatról már döntöttél.")
        if row[5] <= datetime.now(timezone.utc):
            db.execute("UPDATE hybrid_assistant_actions SET status = 'expired', decided_at = NOW() WHERE id = %s", (action_id,))
            db.commit()
            raise ValueError("A javaslat lejárt. Kérj új előnézetet az asszisztenstől.")
        if decision == "reject":
            db.execute("UPDATE hybrid_assistant_actions SET status = 'rejected', decided_at = NOW() WHERE id = %s AND status = 'pending'", (action_id,))
            db.commit()
            return {"id": action_id, "status": "rejected"}
        current = load_state(user_id)
        target_id = row[1].get("deletePlan") or row[1].get("plan", {}).get("id")
        current_plan = next((item for item in current["plans"] if item.get("id") == target_id), None)
        if current_plan != row[6]:
            raise ValueError("A terv az előnézet óta megváltozott. Kérj új javaslatot, hogy ne írjunk felül frissebb módosítást.")
        claimed = db.execute("UPDATE hybrid_assistant_actions SET status = 'applying' WHERE id = %s AND user_id = %s AND status = 'pending' RETURNING id", (action_id, user_id)).fetchone()
        db.commit()
        if not claimed:
            raise ValueError("Erről a javaslatról már döntöttél.")
        try:
            after = apply_patch(row[1], user_id)
        except Exception:
            db.execute("UPDATE hybrid_assistant_actions SET status = 'pending' WHERE id = %s AND status = 'applying'", (action_id,))
            db.commit()
            raise
        after_plan = next((item for item in after["plans"] if item.get("id") == target_id), None)
        db.execute("""
            UPDATE hybrid_assistant_actions
            SET status = 'applied', after_payload = %s::jsonb, decided_at = NOW()
            WHERE id = %s AND user_id = %s AND status = 'applying'
        """, (json.dumps(after_plan, ensure_ascii=False), action_id, user_id))
        db.commit()
        return {"id": action_id, "status": "applied", "state": after}
    finally:
        db.close()
