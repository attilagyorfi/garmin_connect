"""PostgreSQL-backed accounts and opaque browser sessions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
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
INVITE_DAYS = 7
MAX_LOGIN_FAILURES = 5
LOGIN_WINDOW_MINUTES = 15
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RateLimitError(ValueError):
    """Raised when repeated login failures temporarily lock a client key."""


def _auth_schema_ready(db: Any) -> bool:
    # Catalog reads do not acquire locks on the session tables used by requests.
    return bool(db.execute("""
        SELECT
            to_regclass('hybrid_users') IS NOT NULL
            AND to_regclass('hybrid_sessions') IS NOT NULL
            AND to_regclass('hybrid_auth_tokens') IS NOT NULL
            AND to_regclass('hybrid_login_limits') IS NOT NULL
            AND to_regclass('hybrid_invites') IS NOT NULL
            AND to_regclass('hybrid_admin_audit') IS NOT NULL
            AND to_regclass('hybrid_sessions_user_idx') IS NOT NULL
            AND to_regclass('hybrid_sessions_public_id_idx') IS NOT NULL
            AND to_regclass('hybrid_auth_tokens_user_idx') IS NOT NULL
            AND to_regclass('hybrid_admin_audit_created_idx') IS NOT NULL
            AND (
                SELECT COUNT(*) = 7 FROM pg_attribute
                WHERE NOT attisdropped AND (
                    (attrelid = to_regclass('hybrid_sessions')
                     AND attname IN ('session_id', 'user_agent', 'ip_hint', 'last_seen_at'))
                    OR (attrelid = to_regclass('hybrid_users') AND attname IN ('email_verified_at', 'role', 'access_status'))
                )
            )
    """).fetchone()[0])


def initialize_auth(db: Any) -> None:
    # Running CREATE INDEX / ALTER TABLE on every request can deadlock with
    # concurrent authentication reads and last-seen updates. Migrate only once.
    if _auth_schema_ready(db):
        _apply_bootstrap_admin(db)
        db.commit()
        return
    db.execute("SELECT pg_advisory_xact_lock(1213809234, 1)")
    if _auth_schema_ready(db):
        _apply_bootstrap_admin(db)
        db.commit()
        return
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
    db.execute("ALTER TABLE hybrid_sessions ADD COLUMN IF NOT EXISTS session_id TEXT")
    db.execute("ALTER TABLE hybrid_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT")
    db.execute("ALTER TABLE hybrid_sessions ADD COLUMN IF NOT EXISTS ip_hint TEXT")
    db.execute("ALTER TABLE hybrid_sessions ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS hybrid_sessions_public_id_idx ON hybrid_sessions(session_id) WHERE session_id IS NOT NULL")
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
    db.execute("ALTER TABLE hybrid_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'member'")
    db.execute("ALTER TABLE hybrid_users ADD COLUMN IF NOT EXISTS access_status TEXT NOT NULL DEFAULT 'active'")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_invites (
            token_hash TEXT PRIMARY KEY,
            created_by UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            used_by UUID REFERENCES hybrid_users(id) ON DELETE SET NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_invites_created_idx ON hybrid_invites(created_by, created_at DESC)")
    db.execute("""
        CREATE TABLE IF NOT EXISTS hybrid_admin_audit (
            id UUID PRIMARY KEY,
            actor_id UUID NOT NULL REFERENCES hybrid_users(id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            target_user_id UUID REFERENCES hybrid_users(id) ON DELETE SET NULL,
            target_email TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS hybrid_admin_audit_created_idx ON hybrid_admin_audit(created_at DESC)")
    _apply_bootstrap_admin(db)
    db.commit()


def _admin_emails() -> set[str]:
    return {
        item.strip().lower()
        for item in os.getenv("HYBRID_ADMIN_EMAILS", "").split(",")
        if EMAIL_PATTERN.fullmatch(item.strip().lower())
    }


def _apply_bootstrap_admin(db: Any) -> None:
    emails = sorted(_admin_emails())
    if emails:
        db.execute(
            "UPDATE hybrid_users SET role = 'admin' WHERE LOWER(email) = ANY(%s) AND role <> 'admin'",
            (emails,),
        )


def is_ai_enabled() -> bool:
    return os.getenv("HYBRID_AI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


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


def _ip_hint(value: str) -> str:
    value = str(value or "").strip()[:80]
    if ":" in value:
        parts = value.split(":")
        return ":".join(parts[:3]) + ":…"
    parts = value.split(".")
    return ".".join(parts[:3]) + ".…" if len(parts) == 4 else "ismeretlen"


def _new_session(db: Any, user_id: str, user_agent: str = "", client_ip: str = "") -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        """INSERT INTO hybrid_sessions
           (token_hash, user_id, session_id, user_agent, ip_hint, expires_at, last_seen_at)
           VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
        (
            hashlib.sha256(token.encode()).hexdigest(), user_id, str(uuid.uuid4()),
            str(user_agent or "")[:500], _ip_hint(client_ip),
            datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        ),
    )
    db.commit()
    return token


def _public_user(row: Any) -> dict[str, Any]:
    return {
        "id": str(row[0]), "email": row[1], "name": row[2],
        "emailVerified": bool(row[3]), "role": row[4] or "member",
        "accessStatus": row[5] or "active",
    }


def _new_auth_token(db: Any, user_id: str, purpose: str, *, commit: bool = True) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("DELETE FROM hybrid_auth_tokens WHERE user_id = %s AND purpose = %s", (user_id, purpose))
    db.execute(
        "INSERT INTO hybrid_auth_tokens (token_hash, user_id, purpose, expires_at) VALUES (%s, %s, %s, %s)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, purpose, datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)),
    )
    if commit:
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


def register(
    email: str, password: str, name: str, invite_token: str,
    user_agent: str = "", client_ip: str = "",
) -> tuple[dict[str, Any], str]:
    email, password, name = _clean_credentials(email, password, name)
    if not name:
        raise ValueError("Add meg a nevedet.")
    db = connect()
    try:
        initialize_auth(db)
        invite_hash = hashlib.sha256(str(invite_token or "").encode()).hexdigest()
        invite = db.execute(
            """SELECT token_hash FROM hybrid_invites
               WHERE token_hash = %s AND used_at IS NULL AND revoked_at IS NULL
                 AND expires_at > NOW() FOR UPDATE""",
            (invite_hash,),
        ).fetchone()
        if not invite:
            raise ValueError("A meghívó hivatkozás lejárt, visszavonták vagy már felhasználták.")
        user_id = str(uuid.uuid4())
        try:
            db.execute(
                """INSERT INTO hybrid_users
                   (id, email, password_hash, display_name, email_verified_at, role)
                   VALUES (%s, %s, %s, %s, NOW(), 'member')""",
                (user_id, email, _password_hash(password), name),
            )
            db.execute(
                "UPDATE hybrid_invites SET used_at = NOW(), used_by = %s WHERE token_hash = %s",
                (user_id, invite_hash),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            if db.execute("SELECT 1 FROM hybrid_users WHERE email = %s", (email,)).fetchone():
                raise ValueError("Ehhez az e-mail-címhez már tartozik fiók.") from exc
            raise
        user = {
            "id": user_id, "email": email, "name": name,
            "emailVerified": True, "role": "member", "accessStatus": "active",
        }
        return user, _new_session(db, user_id, user_agent, client_ip)
    finally:
        db.close()


def login(
    email: str, password: str, client_id: str = "unknown",
    user_agent: str = "", client_ip: str = "",
) -> tuple[dict[str, Any], str]:
    email, password, _ = _clean_credentials(email, password)
    db = connect()
    try:
        initialize_auth(db)
        key = _limit_key(email, client_id)
        _check_login_limit(db, key)
        row = db.execute("SELECT id, email, display_name, email_verified_at, role, access_status, password_hash FROM hybrid_users WHERE email = %s", (email,)).fetchone()
        if not row or not _verify_password(password, row[6]):
            _record_login_failure(db, key)
            raise ValueError("Hibás e-mail-cím vagy jelszó.")
        if row[5] != "active":
            raise ValueError("A fiók hozzáférését az adminisztrátor felfüggesztette.")
        db.execute("DELETE FROM hybrid_login_limits WHERE limit_key = %s", (key,))
        db.commit()
        user = _public_user(row)
        if not user["emailVerified"]:
            raise ValueError("A belépés előtt erősítsd meg az e-mail-címedet.")
        return user, _new_session(db, user["id"], user_agent, client_ip)
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


def verify_email(
    token: str, user_agent: str = "", client_ip: str = "",
) -> tuple[dict[str, Any], str]:
    db = connect()
    try:
        initialize_auth(db)
        token_hash = hashlib.sha256(str(token or "").encode()).hexdigest()
        row = db.execute("""
            SELECT u.id, u.email, u.display_name, u.email_verified_at, u.role, u.access_status
            FROM hybrid_auth_tokens t JOIN hybrid_users u ON u.id = t.user_id
            WHERE t.token_hash = %s AND t.purpose = 'verify_email'
              AND t.used_at IS NULL AND t.expires_at > NOW()
        """, (token_hash,)).fetchone()
        if not row:
            raise ValueError("A megerősítő hivatkozás lejárt vagy már felhasználták.")
        db.execute("UPDATE hybrid_users SET email_verified_at = COALESCE(email_verified_at, NOW()) WHERE id = %s", (row[0],))
        db.execute("UPDATE hybrid_auth_tokens SET used_at = NOW() WHERE token_hash = %s", (token_hash,))
        db.commit()
        user = {
            "id": str(row[0]), "email": row[1], "name": row[2],
            "emailVerified": True, "role": row[4] or "member", "accessStatus": row[5] or "active",
        }
        return user, _new_session(db, user["id"], user_agent, client_ip)
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


def _require_admin(db: Any, user_id: str) -> None:
    row = db.execute("SELECT role FROM hybrid_users WHERE id = %s", (user_id,)).fetchone()
    if not row or row[0] != "admin":
        raise PermissionError("Ehhez a művelethez adminisztrátori jogosultság szükséges.")


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _record_admin_audit(
    db: Any,
    actor_id: str,
    action: str,
    target_user_id: str | None = None,
    target_email: str | None = None,
) -> None:
    """Record an admin action without ever persisting a generated secret."""
    db.execute(
        """INSERT INTO hybrid_admin_audit
           (id, actor_id, action, target_user_id, target_email)
           VALUES (%s, %s, %s, %s, %s)""",
        (str(uuid.uuid4()), actor_id, action, target_user_id, target_email),
    )


def create_invite(admin_id: str, days: int = INVITE_DAYS) -> tuple[str, dict[str, Any]]:
    db = connect()
    try:
        initialize_auth(db)
        _require_admin(db, admin_id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(30, int(days))))
        db.execute(
            "INSERT INTO hybrid_invites (token_hash, created_by, expires_at) VALUES (%s, %s, %s)",
            (token_hash, admin_id, expires_at),
        )
        _record_admin_audit(db, admin_id, "invite_created")
        db.commit()
        return token, {"id": token_hash, "expiresAt": _iso(expires_at), "status": "active"}
    finally:
        db.close()


def list_access_admin(admin_id: str) -> dict[str, Any]:
    db = connect()
    try:
        initialize_auth(db)
        _require_admin(db, admin_id)
        users = db.execute(
            """SELECT id, email, display_name, role, created_at, access_status
               FROM hybrid_users ORDER BY created_at DESC"""
        ).fetchall()
        invites = db.execute(
            """SELECT i.token_hash, i.created_at, i.expires_at, i.used_at,
                      i.revoked_at, u.email
               FROM hybrid_invites i
               LEFT JOIN hybrid_users u ON u.id = i.used_by
               ORDER BY i.created_at DESC LIMIT 100"""
        ).fetchall()
        audit = db.execute(
            """SELECT a.id, a.action, a.created_at, actor.email,
                      COALESCE(target.email, a.target_email)
               FROM hybrid_admin_audit a
               JOIN hybrid_users actor ON actor.id = a.actor_id
               LEFT JOIN hybrid_users target ON target.id = a.target_user_id
               ORDER BY a.created_at DESC LIMIT 100"""
        ).fetchall()
        now = datetime.now(timezone.utc)
        return {
            "users": [
                {
                    "id": str(row[0]), "email": row[1], "name": row[2], "role": row[3],
                    "createdAt": _iso(row[4]), "accessStatus": row[5] or "active",
                }
                for row in users
            ],
            "invites": [
                {
                    "id": row[0], "createdAt": _iso(row[1]), "expiresAt": _iso(row[2]),
                    "usedAt": _iso(row[3]), "revokedAt": _iso(row[4]), "usedBy": row[5],
                    "status": "used" if row[3] else "revoked" if row[4] else "expired" if row[2] <= now else "active",
                }
                for row in invites
            ],
            "audit": [
                {
                    "id": str(row[0]), "action": row[1], "createdAt": _iso(row[2]),
                    "actor": row[3], "target": row[4],
                }
                for row in audit
            ],
        }
    finally:
        db.close()


def revoke_invite(admin_id: str, invite_id: str) -> None:
    db = connect()
    try:
        initialize_auth(db)
        _require_admin(db, admin_id)
        revoked = db.execute(
            """UPDATE hybrid_invites SET revoked_at = NOW()
               WHERE token_hash = %s AND used_at IS NULL AND revoked_at IS NULL
               RETURNING token_hash""",
            (str(invite_id or ""),),
        ).fetchone()
        if not revoked:
            raise ValueError("Az aktív meghívó nem található.")
        _record_admin_audit(db, admin_id, "invite_revoked")
        db.commit()
    finally:
        db.close()


def set_user_access(admin_id: str, user_id: str, status: str) -> None:
    if status not in {"active", "suspended"}:
        raise ValueError("Érvénytelen hozzáférési állapot.")
    db = connect()
    try:
        initialize_auth(db)
        _require_admin(db, admin_id)
        target = db.execute(
            "SELECT role, access_status, email FROM hybrid_users WHERE id = %s",
            (str(user_id or ""),),
        ).fetchone()
        if not target:
            raise ValueError("A felhasználó nem található.")
        if str(user_id) == str(admin_id) or target[0] == "admin":
            raise ValueError("Adminisztrátori fiók hozzáférése itt nem módosítható.")
        if target[1] == status:
            return
        db.execute(
            "UPDATE hybrid_users SET access_status = %s WHERE id = %s",
            (status, user_id),
        )
        if status == "suspended":
            db.execute("DELETE FROM hybrid_sessions WHERE user_id = %s", (user_id,))
        _record_admin_audit(
            db, admin_id,
            "user_suspended" if status == "suspended" else "user_reactivated",
            str(user_id), target[2],
        )
        db.commit()
    finally:
        db.close()


def create_admin_password_reset(admin_id: str, email: str) -> tuple[str, str] | None:
    clean_email = str(email or "").strip().lower()[:254]
    if not EMAIL_PATTERN.fullmatch(clean_email):
        raise ValueError("Adj meg egy érvényes e-mail-címet.")
    db = connect()
    try:
        initialize_auth(db)
        _require_admin(db, admin_id)
        row = db.execute("SELECT id FROM hybrid_users WHERE email = %s", (clean_email,)).fetchone()
        if not row:
            return None
        token = _new_auth_token(db, str(row[0]), "reset_password", commit=False)
        _record_admin_audit(db, admin_id, "password_reset_created", str(row[0]), clean_email)
        db.commit()
        return clean_email, token
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
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = db.execute("""
            SELECT u.id, u.email, u.display_name, u.email_verified_at, u.role, u.access_status
            FROM hybrid_sessions s JOIN hybrid_users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW() AND u.access_status = 'active'
        """, (token_hash,)).fetchone()
        if row:
            db.execute(
                """UPDATE hybrid_sessions SET last_seen_at = NOW()
                   WHERE token_hash = %s
                     AND COALESCE(last_seen_at, created_at) < NOW() - INTERVAL '5 minutes'""",
                (token_hash,),
            )
            db.commit()
        return _public_user(row) if row else None
    except Exception as exc:
        logging.getLogger(__name__).error(
            "current_user_failed type=%s sqlstate=%s",
            type(exc).__name__, getattr(exc, "sqlstate", None),
        )
        raise
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


def _device_name(user_agent: str) -> str:
    agent = str(user_agent or "").lower()
    browser = (
        "Edge" if "edg/" in agent else "Chrome" if "chrome/" in agent
        else "Firefox" if "firefox/" in agent else "Safari" if "safari/" in agent
        else "Ismeretlen böngésző"
    )
    system = (
        "Windows" if "windows" in agent else "iPhone" if "iphone" in agent
        else "iPad" if "ipad" in agent else "Android" if "android" in agent
        else "macOS" if "mac os" in agent else "Linux" if "linux" in agent
        else "ismeretlen eszköz"
    )
    return f"{browser} · {system}"


def list_sessions(headers: Any) -> list[dict[str, Any]]:
    token = token_from_headers(headers)
    if not token:
        raise ValueError("A művelethez bejelentkezés szükséges.")
    current_hash = hashlib.sha256(token.encode()).hexdigest()
    db = connect()
    try:
        initialize_auth(db)
        owner = db.execute(
            "SELECT user_id FROM hybrid_sessions WHERE token_hash = %s AND expires_at > NOW()",
            (current_hash,),
        ).fetchone()
        if not owner:
            raise ValueError("A munkamenet lejárt.")
        rows = db.execute("""
            SELECT token_hash, session_id, user_agent, ip_hint, created_at,
                   COALESCE(last_seen_at, created_at), expires_at
            FROM hybrid_sessions
            WHERE user_id = %s AND expires_at > NOW()
            ORDER BY COALESCE(last_seen_at, created_at) DESC
        """, (owner[0],)).fetchall()
        result = []
        for row in rows:
            session_id = row[1] or str(uuid.uuid4())
            if not row[1]:
                db.execute(
                    "UPDATE hybrid_sessions SET session_id = %s WHERE token_hash = %s",
                    (session_id, row[0]),
                )
            result.append({
                "id": session_id,
                "device": _device_name(row[2]),
                "ipHint": row[3] or "ismeretlen",
                "createdAt": row[4].isoformat(),
                "lastSeenAt": row[5].isoformat(),
                "expiresAt": row[6].isoformat(),
                "current": hmac.compare_digest(row[0], current_hash),
            })
        db.commit()
        return result
    finally:
        db.close()


def revoke_session(headers: Any, session_id: str) -> None:
    token = token_from_headers(headers)
    if not token:
        raise ValueError("A művelethez bejelentkezés szükséges.")
    current_hash = hashlib.sha256(token.encode()).hexdigest()
    db = connect()
    try:
        initialize_auth(db)
        current = db.execute(
            "SELECT user_id, session_id FROM hybrid_sessions WHERE token_hash = %s AND expires_at > NOW()",
            (current_hash,),
        ).fetchone()
        if not current:
            raise ValueError("A munkamenet lejárt.")
        if str(current[1]) == str(session_id):
            raise ValueError("A jelenlegi munkamenetet a Kijelentkezés gombbal zárhatod le.")
        db.execute(
            "DELETE FROM hybrid_sessions WHERE user_id = %s AND session_id = %s",
            (current[0], str(session_id)),
        )
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
