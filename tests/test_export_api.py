import importlib.util
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock


def endpoint():
    spec = importlib.util.spec_from_file_location(
        "export_endpoint", Path(__file__).parents[1] / "api" / "export.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_requires_an_authenticated_user(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send_json = Mock()
    builder = Mock()
    monkeypatch.setattr(module, "current_user", lambda _headers: None)
    monkeypatch.setattr(module, "build_user_export", builder)

    handler.do_GET()

    builder.assert_not_called()
    assert handler._send_json.call_args.args[1] == 401


def test_export_uses_only_the_current_authenticated_user(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send_json = Mock()
    user = {"id": "user-1", "email": "sportolo@example.com"}
    monkeypatch.setattr(module, "current_user", lambda _headers: user)
    builder = Mock(return_value={"exportVersion": 1})
    monkeypatch.setattr(module, "build_user_export", builder)

    handler.do_GET()

    builder.assert_called_once_with(user)
    assert handler._send_json.call_args.args == ({"exportVersion": 1},)
    assert handler._send_json.call_args.kwargs == {"attachment": True}


def test_export_response_is_a_non_cacheable_json_attachment():
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.wfile = BytesIO()
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()

    handler._send_json({"exportVersion": 1}, attachment=True)

    headers = dict(call.args for call in handler.send_header.call_args_list)
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "private, no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Disposition"].startswith('attachment; filename="hybrid-athlete-adatexport-')
    assert b'"exportVersion": 1' in handler.wfile.getvalue()
