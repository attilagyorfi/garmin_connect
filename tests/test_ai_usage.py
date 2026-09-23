import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
import ai_usage


def test_default_daily_limit(monkeypatch):
    monkeypatch.delenv("HYBRID_AI_DAILY_TOKEN_LIMIT", raising=False)
    assert ai_usage.daily_token_limit() == 50_000


def test_daily_limit_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("HYBRID_AI_DAILY_TOKEN_LIMIT", "nem-szám")
    assert ai_usage.daily_token_limit() == 50_000


@pytest.mark.parametrize("value", ["", "0", "-1", "12.5", "NaN", "Infinity", "9007199254740992"])
def test_invalid_limit_falls_back_consistently_with_node(monkeypatch, value):
    monkeypatch.setenv("HYBRID_AI_DAILY_TOKEN_LIMIT", value)
    assert ai_usage.daily_token_limit() == 50_000


def test_summary_keeps_unknown_cost_and_database_local_date(monkeypatch):
    db = Mock()
    db.execute.return_value.fetchone.return_value = (1200, None, 2, "2026-09-11", 500)
    monkeypatch.setattr(ai_usage, "connect", lambda: db)
    result = ai_usage.usage_today("user-1")
    sql, params = db.execute.call_args.args
    assert params == ("user-1",)
    assert "NOW() AT TIME ZONE 'Europe/Budapest'" in sql
    assert "status IN" not in sql
    assert result["date"] == "2026-09-11"
    assert result["estimatedCostUsd"] is None
    assert result["usedTokens"] == 1200
    assert result["reservedTokens"] == 500
    db.close.assert_called_once()


def endpoint():
    spec = importlib.util.spec_from_file_location("ai_usage_endpoint", Path(__file__).parents[1] / "api" / "ai-usage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("method", ["do_POST", "do_PATCH", "do_DELETE", "do_PUT"])
def test_browsers_cannot_write_usage(method):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler._send = Mock()
    getattr(handler, method)()
    assert handler._send.call_args.args[1] == 405


def test_summary_requires_login_and_uses_authenticated_owner(monkeypatch):
    module = endpoint()
    handler = object.__new__(module.handler)
    handler.headers = {}
    handler._send = Mock()
    usage = Mock(return_value={"usedTokens": 10})
    monkeypatch.setattr(module, "usage_today", usage)
    monkeypatch.setattr(module, "is_ai_enabled", lambda: True)
    monkeypatch.setattr(module, "current_user", lambda _headers: None)
    handler.do_GET()
    usage.assert_not_called()
    assert handler._send.call_args.args[1] == 401
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "owner-123"})
    handler.do_GET()
    usage.assert_called_once_with("owner-123")
