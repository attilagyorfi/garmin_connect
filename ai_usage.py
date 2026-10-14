"""Durable per-user AI usage ledger with atomic daily limits.

Every Claude call is reserved before it is sent and settled with the real token usage afterwards.
The reservation runs under a per-user transaction lock, so parallel requests cannot overrun the
daily question or token cap (a read-modify-write JSON counter could). Days follow Europe/Budapest.

A global monthly budget sits above the per-user limits: at 80% of it the admins get one e-mail, at 100% every new
call is refused until the month ends (the admins get a second e-mail). The budget check runs under a global lock,
so parallel requests cannot overrun it either.
"""
from __future__ import annotations

import os
import sys
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
_MONTH_START = "date_trunc('month', NOW() AT TIME ZONE 'Europe/Budapest') AT TIME ZONE 'Europe/Budapest'"

DEFAULT_MONTHLY_BUDGET_USD = 25.0  # all users together; AI_MONTHLY_BUDGET_USD overrides it
ALERT_SHARE = 0.8
# An in-flight reservation counts at the input price until its real cost is known (a typical answer costs less).
RESERVED_USD_PER_TOKEN = PRICE_PER_MTOK["input"] / 1_000_000
PAUSED_MESSAGE = "Az Edzőtárs ebben a hónapban elérte a szolgáltatási keretét, ezért a hónap végéig szünetel. Az alkalmazás többi része változatlanul működik."


def monthly_budget_usd() -> float:
    try:
        value = float(os.getenv("AI_MONTHLY_BUDGET_USD", "") or DEFAULT_MONTHLY_BUDGET_USD)
    except ValueError:
        return DEFAULT_MONTHLY_BUDGET_USD
    return value if value > 0 else DEFAULT_MONTHLY_BUDGET_USD


class UsageLimitError(ValueError):
    """The user's daily AI allowance is used up."""


class BudgetExceededError(UsageLimitError):
    """The service-wide monthly AI budget is used up."""


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
    # Production already has this table from the retired codex build (no kind/cache columns, a required
    # prompt_hash). CREATE TABLE IF NOT EXISTS keeps that shape, so bring it up to date idempotently.
    db.execute("ALTER TABLE hybrid_ai_generations ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'answer'")
    db.execute("ALTER TABLE hybrid_ai_generations ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER")
    db.execute("ALTER TABLE hybrid_ai_generations ADD COLUMN IF NOT EXISTS cache_write_tokens INTEGER")
    legacy_prompt_hash = db.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'hybrid_ai_generations'
          AND column_name = 'prompt_hash' AND is_nullable = 'NO'
    """).fetchone()
    if legacy_prompt_hash:
        db.execute("ALTER TABLE hybrid_ai_generations ALTER COLUMN prompt_hash DROP NOT NULL")
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_ai_generations_user_day_idx ON hybrid_ai_generations(user_id, created_at DESC)")
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_ai_generations_created_idx ON hybrid_ai_generations(created_at)")
    # One row per month and alert level, so each alert e-mail goes out once.
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_ai_budget_alerts (
            month TEXT NOT NULL,
            level INTEGER NOT NULL,
            spent_usd NUMERIC(12,4) NOT NULL,
            budget_usd NUMERIC(12,4) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (month, level)
        )
    """)
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


def _month_spend(db: Any) -> float:
    """This month's estimated spend: settled calls at their cost, in-flight reservations at the input price."""
    row = db.execute(f"""
        SELECT COALESCE(SUM(estimated_cost_usd) FILTER (WHERE status = 'completed'), 0),
               COALESCE(SUM(reserved_tokens) FILTER (WHERE status = 'reserved'), 0)
        FROM hybrid_ai_generations WHERE created_at >= {_MONTH_START}
    """).fetchone()
    return float(row[0]) + int(row[1]) * RESERVED_USD_PER_TOKEN


def _current_month(db: Any) -> str:
    return db.execute("SELECT to_char(NOW() AT TIME ZONE 'Europe/Budapest', 'YYYY-MM')").fetchone()[0]


def _claim_alert(db: Any, level: int, spent: float, budget: float) -> str | None:
    """Record the alert for this month; returns the month only the first time (that caller sends the e-mail)."""
    month = _current_month(db)
    row = db.execute("""
        INSERT INTO hybrid_ai_budget_alerts (month, level, spent_usd, budget_usd) VALUES (%s, %s, %s, %s)
        ON CONFLICT (month, level) DO NOTHING RETURNING month
    """, (month, level, round(spent, 4), round(budget, 4))).fetchone()
    return row[0] if row else None


def _admin_recipients(db: Any) -> list[str]:
    rows = db.execute("SELECT email FROM hybrid_users WHERE role = 'admin' AND access_status = 'active' ORDER BY email").fetchall()
    return [row[0] for row in rows]


def _send_alert(recipients: list[str], level: int, month: str, spent: float, budget: float) -> None:
    """Best effort: a failed e-mail is logged, the limit itself still applies."""
    from auth_email import EmailError, budget_alert_message, send_email

    subject, text, markup = budget_alert_message(level, month, spent, budget)
    for recipient in recipients:
        try:
            send_email(recipient, subject, text, markup)
        except EmailError as exc:
            sys.stderr.write(f"AI budget alert ({level}%) not sent: {exc}\n")


def _check_alerts(db: Any) -> tuple[int, str, float, float, list[str]] | None:
    """Claim the highest newly crossed alert level inside the caller's transaction; the e-mail is sent after commit."""
    budget, spent = monthly_budget_usd(), _month_spend(db)
    level = 100 if spent >= budget else 80 if spent >= budget * ALERT_SHARE else None
    if level is None:
        return None
    month = _claim_alert(db, level, spent, budget)
    if level == 100:
        _claim_alert(db, 80, spent, budget)  # a jump past 80% straight to 100% needs only one e-mail
    return (level, month, spent, budget, _admin_recipients(db)) if month else None


def reserve(user_id: str, kind: str, model: str, tokens: int = RESERVATION_TOKENS) -> str:
    """Atomically check the monthly budget and today's allowance and hold them for one call.

    Raises BudgetExceededError when the service-wide monthly budget is used up, UsageLimitError when the user's
    daily allowance is.
    """
    db = connect()
    alert = None
    try:
        _initialize(db)
        # Global lock first (always the same order), then the per-user one.
        db.execute("SELECT pg_advisory_xact_lock(hashtext('ai-usage:budget'))")
        if _month_spend(db) + int(tokens) * RESERVED_USD_PER_TOKEN > monthly_budget_usd():
            alert = _check_alerts(db)
            db.commit()
            raise BudgetExceededError(PAUSED_MESSAGE)
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
        if alert:
            _send_alert(alert[4], *alert[:4])


def usage_numbers(response_usage: Any) -> dict[str, int]:
    get = lambda name: int(getattr(response_usage, name, 0) or 0)  # noqa: E731
    return {"input": get("input_tokens"), "output": get("output_tokens"),
            "cache_read": get("cache_read_input_tokens"), "cache_write": get("cache_creation_input_tokens")}


def estimated_cost(numbers: dict[str, int]) -> float:
    return sum(numbers[key] * PRICE_PER_MTOK[key] for key in PRICE_PER_MTOK) / 1_000_000


def settle(generation_id: str, numbers: dict[str, int]) -> None:
    db = connect()
    alert = None
    try:
        _initialize(db)
        db.execute("""
            UPDATE hybrid_ai_generations
            SET status = 'completed', input_tokens = %s, output_tokens = %s, cache_read_tokens = %s,
                cache_write_tokens = %s, total_tokens = %s, estimated_cost_usd = %s, completed_at = NOW()
            WHERE id = %s
        """, (numbers["input"], numbers["output"], numbers["cache_read"], numbers["cache_write"],
              sum(numbers.values()), estimated_cost(numbers), generation_id))
        alert = _check_alerts(db)
        db.commit()
    finally:
        db.close()
    if alert:
        _send_alert(alert[4], *alert[:4])


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
        paused = _month_spend(db) >= monthly_budget_usd()
    finally:
        db.close()
    return {
        "servicePaused": paused,
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
        spent, budget = _month_spend(db), monthly_budget_usd()
    finally:
        db.close()
    month = {"spentUsd": round(spent, 2), "budgetUsd": round(budget, 2), "usedPct": min(100, round(spent / budget * 100)),
             "alertPct": round(ALERT_SHARE * 100), "paused": spent >= budget}
    daily = [{"date": row[0], "questions": int(row[1]), "users": int(row[2]), "tokens": int(row[3]), "estimatedCostUsd": round(float(row[4]), 4)} for row in rows]
    return {"days": days, "daily": daily, "month": month, "questions": sum(item["questions"] for item in daily),
            "tokens": sum(item["tokens"] for item in daily), "estimatedCostUsd": round(sum(item["estimatedCostUsd"] for item in daily), 4)}
