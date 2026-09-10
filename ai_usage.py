"""Read-only per-user AI usage summary. Writes belong to the server chat handler."""
from __future__ import annotations

import os
import re
from typing import Any

from cloud_cache import connect


def daily_token_limit() -> int:
    value = os.getenv("HYBRID_AI_DAILY_TOKEN_LIMIT", "").strip()
    if re.fullmatch(r"[0-9]+", value):
        number = int(value)
        if 0 < number <= 9_007_199_254_740_991:
            return number
    return 50_000


def _initialize(db: Any) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_ai_generations (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            reserved_tokens INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd NUMERIC(12,8),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_ai_generations_user_day_idx ON hybrid_ai_generations(user_id, created_at DESC)")
    db.commit()


def usage_today(user_id: str) -> dict[str, Any]:
    db = connect()
    try:
        _initialize(db)
        row = db.execute("""
            SELECT COALESCE(SUM(COALESCE(total_tokens, reserved_tokens)), 0),
                   CASE WHEN COUNT(*) > 0 AND COUNT(estimated_cost_usd) = COUNT(*)
                        THEN SUM(estimated_cost_usd) ELSE NULL END,
                   COUNT(*),
                   (NOW() AT TIME ZONE 'Europe/Budapest')::date::text,
                   COALESCE(SUM(reserved_tokens) FILTER (WHERE total_tokens IS NULL), 0)
            FROM hybrid_ai_generations
            WHERE user_id = %s AND created_at >= date_trunc('day', NOW() AT TIME ZONE 'Europe/Budapest') AT TIME ZONE 'Europe/Budapest'
        """, (user_id,)).fetchone()
        return {
            "usedTokens": int(row[0]), "limitTokens": daily_token_limit(),
            "estimatedCostUsd": float(row[1]) if row[1] is not None else None,
            "generations": int(row[2]), "date": row[3], "reservedTokens": int(row[4]),
        }
    finally:
        db.close()
