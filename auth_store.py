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
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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


def register(email: str, password: str, name: str) -> tuple[dict[str, str], str]:
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
        return {"id": user_id, "email": email, "name": name}, _new_session(db, user_id)
    finally:
        db.close()


def login(email: str, password: str) -> tuple[dict[str, str], str]:
    email, password, _ = _clean_credentials(email, password)
    db = connect()
    try:
        initialize_auth(db)
        row = db.execute("SELECT id, email, display_name, password_hash FROM hybrid_users WHERE email = %s", (email,)).fetchone()
        if not row or not _verify_password(password, row[3]):
            raise ValueError("Hibás e-mail-cím vagy jelszó.")
        user = {"id": str(row[0]), "email": row[1], "name": row[2]}
        return user, _new_session(db, user["id"])
    finally:
        db.close()


def token_from_headers(headers: Any) -> str | None:
    cookie = SimpleCookie()
    cookie.load(headers.get("Cookie", ""))
    item = cookie.get(SESSION_COOKIE)
    return item.value if item else None


def current_user(headers: Any) -> dict[str, str] | None:
    token = token_from_headers(headers)
    if not token:
        return None
    db = connect()
    try:
        initialize_auth(db)
        row = db.execute("""
            SELECT u.id, u.email, u.display_name
            FROM hybrid_sessions s JOIN hybrid_users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW()
        """, (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return {"id": str(row[0]), "email": row[1], "name": row[2]} if row else None
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
