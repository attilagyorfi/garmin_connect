import importlib.util
from pathlib import Path
from unittest.mock import Mock


def endpoint():
    spec = importlib.util.spec_from_file_location(
        "admin_endpoint", Path(__file__).parents[1] / "api" / "admin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_non_admin_cannot_read_access_list(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send = Mock()
    listing = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "member-1", "role": "member"})
    monkeypatch.setattr(module, "list_access_admin", listing)
    handler.do_GET()
    listing.assert_not_called()
    assert handler._send.call_args.args[1] == 403


def test_admin_can_suspend_member_through_endpoint(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send = Mock()
    handler._payload = lambda: {
        "action": "set_user_access", "id": "member-1", "status": "suspended"
    }
    change = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "admin-1", "role": "admin"})
    monkeypatch.setattr(module, "set_user_access", change)
    handler.do_POST()
    change.assert_called_once_with("admin-1", "member-1", "suspended")
    assert handler._send.call_args.args == ({"ok": True},)
