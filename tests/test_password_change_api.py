import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock


def endpoint():
    spec = importlib.util.spec_from_file_location(
        "password_change_endpoint", Path(__file__).parents[1] / "api" / "auth.py"
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


def test_password_change_requires_an_authenticated_session(monkeypatch):
    module = endpoint()
    handler = request_handler(module, {
        "action": "change_password", "currentPassword": "current-password",
        "newPassword": "new-password-value",
    })
    changer = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: None)
    monkeypatch.setattr(module, "change_password", changer)

    handler.do_POST()

    changer.assert_not_called()
    assert handler._send.call_args.args[1] == 401


def test_password_change_uses_authenticated_user_and_clears_cookie(monkeypatch):
    module = endpoint()
    handler = request_handler(module, {
        "action": "change_password", "currentPassword": "current-password",
        "newPassword": "new-password-value",
    })
    changer = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "user-1"})
    monkeypatch.setattr(module, "change_password", changer)
    monkeypatch.setattr(module, "clear_cookie_header", lambda: "cleared-cookie")

    handler.do_POST()

    changer.assert_called_once_with(
        "user-1", "current-password", "new-password-value", "192.0.2.10"
    )
    assert handler._send.call_args.args[1:] == (200, "cleared-cookie")
    assert handler._send.call_args.args[0]["ok"] is True
