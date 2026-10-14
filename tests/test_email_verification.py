import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

import auth_email
import auth_store
from tests.test_auth_store import BootstrapConnection


def endpoint():
    spec = importlib.util.spec_from_file_location("verify_auth_endpoint", Path(__file__).parents[1] / "api" / "auth.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def handler_for(module, payload):
    raw = json.dumps(payload).encode("utf-8")
    handler = object.__new__(module.handler)
    handler.headers = {"Content-Length": str(len(raw)), "X-Forwarded-Proto": "https", "X-Forwarded-For": "192.0.2.10"}
    handler.rfile = BytesIO(raw)
    handler._send = Mock()
    return handler


@pytest.fixture
def mail_env(monkeypatch):
    monkeypatch.delenv("AUTH_EMAIL_TEST_MODE", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "Hybrid Athlete <noreply@example.test>")
    monkeypatch.setenv("AUTH_PUBLIC_URL", "https://app.example.test")


def test_verification_is_required_only_with_real_e_mail_delivery(mail_env, monkeypatch):
    assert auth_email.verification_required()
    monkeypatch.setenv("AUTH_EMAIL_TEST_MODE", "1")
    assert not auth_email.verification_required()  # local development: nobody would get the link
    monkeypatch.delenv("AUTH_EMAIL_TEST_MODE")
    monkeypatch.delenv("RESEND_API_KEY")
    assert not auth_email.verification_required()  # missing Resend settings must not lock new users out


def test_message_has_the_link_and_validity():
    subject, text, _markup = auth_email.verification_message("https://app.example.test/?auth=verify&token=a%2Bb", 24)
    assert "erősítsd meg" in subject and "24 óráig" in text and "token=a%2Bb" in text


def test_register_leaves_the_address_unconfirmed_and_returns_a_verification_token(monkeypatch):
    monkeypatch.setenv("HYBRID_ADMIN_EMAILS", "admin@example.com")
    db = BootstrapConnection()
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    sessions = Mock(return_value="session-token")
    monkeypatch.setattr(auth_store, "_new_session", sessions)
    user, token = auth_store.register("admin@example.com", "hosszu-biztonsagos", "Admin", "", require_verification=True)
    assert user["emailVerified"] is False and token != "session-token"
    sessions.assert_not_called()  # no session until the address is confirmed
    insert = next(params for sql, params in db.sql if sql.startswith("INSERT INTO hybrid_users"))
    assert insert[-1] is True
    token_row = next(params for sql, params in db.sql if sql.startswith("INSERT INTO hybrid_auth_tokens"))
    assert token_row[2] == "verify_email"


def test_register_endpoint_sends_the_link_and_sets_no_cookie(mail_env, monkeypatch):
    module = endpoint()
    sent = Mock(return_value={"sent": True, "testMode": False})
    register = Mock(return_value=({"id": "u1", "email": "uj@example.test", "emailVerified": False}, "ver+tok"))
    monkeypatch.setattr(module, "register", register)
    monkeypatch.setattr(module, "send_email", sent)
    handler = handler_for(module, {"action": "register", "email": "uj@example.test", "password": "hosszu-biztonsagos", "name": "Új", "inviteToken": "inv"})
    handler.do_POST()
    assert register.call_args.kwargs["require_verification"] is True
    body, status = handler._send.call_args.args
    assert status == 201 and body["verificationRequired"] is True and "uj@example.test" in body["message"]
    assert "cookie" not in handler._send.call_args.kwargs and len(handler._send.call_args.args) == 2
    assert "https://app.example.test/?auth=verify&token=ver%2Btok" in sent.call_args.args[2]


def test_register_without_e_mail_delivery_signs_in_as_before(monkeypatch):
    module = endpoint()
    monkeypatch.setattr(module, "verification_required", lambda: False)
    monkeypatch.setattr(module, "register", Mock(return_value=({"id": "u1", "email": "uj@example.test", "emailVerified": True}, "session")))
    handler = handler_for(module, {"action": "register", "email": "uj@example.test", "password": "x" * 12, "name": "Új", "inviteToken": "inv"})
    handler.do_POST()
    assert handler._send.call_args.args[1] == 201 and "hybrid_session=session" in handler._send.call_args.args[2]


def test_unverified_login_gets_a_distinct_code(monkeypatch):
    module = endpoint()
    monkeypatch.setattr(module, "login", Mock(side_effect=auth_store.UnverifiedEmailError("A belépés előtt erősítsd meg az e-mail-címedet.")))
    handler = handler_for(module, {"action": "login", "email": "uj@example.test", "password": "hosszu-biztonsagos"})
    handler.do_POST()
    body, status = handler._send.call_args.args
    assert status == 403 and body["code"] == "email_unverified"


@pytest.mark.parametrize("account", [("uj@example.test", "tok"), None])
def test_resend_answers_the_same_with_or_without_account(mail_env, monkeypatch, account):
    module = endpoint()
    sent = Mock(return_value={"sent": True, "testMode": False})
    monkeypatch.setattr(module, "resend_verification", lambda _email, _ip: account)
    monkeypatch.setattr(module, "send_email", sent)
    handler = handler_for(module, {"action": "resend_verification", "email": "uj@example.test"})
    handler.do_POST()
    assert handler._send.call_args.args == ({"ok": True, "message": module.SENT_VERIFICATION},)
    assert sent.called is bool(account)


class ResendConnection:
    def __init__(self, unverified):
        self.unverified = unverified

    def execute(self, sql, params=()):
        result = Mock()
        result.fetchone.return_value = ("user-1",) if self.unverified and "FROM hybrid_users" in sql else None
        return result

    def close(self):
        pass


@pytest.mark.parametrize("unverified", [True, False])
def test_resend_is_rate_limited_and_only_for_unconfirmed_accounts(monkeypatch, unverified):
    recorded = []
    monkeypatch.setattr(auth_store, "connect", lambda: ResendConnection(unverified))
    monkeypatch.setattr(auth_store, "initialize_auth", lambda _db: None)
    monkeypatch.setattr(auth_store, "_check_login_limit", lambda _db, _key: None)
    monkeypatch.setattr(auth_store, "_record_login_failure", lambda _db, key: recorded.append(key))
    monkeypatch.setattr(auth_store, "_new_auth_token", lambda _db, user_id, purpose, **kwargs: f"{purpose}:{user_id}:{kwargs.get('minutes')}")
    result = auth_store.resend_verification(" Uj@Example.test ", "192.0.2.10")
    assert result == (("uj@example.test", f"verify_email:user-1:{auth_store.VERIFY_MINUTES}") if unverified else None)
    assert len(set(recorded)) == 3
