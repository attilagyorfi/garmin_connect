"""PostgreSQL-backed accounts and opaque browser sessions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from typing import Any

from cloud_cache import connect


SESSION_COOKIE = "hybrid_session"
SESSION_DAYS = 30
TOKEN_MINUTES = 30
MAX_LOGIN_FAILURES = 5
LOGIN_WINDOW_MINUTES = 15
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RateLimitError(ValueError):
    """Raised when repeated login failures temporarily lock a client key."""


def initialize_auth(db: Any) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_users (
            id UUID PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_sessions_user_idx ON hybrid_sessions(user_id)")
    db.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hybrid_users' AND column_name = 'email_verified_at'
            ) THEN
                ALTER TABLE hybrid_users ADD COLUMN email_verified_at TIMESTAMPTZ;
                UPDATE hybrid_users SET email_verified_at = created_at;
            END IF;
        END $$
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_auth_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            purpose TEXT NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_auth_tokens_user_idx ON hybrid_auth_tokens(user_id, purpose)")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_login_limits (
            limit_key TEXT PRIMARY KEY,
            failures INTEGER NOT NULL DEFAULT 0,
            window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_until TIMESTAMPTZ
        )
    """)
    db.commit()


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(value).decode()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=base64.urlsafe_b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def _clean_credentials(email: str, password: str, name: str = "") -> tuple[str, str, str]:
    clean_email = str(email or "").strip().lower()[:254]
    clean_name = str(name or "").strip()[:80]
    if not EMAIL_PATTERN.fullmatch(clean_email):
        raise ValueError("Adj meg egy érvényes e-mail-címet.")
    if len(password or "") < 10 or len(password) > 200:
        raise ValueError("A jelszó legalább 10 karakter legyen.")
    return clean_email, password, clean_name


def _new_session(db: Any, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO hybrid_sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)),
    )
    db.commit()
    return token


def _public_user(row: Any) -> dict[str, Any]:
    return {
        "id": str(row[0]), "email": row[1], "name": row[2],
        "emailVerified": bool(row[3]),
    }


def _new_auth_token(db: Any, user_id: str, purpose: str) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM hybrid_auth_tokens WHERE user_id = %s AND purpose = %s", (user_id, purpose))
    db.execute(
        "INSERT INTO hybrid_auth_tokens (token_hash, user_id, purpose, expires_at) VALUES (%s, %s, %s, %s)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, purpose, datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)),
    )
    db.commit()
    return token


def _limit_key(email: str, client_id: str) -> str:
    return hashlib.sha256(f"{email}|{client_id}".encode()).hexdigest()


def _check_login_limit(db: Any, key: str) -> None:
    row = db.execute("SELECT failures, window_started_at, locked_until FROM hybrid_login_limits WHERE limit_key = %s", (key,)).fetchone()
    now = datetime.now(timezone.utc)
    if row and row[2] and row[2] > now:
        seconds = max(1, int((row[2] - now).total_seconds()))
        raise RateLimitError(f"Túl sok sikertelen próbálkozás. Próbáld újra {max(1, (seconds + 59) // 60)} perc múlva.")


def _record_login_failure(db: Any, key: str) -> None:
    now = datetime.now(timezone.utc)
    row = db.execute("SELECT failures, window_started_at FROM hybrid_login_limits WHERE limit_key = %s", (key,)).fetchone()
    failures = 1 if not row or row[1] < now - timedelta(minutes=LOGIN_WINDOW_MINUTES) else int(row[0]) + 1
    locked_until = now + timedelta(minutes=LOGIN_WINDOW_MINUTES) if failures >= MAX_LOGIN_FAILURES else None
    db.execute("""
        INSERT INTO hybrid_login_limits (limit_key, failures, window_started_at, locked_until)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (limit_key) DO UPDATE SET failures = EXCLUDED.failures,
          window_started_at = EXCLUDED.window_started_at, locked_until = EXCLUDED.locked_until
    """, (key, failures, now if failures == 1 else row[1], locked_until))
    db.commit()


def register(email: str, password: str, name: str) -> tuple[dict[str, Any], str]:
    email, password, name = _clean_credentials(email, password, name)
    if not name:
        raise ValueError("Add meg a nevedet.")
    db = connect()
    try:
        initialize_auth(db)
        user_id = str(uuid.uuid4())
        try:
            db.execute("INSERT INTO hybrid_users (id, email, password_hash, display_name) VALUES (%s, %s, %s, %s)", (user_id, email, _password_hash(password), name))
            db.commit()
        except Exception as exc:
            db.rollback()
            if db.execute("SELECT 1 FROM hybrid_users WHERE email = %s", (email,)).fetchone():
                raise ValueError("Ehhez az e-mail-címhez már tartozik fiók.") from exc
            raise
        return {"id": user_id, "email": email, "name": name, "emailVerified": False}, _new_auth_token(db, user_id, "verify_email")
    finally:
        db.close()


def login(email: str, password: str, client_id: str = "unknown") -> tuple[dict[str, Any], str]:
    email, password, _ = _clean_credentials(email, password)
    db = connect()
    try:
        initialize_auth(db)
        key = _limit_key(email, client_id)
        _check_login_limit(db, key)
        row = db.execute("SELECT id, email, display_name, email_verified_at, password_hash FROM hybrid_users WHERE email = %s", (email,)).fetchone()
        if not row or not _verify_password(password, row[4]):
            _record_login_failure(db, key)
            raise ValueError("Hibás e-mail-cím vagy jelszó.")
        db.execute("DELETE FROM hybrid_login_limits WHERE limit_key = %s", (key,))
        db.commit()
        user = _public_user(row)
        if not user["emailVerified"]:
            raise ValueError("A belépés előtt erősítsd meg az e-mail-címedet.")
        return user, _new_session(db, user["id"])
    finally:
        db.close()


def resend_verification(email: str) -> tuple[str, str] | None:
    clean_email = str(email or "").strip().lower()[:254]
    if not EMAIL_PATTERN.fullmatch(clean_email):
        return None
    db = connect()
    try:
        initialize_auth(db)
        row = db.execute("SELECT id, email_verified_at FROM hybrid_users WHERE email = %s", (clean_email,)).fetchone()
        if not row or row[1]:
            return None
        return clean_email, _new_auth_token(db, str(row[0]), "verify_email")
    finally:
        db.close()


def verify_email(token: str) -> tuple[dict[str, Any], str]:
    db = connect()
    try:
        initialize_auth(db)
        token_hash = hashlib.sha256(str(token or "").encode()).hexdigest()
        row = db.execute("""
            SELECT u.id, u.email, u.display_name, u.email_verified_at
            FROM hybrid_auth_tokens t JOIN hybrid_users u ON u.id = t.user_id
            WHERE t.token_hash = %s AND t.purpose = 'verify_email'
              AND t.used_at IS NULL AND t.expires_at > NOW()
        """, (token_hash,)).fetchone()
        if not row:
            raise ValueError("A megerősítő hivatkozás lejárt vagy már felhasználták.")
        db.execute("UPDATE hybrid_users SET email_verified_at = COALESCE(email_verified_at, NOW()) WHERE id = %s", (row[0],))
        db.execute("UPDATE hybrid_auth_tokens SET used_at = NOW() WHERE token_hash = %s", (token_hash,))
        db.commit()
        user = {"id": str(row[0]), "email": row[1], "name": row[2], "emailVerified": True}
        return user, _new_session(db, user["id"])
    finally:
        db.close()


def create_password_reset(email: str) -> tuple[str, str] | None:
    clean_email = str(email or "").strip().lower()[:254]
    if not EMAIL_PATTERN.fullmatch(clean_email):
        return None
    db = connect()
    try:
        initialize_auth(db)
        row = db.execute("SELECT id FROM hybrid_users WHERE email = %s", (clean_email,)).fetchone()
        return (clean_email, _new_auth_token(db, str(row[0]), "reset_password")) if row else None
    finally:
        db.close()


def reset_password(token: str, password: str) -> None:
    if len(password or "") < 10 or len(password) > 200:
        raise ValueError("A jelszó legalább 10 karakter legyen.")
    db = connect()
    try:
        initialize_auth(db)
        token_hash = hashlib.sha256(str(token or "").encode()).hexdigest()
        row = db.execute("""
            SELECT user_id FROM hybrid_auth_tokens
            WHERE token_hash = %s AND purpose = 'reset_password'
              AND used_at IS NULL AND expires_at > NOW()
        """, (token_hash,)).fetchone()
        if not row:
            raise ValueError("A jelszó-visszaállító hivatkozás lejárt vagy már felhasználták.")
        db.execute("UPDATE hybrid_users SET password_hash = %s WHERE id = %s", (_password_hash(password), row[0]))
        db.execute("UPDATE hybrid_auth_tokens SET used_at = NOW() WHERE token_hash = %s", (token_hash,))
        db.execute("DELETE FROM hybrid_sessions WHERE user_id = %s", (row[0],))
        db.commit()
    finally:
        db.close()


def token_from_headers(headers: Any) -> str | None:
    cookie = SimpleCookie()
    cookie.load(headers.get("Cookie", ""))
    item = cookie.get(SESSION_COOKIE)
    return item.value if item else None


def current_user(headers: Any) -> dict[str, Any] | None:
    token = token_from_headers(headers)
    if not token:
        return None
    db = connect()
    try:
        initialize_auth(db)
        row = db.execute("""
            SELECT u.id, u.email, u.display_name, u.email_verified_at
            FROM hybrid_sessions s JOIN hybrid_users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW()
        """, (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return _public_user(row) if row else None
    finally:
        db.close()


def logout(headers: Any) -> None:
    token = token_from_headers(headers)
    if not token:
        return
    db = connect()
    try:
        initialize_auth(db)
        db.execute("DELETE FROM hybrid_sessions WHERE token_hash = %s", (hashlib.sha256(token.encode()).hexdigest(),))
        db.commit()
    finally:
        db.close()


def cookie_header(token: str, secure: bool = True) -> str:
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", f"Max-Age={SESSION_DAYS * 86400}", "HttpOnly", "SameSite=Strict"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie_header() -> str:
    return f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict; Secure"
