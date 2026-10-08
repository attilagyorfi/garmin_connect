"""Plan changes proposed by the AI assistant; nothing is written until the user approves.

A proposal is stored as a pending, audited action (24 h validity). Approval re-checks that the
targeted plan is still exactly what was previewed, so an older suggestion never overwrites a newer edit.
The model refers to existing plans only by short per-request handles (T1, T2, …), never by stored IDs.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from cloud_cache import SCHEMA_READY, connect
from user_state import PLAN_INTENSITIES, PLAN_TYPES, apply_patch, load_state, validate_plan

ACTION_TYPES = {"upsert_plan", "delete_plan"}
VALIDITY = timedelta(hours=24)
UPCOMING_DAYS = 21
MAX_PLANS_IN_CONTEXT = 30

# Strict tool schema: every field is required; fields that do not apply are null.
PLAN_TOOL = {
    "name": "propose_plan_change",
    "description": (
        "Edzésterv-módosítás javaslata a sportoló Naptárába. Csak akkor használd, ha a sportoló kifejezetten kéri, "
        "hogy tervezz, módosíts, mozgass vagy törölj egy edzést. A javaslat NEM kerül automatikusan a tervbe: "
        "a sportoló jóváhagyja vagy elutasítja. Meglévő tervre a TERVEK listában szereplő jellel (pl. T2) hivatkozz; "
        "új edzésnél a target legyen null. Törlésnél (delete_plan) az edzés mezői legyenek null."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "target", "date", "type", "title", "duration", "intensity", "rpe", "purpose", "summary", "reason"],
        "properties": {
            "action": {"type": "string", "enum": sorted(ACTION_TYPES)},
            "target": {"type": ["string", "null"], "description": "Meglévő terv jele (pl. T2), új edzésnél null"},
            "date": {"type": ["string", "null"], "description": "ÉÉÉÉ-HH-NN"},
            "type": {"type": ["string", "null"], "description": "Egyike: " + ", ".join(sorted(PLAN_TYPES))},
            "title": {"type": ["string", "null"]},
            "duration": {"type": ["integer", "null"], "description": "perc"},
            "intensity": {"type": ["string", "null"], "description": "Egyike: " + ", ".join(sorted(PLAN_INTENSITIES))},
            "rpe": {"type": ["integer", "null"], "description": "1–10"},
            "purpose": {"type": ["string", "null"]},
            "summary": {"type": "string", "description": "Egy rövid mondat: mi változik"},
            "reason": {"type": "string", "description": "Rövid indoklás a sportoló adataiból"},
        },
    },
}


def _initialize(db: Any) -> None:
    if "assistant_actions" in SCHEMA_READY:
        return
    # Concurrent first requests would race on CREATE TABLE IF NOT EXISTS; serialize the DDL.
    db.execute("SELECT pg_advisory_xact_lock(hashtext('schema:hybrid_assistant_actions'))")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_assistant_actions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
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
    SCHEMA_READY.add("assistant_actions")


def plan_handles(plans: list[dict[str, Any]], today: date | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Upcoming plans for the model context, keyed by short handles instead of stored IDs."""
    start = (today or date.today()).isoformat()
    end = ((today or date.today()) + timedelta(days=UPCOMING_DAYS)).isoformat()
    upcoming = sorted((plan for plan in plans if start <= str(plan.get("date", "")) <= end), key=lambda plan: (plan["date"], plan["id"]))[:MAX_PLANS_IN_CONTEXT]
    handles, listing = {}, []
    for index, plan in enumerate(upcoming, start=1):
        handle = f"T{index}"
        handles[handle] = plan["id"]
        listing.append({"jel": handle, "dátum": plan["date"], "típus": plan.get("type"), "cím": plan.get("title"),
                        "perc": plan.get("duration"), "intenzitás": plan.get("intensity"), "rpe": plan.get("rpe")})
    return listing, handles


def _text(value: Any, maximum: int) -> str:
    return str(value or "").strip()[:maximum]


def _normalize(proposal: Any, user_id: str, handles: dict[str, str]) -> tuple[str, dict[str, Any], str, str, dict[str, Any] | None]:
    if not isinstance(proposal, dict) or proposal.get("action") not in ACTION_TYPES:
        raise ValueError("Az edzőtárs javaslata nem támogatott műveletet tartalmaz.")
    state = load_state(user_id)
    target = _text(proposal.get("target"), 10)
    plan_id = handles.get(target) if target else None
    if target and not plan_id:
        raise ValueError("A javaslat ismeretlen edzéstervre hivatkozik.")
    existing = next((item for item in state["plans"] if item.get("id") == plan_id), None) if plan_id else None
    if plan_id and not existing:
        raise ValueError("A módosítandó edzésterv már nem található.")
    summary, reason = _text(proposal.get("summary"), 300), _text(proposal.get("reason"), 1000)
    if proposal["action"] == "delete_plan":
        if not existing:
            raise ValueError("Törlésre csak meglévő edzésterv javasolható.")
        return "delete_plan", {"deletePlan": existing["id"]}, summary or f"{existing['title']} törlése", reason, existing
    fields = {key: proposal.get(key) for key in ("date", "type", "title", "duration", "intensity", "rpe", "purpose") if proposal.get(key) is not None}
    base = {key: value for key, value in (existing or {}).items() if key not in {"updatedAt"}}
    new_id = existing["id"] if existing else f"ai-{uuid.uuid4().hex[:12]}"
    plan = validate_plan({**base, **fields, "note": _text((existing or {}).get("note"), 2000) or "Az edzőtárs javaslata alapján"}, new_id)
    plan.pop("updatedAt", None)
    return "upsert_plan", {"plan": plan}, summary or f"{plan['title']} · {plan['date']}", reason, existing


def _public(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"] or {}
    return {"id": row["id"], "action": row["action_type"], "summary": row["summary"], "reason": row["reason"], "status": row["status"],
            "plan": payload.get("plan"), "before": row.get("before"), "expiresAt": row["expires_at"]}


def create_actions(user_id: str, proposals: list[Any], handles: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Store valid proposals as pending actions; return them plus readable rejection reasons for the rest."""
    created, problems = [], []
    db = None
    try:
        for proposal in proposals[:5]:
            try:
                action_type, payload, summary, reason, before = _normalize(proposal, user_id, handles)
            except (ValueError, TypeError) as exc:
                problems.append(str(exc))
                continue
            if db is None:
                db = connect()
                _initialize(db)
            action_id, expires_at = str(uuid.uuid4()), datetime.now(timezone.utc) + VALIDITY
            db.execute("""
                INSERT INTO hybrid_assistant_actions (id, user_id, action_type, payload, summary, reason, before_payload, expires_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
            """, (action_id, user_id, action_type, json.dumps(payload, ensure_ascii=False), summary, reason,
                  json.dumps(before, ensure_ascii=False), expires_at))
            created.append(_public({"id": action_id, "action_type": action_type, "payload": payload, "summary": summary, "reason": reason,
                                    "status": "pending", "before": before, "expires_at": expires_at.isoformat()}))
        if db is not None:
            db.commit()
    finally:
        if db is not None:
            db.close()
    return created, problems


def list_actions(user_id: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    """Current status of the given actions (expired pending ones are reported as expired)."""
    valid = [value for value in ids if _is_uuid(value)]
    if not valid:
        return {}
    db = connect()
    try:
        _initialize(db)
        rows = db.execute("""
            SELECT id::text, action_type, payload, summary, reason,
                   CASE WHEN status = 'pending' AND expires_at <= NOW() THEN 'expired' ELSE status END,
                   before_payload, expires_at
            FROM hybrid_assistant_actions WHERE user_id = %s AND id::text = ANY(%s)
        """, (user_id, valid)).fetchall()
    finally:
        db.close()
    return {row[0]: _public({"id": row[0], "action_type": row[1], "payload": row[2], "summary": row[3], "reason": row[4], "status": row[5],
                             "before": row[6], "expires_at": row[7].isoformat()}) for row in rows}


def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def decide_action(user_id: str, action_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ValueError("Érvénytelen döntés.")
    if not _is_uuid(action_id):
        raise ValueError("Érvénytelen javaslatazonosító.")
    db = connect()
    try:
        _initialize(db)
        row = db.execute("""
            SELECT payload, status, expires_at, before_payload FROM hybrid_assistant_actions WHERE id = %s AND user_id = %s
        """, (action_id, user_id)).fetchone()
        if not row:
            raise ValueError("A javaslat nem található.")
        payload, status, expires_at, before = row
        if status != "pending":
            raise ValueError("Erről a javaslatról már döntöttél.")
        if expires_at <= datetime.now(timezone.utc):
            db.execute("UPDATE hybrid_assistant_actions SET status = 'expired', decided_at = NOW() WHERE id = %s", (action_id,))
            db.commit()
            raise ValueError("A javaslat lejárt. Kérj új javaslatot az edzőtárstól.")
        if decision == "reject":
            db.execute("UPDATE hybrid_assistant_actions SET status = 'rejected', decided_at = NOW() WHERE id = %s AND status = 'pending'", (action_id,))
            db.commit()
            return {"id": action_id, "status": "rejected"}
        target_id = payload.get("deletePlan") or (payload.get("plan") or {}).get("id")
        current = next((item for item in load_state(user_id)["plans"] if item.get("id") == target_id), None)
        if current != before:
            raise ValueError("A terv a javaslat óta megváltozott. Kérj új javaslatot, hogy ne írjunk felül frissebb módosítást.")
        claimed = db.execute("UPDATE hybrid_assistant_actions SET status = 'applying' WHERE id = %s AND user_id = %s AND status = 'pending' RETURNING id",
                             (action_id, user_id)).fetchone()
        db.commit()
        if not claimed:
            raise ValueError("Erről a javaslatról már döntöttél.")
        try:
            after = apply_patch(payload, user_id)
        except Exception:
            db.execute("UPDATE hybrid_assistant_actions SET status = 'pending' WHERE id = %s AND status = 'applying'", (action_id,))
            db.commit()
            raise
        after_plan = next((item for item in after["plans"] if item.get("id") == target_id), None)
        db.execute("UPDATE hybrid_assistant_actions SET status = 'applied', after_payload = %s::jsonb, decided_at = NOW() WHERE id = %s AND status = 'applying'",
                   (json.dumps(after_plan, ensure_ascii=False), action_id))
        db.commit()
        return {"id": action_id, "status": "applied"}
    finally:
        db.close()
