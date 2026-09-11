from http.client import HTTPMessage

import pytest

from auth_store import (
    _clean_credentials, _device_name, _ip_hint, _limit_key, _password_hash,
    _verify_password, cookie_header, initialize_auth, token_from_headers,
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
