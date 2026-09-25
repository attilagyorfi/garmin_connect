from http.client import HTTPMessage

import pytest
import auth_store

from auth_store import (
    _admin_emails, _clean_credentials, _device_name, _ip_hint, _limit_key,
    _password_hash, _public_user, _verify_password, cookie_header,
    initialize_auth, is_ai_enabled, token_from_headers,
)


def test_scrypt_password_hash_is_salted_and_verifiable():
    first = _password_hash("hosszú-biztonságos-jelszó")
    second = _password_hash("hosszú-biztonságos-jelszó")
    assert first != second
    assert _verify_password("hosszú-biztonságos-jelszó", first)
    assert not _verify_password("hibás-jelszó", first)


@pytest.mark.parametrize("email,password", [
    ("hibás", "hosszú-biztonságos-jelszó"),
    ("sportolo@example.com", "rövid"),
])
def test_credentials_are_validated(email, password):
    with pytest.raises(ValueError):
        _clean_credentials(email, password)


def test_session_cookie_is_http_only_and_strict():
    value = cookie_header("titkos-token")
    assert "HttpOnly" in value
    assert "SameSite=Strict" in value
    assert "Secure" in value


def test_session_token_is_read_from_cookie_header():
    headers = HTTPMessage()
    headers.add_header("Cookie", "theme=teal; hybrid_session=session-token")
    assert token_from_headers(headers) == "session-token"


def test_login_limit_key_does_not_expose_email_or_ip():
    value = _limit_key("sportolo@example.com", "192.0.2.10")
    assert len(value) == 64
    assert "sportolo" not in value
    assert value == _limit_key("sportolo@example.com", "192.0.2.10")


def test_session_metadata_is_human_readable_and_ip_is_masked():
    assert _device_name(
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit Chrome/140.0 Safari/537.36"
    ) == "Chrome · Windows"
    assert _ip_hint("192.0.2.123") == "192.0.2.…"
    assert _ip_hint("2001:db8:abcd:12::1") == "2001:db8:abcd:…"


def test_admin_accounts_and_ai_flag_are_explicit(monkeypatch):
    monkeypatch.setenv("HYBRID_ADMIN_EMAILS", " Admin@Example.com, hibás, sportolo@example.com ")
    monkeypatch.delenv("HYBRID_AI_ENABLED", raising=False)
    assert _admin_emails() == {"admin@example.com", "sportolo@example.com"}
    assert is_ai_enabled() is False
    monkeypatch.setenv("HYBRID_AI_ENABLED", "true")
    assert is_ai_enabled() is True


def test_public_user_includes_authorization_role():
    user = _public_user(("id", "admin@example.com", "Admin", object(), "admin", "active"))
    assert user["role"] == "admin"
    assert user["accessStatus"] == "active"


class AccessConnection:
    def __init__(self, target=("member", "active", "sportolo@example.com")):
        self.target = target
        self.sql = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        self.current_sql = sql
        return self

    def fetchone(self):
        if "FROM pg_attribute" in self.current_sql:
            return (True,)
        if "SELECT role FROM hybrid_users" in self.current_sql:
            return ("admin",)
        if "SELECT role, access_status, email" in self.current_sql:
            return self.target
        return None

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_suspending_member_revokes_every_session(monkeypatch):
    db = AccessConnection()
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    auth_store.set_user_access("admin-1", "member-1", "suspended")
    statements = [sql for sql, _params in db.sql]
    assert any("UPDATE hybrid_users SET access_status" in sql for sql in statements)
    assert any("DELETE FROM hybrid_sessions" in sql for sql in statements)
    audit = next(params for sql, params in db.sql if "INSERT INTO hybrid_admin_audit" in sql)
    assert audit[1:] == ("admin-1", "user_suspended", "member-1", "sportolo@example.com")
    assert db.commits == 2


def test_admin_access_cannot_be_suspended(monkeypatch):
    db = AccessConnection(target=("admin", "active", "other-admin@example.com"))
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    with pytest.raises(ValueError, match="Adminisztrátori"):
        auth_store.set_user_access("admin-1", "admin-2", "suspended")


def test_unchanged_access_state_is_not_added_to_audit(monkeypatch):
    db = AccessConnection(target=("member", "active", "sportolo@example.com"))
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    auth_store.set_user_access("admin-1", "member-1", "active")
    assert not any("INSERT INTO hybrid_admin_audit" in sql for sql, _params in db.sql)
    assert db.commits == 1


def test_invite_audit_never_contains_generated_secret(monkeypatch):
    db = AccessConnection()
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    token, invite = auth_store.create_invite("admin-1")
    audit = next(params for sql, params in db.sql if "INSERT INTO hybrid_admin_audit" in sql)
    assert audit[1:] == ("admin-1", "invite_created", None, None)
    assert token not in repr(audit)
    assert invite["id"] not in repr(audit)


class SchemaConnection:
    def __init__(self, readiness):
        self.readiness = iter(readiness)
        self.statements = []
        self.commits = 0

    def execute(self, sql):
        self.statements.append(sql.strip())
        return self

    def fetchone(self):
        return (next(self.readiness),)

    def commit(self):
        self.commits += 1


def test_ready_auth_schema_does_not_run_ddl_or_acquire_migration_lock():
    db = SchemaConnection([True])
    initialize_auth(db)
    assert len(db.statements) == 1
    assert "FROM pg_attribute" in db.statements[0]
    assert db.commits == 1


def test_auth_schema_rechecks_after_lock_when_another_request_migrated():
    db = SchemaConnection([False, True])
    initialize_auth(db)
    assert len(db.statements) == 3
    assert "pg_advisory_xact_lock" in db.statements[1]
    assert "FROM pg_attribute" in db.statements[2]
    assert db.commits == 1


def test_auth_schema_initialization_locks_before_any_ddl_and_commits():
    db = SchemaConnection([False, False])
    initialize_auth(db)
    assert "pg_advisory_xact_lock" in db.statements[1]
    assert "FROM pg_attribute" in db.statements[2]
    assert db.statements[3].startswith("CREATE TABLE IF NOT EXISTS hybrid_users")
    assert any("ALTER TABLE hybrid_sessions" in sql for sql in db.statements[3:])
    assert db.commits == 1
