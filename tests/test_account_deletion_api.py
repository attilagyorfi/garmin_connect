import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock


def endpoint():
    spec = importlib.util.spec_from_file_location(
        "account_deletion_endpoint", Path(__file__).parents[1] / "api" / "auth.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_handler(module, payload):
    raw = json.dumps(payload).encode("utf-8")
    handler = object.__new__(module.handler)
    handler.headers = {
        "Content-Length": str(len(raw)), "X-Forwarded-Proto": "https",
        "X-Forwarded-For": "192.0.2.10",
    }
    handler.rfile = BytesIO(raw)
    handler._send = Mock()
    return handler


def test_account_deletion_requires_an_authenticated_session(monkeypatch):
    module = endpoint()
    handler = request_handler(module, {
        "action": "delete_account", "currentPassword": "current-password",
        "confirmation": "FIÓK TÖRLÉSE",
    })
    deleter = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: None)
    monkeypatch.setattr(module, "delete_account", deleter)

    handler.do_POST()

    deleter.assert_not_called()
    assert handler._send.call_args.args[1] == 401


def test_account_deletion_uses_session_user_and_clears_cookie(monkeypatch):
    module = endpoint()
    handler = request_handler(module, {
        "action": "delete_account", "currentPassword": "current-password",
        "confirmation": "FIÓK TÖRLÉSE",
    })
    deleter = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "user-1"})
    monkeypatch.setattr(module, "delete_account", deleter)
    monkeypatch.setattr(module, "clear_cookie_header", lambda: "cleared-cookie")

    handler.do_POST()

    deleter.assert_called_once_with(
        "user-1", "current-password", "FIÓK TÖRLÉSE", "192.0.2.10"
    )
    assert handler._send.call_args.args[1:] == (200, "cleared-cookie")
    assert handler._send.call_args.args[0]["ok"] is True
