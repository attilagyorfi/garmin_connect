import importlib.util
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock


def endpoint():
    spec = importlib.util.spec_from_file_location(
        "state_export_endpoint", Path(__file__).parents[1] / "api" / "state.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_requires_an_authenticated_user(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler.path = "/api/state?export=1"
    handler._send = Mock()
    builder = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: None)
    monkeypatch.setattr(module, "build_user_export", builder)

    handler.do_GET()

    builder.assert_not_called()
    assert handler._send.call_args.args[1] == 401


def test_export_uses_only_the_current_authenticated_user(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler.path = "/api/state?export=1"
    handler._send = Mock()
    user = {"id": "user-1", "email": "sportolo@example.com"}
    monkeypatch.setattr(module, "current_user", lambda _headers: user)
    builder = Mock(return_value={"exportVersion": 1})
    monkeypatch.setattr(module, "build_user_export", builder)

    handler.do_GET()

    builder.assert_called_once_with(user)
    assert handler._send.call_args.args == ({"exportVersion": 1},)
    assert handler._send.call_args.kwargs == {"attachment": True}


def test_regular_state_request_does_not_build_an_export(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler.path = "/api/state"
    handler._send = Mock()
    user = {"id": "user-1", "email": "sportolo@example.com"}
    monkeypatch.setattr(module, "current_user", lambda _headers: user)
    monkeypatch.setattr(module, "load_state", lambda user_id: {"owner": user_id})
    builder = Mock()
    monkeypatch.setattr(module, "build_user_export", builder)

    handler.do_GET()

    builder.assert_not_called()
    handler._send.assert_called_once_with({"owner": "user-1"})


def test_export_response_is_a_non_cacheable_json_attachment():
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.wfile = BytesIO()
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()

    handler._send({"exportVersion": 1}, attachment=True)

    headers = dict(call.args for call in handler.send_header.call_args_list)
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "private, no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Disposition"].startswith('attachment; filename="hybrid-athlete-adatexport-')
    assert b'"exportVersion": 1' in handler.wfile.getvalue()
