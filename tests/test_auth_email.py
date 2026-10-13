import importlib.util
import json
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

import auth_email
import auth_store
from auth_email import EmailError, invite_message, password_reset_message, send_email

LINK = "https://app.example.test/?auth=reset&token=abc%2B123"


def endpoint(name):
    spec = importlib.util.spec_from_file_location(f"{name}_mail_endpoint", Path(__file__).parents[1] / "api" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@pytest.fixture
def mail_env(monkeypatch):
    monkeypatch.delenv("AUTH_EMAIL_TEST_MODE", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("AUTH_EMAIL_FROM", "Hybrid Athlete <noreply@example.test>")
    monkeypatch.setenv("AUTH_PUBLIC_URL", "https://app.example.test")


def test_messages_are_hungarian_and_escape_the_link():
    subject, text, markup = password_reset_message(LINK + '"><script>', 30)
    assert "jelszó-visszaállítás" in subject and "30 percig" in text and LINK in text
    assert "<script>" not in markup and "&quot;&gt;&lt;script&gt;" in markup
    subject, text, _markup = invite_message("https://app.example.test/?invite=x", 7)
    assert "Meghívó" in subject and "7 napig" in text


def test_send_email_posts_one_message_to_resend(mail_env):
    opener = Mock(return_value=FakeResponse())
    assert send_email("sportolo@example.test", "Tárgy", "szöveg", "<p>szöveg</p>", opener=opener) == {"sent": True, "testMode": False}
    request = opener.call_args.args[0]
    body = json.loads(request.data)
    assert request.full_url == auth_email.RESEND_URL and request.get_method() == "POST"
    assert request.headers["Authorization"] == "Bearer re_test_key"
    assert body == {"from": "Hybrid Athlete <noreply@example.test>", "to": ["sportolo@example.test"], "subject": "Tárgy", "text": "szöveg", "html": "<p>szöveg</p>"}


def test_test_mode_and_missing_configuration(mail_env, monkeypatch):
    opener = Mock()
    monkeypatch.setenv("AUTH_EMAIL_TEST_MODE", "1")
    assert send_email("a@example.test", "s", "t", "h", opener=opener) == {"sent": False, "testMode": True}
    opener.assert_not_called()
    monkeypatch.delenv("AUTH_EMAIL_TEST_MODE")
    monkeypatch.delenv("RESEND_API_KEY")
    with pytest.raises(EmailError, match="nincs beállítva"):
        send_email("a@example.test", "s", "t", "h", opener=opener)


@pytest.mark.parametrize("failure", [
    urllib.error.HTTPError(auth_email.RESEND_URL, 422, "bad", {}, None),
    urllib.error.URLError("down"),
    TimeoutError(),
])
def test_provider_failures_become_email_errors(mail_env, failure):
    with pytest.raises(EmailError):
        send_email("a@example.test", "s", "t", "h", opener=Mock(side_effect=failure))


class ResetConnection:
    def __init__(self, active):
        self.active, self.closed = active, False

    def execute(self, sql, params=()):
        result = Mock()
        result.fetchone.return_value = ("user-1",) if self.active and "FROM hybrid_users" in sql else None
        return result

    def close(self):
        self.closed = True


@pytest.mark.parametrize("active", [True, False])
def test_self_service_reset_counts_every_request_and_only_issues_for_active_accounts(monkeypatch, active):
    db, recorded = ResetConnection(active), []
    monkeypatch.setattr(auth_store, "connect", lambda: db)
    monkeypatch.setattr(auth_store, "initialize_auth", lambda _db: None)
    monkeypatch.setattr(auth_store, "_check_login_limit", lambda _db, _key: None)
    monkeypatch.setattr(auth_store, "_record_login_failure", lambda _db, key: recorded.append(key))
    monkeypatch.setattr(auth_store, "_new_auth_token", lambda _db, user_id, purpose: f"{purpose}:{user_id}")
    result = auth_store.request_password_reset(" Sportolo@Example.test ", "192.0.2.10")
    assert result == (("sportolo@example.test", "reset_password:user-1") if active else None)
    assert len(set(recorded)) == 3 and db.closed
    assert all("sportolo" not in key and "192.0.2" not in key for key in recorded)


def test_self_service_reset_is_blocked_once_rate_limited(monkeypatch):
    monkeypatch.setattr(auth_store, "connect", lambda: ResetConnection(True))
    monkeypatch.setattr(auth_store, "initialize_auth", lambda _db: None)
    monkeypatch.setattr(auth_store, "_check_login_limit", Mock(side_effect=auth_store.RateLimitError("Túl sok")))
    issue = Mock()
    monkeypatch.setattr(auth_store, "_new_auth_token", issue)
    with pytest.raises(auth_store.RateLimitError):
        auth_store.request_password_reset("sportolo@example.test", "192.0.2.10")
    issue.assert_not_called()


def auth_handler(module, payload):
    raw = json.dumps(payload).encode("utf-8")
    handler = object.__new__(module.handler)
    handler.headers = {"Content-Length": str(len(raw)), "X-Forwarded-Proto": "https", "X-Forwarded-For": "192.0.2.10"}
    handler.rfile = BytesIO(raw)
    handler._send = Mock()
    return handler


@pytest.mark.parametrize("account", [("sportolo@example.test", "tok+en"), None])
def test_reset_request_endpoint_answers_the_same_with_or_without_account(mail_env, monkeypatch, account):
    module = endpoint("auth")
    sent = Mock(return_value={"sent": True, "testMode": False})
    monkeypatch.setattr(module, "request_password_reset", lambda _email, _ip: account)
    monkeypatch.setattr(module, "send_email", sent)
    handler = auth_handler(module, {"action": "request_password_reset", "email": "sportolo@example.test"})
    handler.do_POST()
    body = handler._send.call_args.args[0]
    assert body["ok"] is True and "spam" in body["message"] and len(handler._send.call_args.args) == 1
    if account:
        to, _subject, text, _markup = sent.call_args.args
        assert to == "sportolo@example.test" and "https://app.example.test/?auth=reset&token=tok%2Ben" in text
    else:
        sent.assert_not_called()


def test_reset_request_endpoint_hides_provider_failure(mail_env, monkeypatch):
    module = endpoint("auth")
    monkeypatch.setattr(module, "request_password_reset", lambda _email, _ip: ("sportolo@example.test", "tok"))
    monkeypatch.setattr(module, "send_email", Mock(side_effect=EmailError("Az e-mail-szolgáltató hibát jelzett (500).")))
    handler = auth_handler(module, {"action": "request_password_reset", "email": "sportolo@example.test"})
    handler.do_POST()
    assert handler._send.call_args.args[0]["ok"] is True


def admin_handler(module, payload):
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send = Mock()
    handler._payload = lambda: payload
    return handler


def test_admin_invite_is_e_mailed_when_recipient_given(mail_env, monkeypatch):
    module = endpoint("admin")
    sent = Mock(return_value={"sent": True, "testMode": False})
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "admin-1", "role": "admin"})
    monkeypatch.setattr(module, "create_invite", lambda _admin: ("inv+tok", {"id": "invite-1"}))
    monkeypatch.setattr(module, "send_email", sent)
    handler = admin_handler(module, {"action": "create_invite", "email": "Uj@Example.test"})
    handler.do_POST()
    body, status = handler._send.call_args.args
    assert status == 201 and body["path"] == "/?invite=inv%2Btok" and body["emailSent"] is True and body["emailTo"] == "uj@example.test"
    assert "https://app.example.test/?invite=inv%2Btok" in sent.call_args.args[2]


def test_admin_invite_without_recipient_only_returns_link(mail_env, monkeypatch):
    module = endpoint("admin")
    sent = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "admin-1", "role": "admin"})
    monkeypatch.setattr(module, "create_invite", lambda _admin: ("tok", {"id": "invite-1"}))
    monkeypatch.setattr(module, "send_email", sent)
    handler = admin_handler(module, {"action": "create_invite"})
    handler.do_POST()
    assert "emailSent" not in handler._send.call_args.args[0]
    sent.assert_not_called()


def test_admin_invite_rejects_invalid_recipient_before_creating(mail_env, monkeypatch):
    module = endpoint("admin")
    create = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "admin-1", "role": "admin"})
    monkeypatch.setattr(module, "create_invite", create)
    handler = admin_handler(module, {"action": "create_invite", "email": "nem-email"})
    handler.do_POST()
    create.assert_not_called()
    assert handler._send.call_args.args[1] == 400


def test_admin_reset_mail_failure_keeps_copyable_link(mail_env, monkeypatch):
    module = endpoint("admin")
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "admin-1", "role": "admin"})
    monkeypatch.setattr(module, "create_admin_password_reset", lambda _admin, _email: ("tag@example.test", "tok"))
    monkeypatch.setattr(module, "send_email", Mock(side_effect=EmailError("Az e-mail-szolgáltató nem érhető el.")))
    handler = admin_handler(module, {"action": "create_password_reset", "email": "tag@example.test", "sendEmail": True})
    handler.do_POST()
    body, status = handler._send.call_args.args
    assert status == 201 and body["path"] == "/?auth=reset&token=tok"
    assert body["emailSent"] is False and "kézzel" in body["emailError"]
