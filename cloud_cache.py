"""Durable JSON state shared by Vercel Functions through Neon Postgres."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg


def _database_url() -> str:
    value = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not value:
        raise RuntimeError("A tartós adattár nincs konfigurálva.")
    return value


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(_database_url(), connect_timeout=15)


def initialize(connection: psycopg.Connection[Any]) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS hybrid_app_state (
            state_key TEXT PRIMARY KEY,
            payload JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.commit()


def load_json(state_key: str, connection: psycopg.Connection[Any] | None = None) -> dict[str, Any] | None:
    owns_connection = connection is None
    db = connection or connect()
    try:
        initialize(db)
        row = db.execute(
            "SELECT payload FROM hybrid_app_state WHERE state_key = %s", (state_key,)
        ).fetchone()
        return row[0] if row and isinstance(row[0], dict) else None
    finally:
        if owns_connection:
            db.close()


def save_json(state_key: str, payload: dict[str, Any], connection: psycopg.Connection[Any] | None = None) -> None:
    owns_connection = connection is None
    db = connection or connect()
    try:
        initialize(db)
        db.execute(
            """
            INSERT INTO hybrid_app_state (state_key, payload, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (state_key) DO UPDATE
            SET payload = EXCLUDED.payload, updated_at = NOW()
            """,
            (state_key, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
        )
        db.commit()
    finally:
        if owns_connection:
            db.close()


@contextmanager
def sync_lock() -> Iterator[psycopg.Connection[Any] | None]:
    """Allow only one expensive Garmin refresh at a time."""
    db = connect()
    try:
        initialize(db)
        acquired = db.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ("hybrid-athlete-garmin-sync",)
        ).fetchone()[0]
        yield db if acquired else None
    finally:
        try:
            db.execute("SELECT pg_advisory_unlock(hashtext(%s))", ("hybrid-athlete-garmin-sync",))
        except Exception:
            pass
        db.close()
