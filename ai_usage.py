"""Durable per-user AI usage ledger with atomic daily limits.

Every Claude call is reserved before it is sent and settled with the real token usage afterwards.
The reservation runs under a per-user transaction lock, so parallel requests cannot overrun the
daily question or token cap (a read-modify-write JSON counter could). Days follow Europe/Budapest.
"""
from __future__ import annotations

import uuid
from typing import Any

from cloud_cache import SCHEMA_READY, connect

DAILY_QUESTION_LIMIT = 15
DAILY_TOKEN_LIMIT = 150_000  # input + output tokens per user per day, a cost ceiling beside the question cap
# Held for an answer until its real usage is known: the per-question share of the daily token budget,
# so that the question cap, not the in-flight reservations, is what limits parallel questions.
RESERVATION_TOKENS = DAILY_TOKEN_LIMIT // DAILY_QUESTION_LIMIT

# Estimated USD per million tokens for claude-sonnet-5-5 (first-party API list price, 2026-09).
# Only used for the operator's cost overview; the limits above are token based.
PRICE_PER_MTOK = {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50}

_TODAY = "date_trunc('day', NOW() AT TIME ZONE 'Europe/Budapest') AT TIME ZONE 'Europe/Budapest'"


class UsageLimitError(ValueError):
    """The user's daily AI allowance is used up."""


def _initialize(db: Any) -> None:
    if "ai_generations" in SCHEMA_READY:
        return
    # Concurrent first requests would race on CREATE TABLE IF NOT EXISTS; serialize the DDL.
    db.execute("SELECT pg_advisory_xact_lock(hashtext('schema:hybrid_ai_generations'))")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_ai_generations (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            kind TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            reserved_tokens INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd NUMERIC(12,8),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_ai_generations_user_day_idx ON hybrid_ai_generations(user_id, created_at DESC)")
    db.commit()
    SCHEMA_READY.add("ai_generations")


def _today_totals(db: Any, user_id: str) -> tuple[int, int]:
    row = db.execute(f"""
        SELECT COUNT(*) FILTER (WHERE kind = 'answer'),
               COALESCE(SUM(COALESCE(total_tokens, reserved_tokens)), 0)
        FROM hybrid_ai_generations
        WHERE user_id = %s AND status <> 'failed' AND created_at >= {_TODAY}
    """, (user_id,)).fetchone()
    return int(row[0]), int(row[1])


def reserve(user_id: str, kind: str, model: str, tokens: int = RESERVATION_TOKENS) -> str:
    """Atomically check today's allowance and hold it for one call; raises UsageLimitError when used up."""
    db = connect()
    try:
        _initialize(db)
        db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"ai-usage:{user_id}",))
        questions, used = _today_totals(db, user_id)
        if (kind == "answer" and questions >= DAILY_QUESTION_LIMIT) or used >= DAILY_TOKEN_LIMIT:
            db.rollback()
            raise UsageLimitError(f"Elérted a mai {DAILY_QUESTION_LIMIT} kérdéses keretet. Holnap reggel újra kérdezhetsz.")
        generation_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO hybrid_ai_generations (id, user_id, kind, model, status, reserved_tokens) VALUES (%s, %s, %s, %s, 'reserved', %s)",
            (generation_id, user_id, kind, model, int(tokens)),
        )
        db.commit()
        return generation_id
    finally:
        db.close()


def usage_numbers(response_usage: Any) -> dict[str, int]:
    get = lambda name: int(getattr(response_usage, name, 0) or 0)  # noqa: E731
    return {"input": get("input_tokens"), "output": get("output_tokens"),
            "cache_read": get("cache_read_input_tokens"), "cache_write": get("cache_creation_input_tokens")}


def estimated_cost(numbers: dict[str, int]) -> float:
    return sum(numbers[key] * PRICE_PER_MTOK[key] for key in PRICE_PER_MTOK) / 1_000_000


def settle(generation_id: str, numbers: dict[str, int]) -> None:
    db = connect()
    try:
        _initialize(db)
        db.execute("""
            UPDATE hybrid_ai_generations
            SET status = 'completed', input_tokens = %s, output_tokens = %s, cache_read_tokens = %s,
                cache_write_tokens = %s, total_tokens = %s, estimated_cost_usd = %s, completed_at = NOW()
            WHERE id = %s
        """, (numbers["input"], numbers["output"], numbers["cache_read"], numbers["cache_write"],
              sum(numbers.values()), estimated_cost(numbers), generation_id))
        db.commit()
    finally:
        db.close()


def release(generation_id: str) -> None:
    """A call that failed before producing output does not count against the allowance."""
    db = connect()
    try:
        _initialize(db)
        db.execute("UPDATE hybrid_ai_generations SET status = 'failed', completed_at = NOW() WHERE id = %s AND status = 'reserved'", (generation_id,))
        db.commit()
    finally:
        db.close()


def usage_today(user_id: str) -> dict[str, Any]:
    db = connect()
    try:
        _initialize(db)
        questions, tokens = _today_totals(db, user_id)
    finally:
        db.close()
    return {
        "questions": questions, "limit": DAILY_QUESTION_LIMIT, "remaining": max(0, DAILY_QUESTION_LIMIT - questions),
        "tokens": tokens, "tokenLimit": DAILY_TOKEN_LIMIT, "tokenBudgetLeft": tokens < DAILY_TOKEN_LIMIT,
        "tokenUsedPct": min(100, round(tokens / DAILY_TOKEN_LIMIT * 100)),
    }


def admin_summary(days: int = 30) -> dict[str, Any]:
    """Aggregated operator view (no per-user identities): daily calls, users, tokens and estimated cost."""
    db = connect()
    try:
        _initialize(db)
        rows = db.execute("""
            SELECT (created_at AT TIME ZONE 'Europe/Budapest')::date::text AS day,
                   COUNT(*) FILTER (WHERE kind = 'answer'), COUNT(DISTINCT user_id),
                   COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost_usd), 0)
            FROM hybrid_ai_generations
            WHERE status = 'completed' AND created_at >= NOW() - (%s || ' days')::interval
            GROUP BY day ORDER BY day DESC
        """, (max(1, min(365, int(days))),)).fetchall()
    finally:
        db.close()
    daily = [{"date": row[0], "questions": int(row[1]), "users": int(row[2]), "tokens": int(row[3]), "estimatedCostUsd": round(float(row[4]), 4)} for row in rows]
    return {"days": days, "daily": daily, "questions": sum(item["questions"] for item in daily),
            "tokens": sum(item["tokens"] for item in daily), "estimatedCostUsd": round(sum(item["estimatedCostUsd"] for item in daily), 4)}
