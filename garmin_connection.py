"""Encrypted per-user Garmin Connect credentials.

Credentials and Garmin session tokens are decrypted only inside server-side sync calls
and are never returned to the browser. Sync steps reuse the stored tokens and fall back
to a password login only when Garmin rejects them.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from cloud_cache import SCHEMA_READY, connect


def _cipher() -> Fernet:
    key = os.getenv("GARMIN_CREDENTIALS_KEY", "").strip().encode()
    if not key:
        raise RuntimeError("Hiányzik a GARMIN_CREDENTIALS_KEY szerveroldali titkosítási kulcs.")
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("A GARMIN_CREDENTIALS_KEY formátuma érvénytelen.") from exc


def initialize_connections(db: Any) -> None:
    if "garmin_connections" in SCHEMA_READY:
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_garmin_connections (
            user_id UUID PRIMARY KEY REFERENCES hybrid_users(id) ON DELETE CASCADE,
            encrypted_credentials BYTEA NOT NULL,
            email_hint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("ALTER TABLE hybrid_garmin_connections ADD COLUMN IF NOT EXISTS encrypted_tokens BYTEA")
    db.commit()
    SCHEMA_READY.add("garmin_connections")


def _hint(email: str) -> str:
    local, _, domain = email.partition("@")
    visible = local[:2]
    return f"{visible}{'•' * max(3, len(local) - len(visible))}@{domain}"


def save_connection(user_id: str, email: str, password: str) -> dict[str, str]:
    email = str(email or "").strip().lower()[:254]
    if "@" not in email or not password:
        raise ValueError("Add meg a Garmin e-mail-címedet és jelszavadat.")
    payload = json.dumps({"email": email, "password": password}, separators=(",", ":")).encode()
    encrypted = _cipher().encrypt(payload)
    db = connect()
    try:
        initialize_connections(db)
        db.execute("""
            INSERT INTO hybrid_garmin_connections (user_id, encrypted_credentials, email_hint, status, updated_at)
            VALUES (%s, %s, %s, 'connected', NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                encrypted_credentials = EXCLUDED.encrypted_credentials,
                email_hint = EXCLUDED.email_hint,
                encrypted_tokens = NULL,
                status = 'connected', updated_at = NOW()
        """, (user_id, encrypted, _hint(email)))
        db.commit()
        return {"status": "connected", "email_hint": _hint(email), "updated_at": datetime.now(timezone.utc).isoformat()}
    finally:
        db.close()


def connection_status(user_id: str) -> dict[str, str]:
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute("SELECT status, email_hint, updated_at FROM hybrid_garmin_connections WHERE user_id = %s", (user_id,)).fetchone()
        return {"status": row[0], "email_hint": row[1], "updated_at": row[2].isoformat()} if row else {"status": "disconnected"}
    finally:
        db.close()


def load_credentials(user_id: str) -> tuple[str, str]:
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute("SELECT encrypted_credentials FROM hybrid_garmin_connections WHERE user_id = %s", (user_id,)).fetchone()
    finally:
        db.close()
    if not row:
        raise ValueError("Előbb csatlakoztasd a Garmin-fiókodat a Beállításokban.")
    try:
        payload = json.loads(_cipher().decrypt(bytes(row[0])))
        return payload["email"], payload["password"]
    except (InvalidToken, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("A Garmin-kapcsolat nem fejthető vissza. Csatlakoztasd újra a fiókot.") from exc


def load_tokens(user_id: str) -> str | None:
    """Return the decrypted Garmin session tokens, or None when a password login is needed."""
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute("SELECT encrypted_tokens FROM hybrid_garmin_connections WHERE user_id = %s", (user_id,)).fetchone()
    finally:
        db.close()
    if not row or row[0] is None:
        return None
    try:
        return _cipher().decrypt(bytes(row[0])).decode()
    except (InvalidToken, UnicodeDecodeError):
        return None


def save_tokens(user_id: str, tokens: str) -> None:
    db = connect()
    try:
        initialize_connections(db)
        db.execute(
            "UPDATE hybrid_garmin_connections SET encrypted_tokens = %s WHERE user_id = %s",
            (_cipher().encrypt(tokens.encode()), user_id),
        )
        db.commit()
    finally:
        db.close()


def delete_connection(user_id: str) -> None:
    db = connect()
    try:
        initialize_connections(db)
        db.execute("DELETE FROM hybrid_garmin_connections WHERE user_id = %s", (user_id,))
        db.commit()
    finally:
        db.close()
