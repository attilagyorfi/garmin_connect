"""Encrypted, per-user Garmin Connect token storage.

The Garmin password is used only while establishing a connection. Successful
authentication is persisted as an encrypted refresh-token bundle.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from cloud_cache import connect


def _cipher() -> Fernet:
    key = os.getenv("GARMIN_CREDENTIALS_KEY", "").strip().encode()
    if not key:
        raise RuntimeError("Hiányzik a GARMIN_CREDENTIALS_KEY szerveroldali titkosítási kulcs.")
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("A GARMIN_CREDENTIALS_KEY formátuma érvénytelen.") from exc


def initialize_connections(db: Any) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_garmin_connections (
            user_id UUID PRIMARY KEY REFERENCES hybrid_users(id) ON DELETE CASCADE,
            encrypted_credentials BYTEA,
            encrypted_tokenstore BYTEA,
            encrypted_mfa_state BYTEA,
            mfa_expires_at TIMESTAMPTZ,
            mfa_attempts INTEGER NOT NULL DEFAULT 0,
            email_hint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("ALTER TABLE hybrid_garmin_connections ALTER COLUMN encrypted_credentials DROP NOT NULL")
    db.execute("ALTER TABLE hybrid_garmin_connections ADD COLUMN IF NOT EXISTS encrypted_tokenstore BYTEA")
    db.execute("ALTER TABLE hybrid_garmin_connections ADD COLUMN IF NOT EXISTS encrypted_mfa_state BYTEA")
    db.execute("ALTER TABLE hybrid_garmin_connections ADD COLUMN IF NOT EXISTS mfa_expires_at TIMESTAMPTZ")
    db.execute("ALTER TABLE hybrid_garmin_connections ADD COLUMN IF NOT EXISTS mfa_attempts INTEGER NOT NULL DEFAULT 0")
    db.commit()


def _hint(email: str) -> str:
    local, _, domain = email.partition("@")
    visible = local[:2]
    return f"{visible}{'•' * max(3, len(local) - len(visible))}@{domain}"


def save_token_connection(user_id: str, email: str, tokenstore: str) -> dict[str, str]:
    email = str(email or "").strip().lower()[:254]
    if "@" not in email or not tokenstore:
        raise ValueError("A Garmin-kapcsolat adatai hiányosak.")
    encrypted = _cipher().encrypt(tokenstore.encode("utf-8"))
    db = connect()
    try:
        initialize_connections(db)
        db.execute("""
            INSERT INTO hybrid_garmin_connections
                (user_id, encrypted_credentials, encrypted_tokenstore, email_hint, status, updated_at)
            VALUES (%s, NULL, %s, %s, 'connected', NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                encrypted_credentials = NULL,
                encrypted_tokenstore = EXCLUDED.encrypted_tokenstore,
                encrypted_mfa_state = NULL, mfa_expires_at = NULL, mfa_attempts = 0,
                email_hint = EXCLUDED.email_hint,
                status = 'connected', updated_at = NOW()
        """, (user_id, encrypted, _hint(email)))
        db.commit()
        return {
            "status": "connected", "email_hint": _hint(email),
            "auth_method": "token", "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


def connection_status(user_id: str) -> dict[str, str]:
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute(
            "SELECT status, email_hint, updated_at, encrypted_tokenstore IS NOT NULL "
            "FROM hybrid_garmin_connections WHERE user_id = %s", (user_id,),
        ).fetchone()
        if not row:
            return {"status": "disconnected"}
        status = row[0] if row[0] == "mfa_required" or row[3] else "reauth_required"
        return {
            "status": status, "email_hint": row[1],
            "auth_method": "token" if row[3] else "legacy",
            "updated_at": row[2].isoformat(),
        }
    finally:
        db.close()


def load_tokenstore(user_id: str) -> str:
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute(
            "SELECT encrypted_tokenstore FROM hybrid_garmin_connections WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    finally:
        db.close()
    if not row or not row[0]:
        raise ValueError("A Garmin-fiókot újra kell csatlakoztatni a Beállításokban.")
    try:
        return _cipher().decrypt(bytes(row[0])).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, TypeError) as exc:
        raise RuntimeError("A Garmin-munkamenet nem fejthető vissza. Csatlakoztasd újra a fiókot.") from exc


def refresh_tokenstore(user_id: str, tokenstore: str) -> None:
    encrypted = _cipher().encrypt(tokenstore.encode("utf-8"))
    db = connect()
    try:
        initialize_connections(db)
        db.execute(
            "UPDATE hybrid_garmin_connections SET encrypted_tokenstore = %s, status = 'connected', "
            "updated_at = NOW() WHERE user_id = %s", (encrypted, user_id),
        )
        db.commit()
    finally:
        db.close()


def mark_reauth_required(user_id: str) -> None:
    db = connect()
    try:
        initialize_connections(db)
        db.execute(
            "UPDATE hybrid_garmin_connections SET status = 'reauth_required', updated_at = NOW() "
            "WHERE user_id = %s", (user_id,),
        )
        db.commit()
    finally:
        db.close()


def save_mfa_state(user_id: str, email: str, state: dict[str, Any]) -> None:
    email = str(email or "").strip().lower()[:254]
    encrypted = _cipher().encrypt(
        json.dumps({"email": email, "state": state}, separators=(",", ":")).encode("utf-8"),
    )
    db = connect()
    try:
        initialize_connections(db)
        db.execute("""
            INSERT INTO hybrid_garmin_connections
                (user_id, encrypted_credentials, encrypted_mfa_state, mfa_expires_at,
                 mfa_attempts, email_hint, status, updated_at)
            VALUES (%s, NULL, %s, NOW() + INTERVAL '10 minutes', 0, %s, 'mfa_required', NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                encrypted_credentials = NULL,
                encrypted_mfa_state = EXCLUDED.encrypted_mfa_state,
                mfa_expires_at = EXCLUDED.mfa_expires_at,
                mfa_attempts = 0, email_hint = EXCLUDED.email_hint,
                status = 'mfa_required', updated_at = NOW()
        """, (user_id, encrypted, _hint(email)))
        db.commit()
    finally:
        db.close()


def load_mfa_state(user_id: str) -> tuple[str, dict[str, Any]]:
    db = connect()
    try:
        initialize_connections(db)
        row = db.execute("""
            UPDATE hybrid_garmin_connections
            SET mfa_attempts = mfa_attempts + 1, updated_at = NOW()
            WHERE user_id = %s AND encrypted_mfa_state IS NOT NULL
              AND mfa_expires_at > NOW() AND mfa_attempts < 5
            RETURNING encrypted_mfa_state
        """, (user_id,)).fetchone()
        db.commit()
    finally:
        db.close()
    if not row:
        clear_mfa_state(user_id)
        raise ValueError("Az MFA-munkamenet lejárt vagy túl sok próbálkozás történt. Indítsd újra a csatlakoztatást.")
    try:
        payload = json.loads(_cipher().decrypt(bytes(row[0])))
        return payload["email"], payload["state"]
    except (InvalidToken, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        clear_mfa_state(user_id)
        raise RuntimeError("Az MFA-munkamenet nem állítható helyre. Indítsd újra a csatlakoztatást.") from exc


def clear_mfa_state(user_id: str) -> None:
    db = connect()
    try:
        initialize_connections(db)
        db.execute("""
            UPDATE hybrid_garmin_connections
            SET encrypted_mfa_state = NULL, mfa_expires_at = NULL, mfa_attempts = 0,
                status = CASE WHEN encrypted_tokenstore IS NULL THEN 'disconnected' ELSE status END,
                updated_at = NOW()
            WHERE user_id = %s
        """, (user_id,))
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
