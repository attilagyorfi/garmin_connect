from unittest.mock import Mock

import pytest

import ai_usage
from auth_email import budget_alert_message


class FakeDb:
    """Records the transaction calls; queries return a neutral row."""

    def __init__(self):
        self.events = []

    def execute(self, sql, params=()):
        self.events.append(("sql", sql.strip().split()[0]))
        result = Mock()
        result.fetchone.return_value = (0, 0)
        return result

    def commit(self):
        self.events.append(("commit",))

    def rollback(self):
        self.events.append(("rollback",))

    def close(self):
        self.events.append(("close",))


@pytest.fixture
def ledger(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(ai_usage, "connect", lambda: db)
    monkeypatch.setattr(ai_usage, "_initialize", lambda _db: None)
    monkeypatch.setattr(ai_usage, "_today_totals", lambda _db, _user: (0, 0))
    sent = []
    monkeypatch.setattr(ai_usage, "_send_alert", lambda recipients, *alert: (db.events.append(("mail",)), sent.append((recipients, *alert))))
    return db, sent


@pytest.mark.parametrize("raw, expected", [("", 25.0), ("40", 40.0), ("12.5", 12.5), ("-3", 25.0), ("sok", 25.0)])
def test_monthly_budget_comes_from_the_environment(monkeypatch, raw, expected):
    monkeypatch.setenv("AI_MONTHLY_BUDGET_USD", raw)
    assert ai_usage.monthly_budget_usd() == expected


def test_over_budget_refuses_and_alerts_after_commit(ledger, monkeypatch):
    db, sent = ledger
    monkeypatch.setattr(ai_usage, "_month_spend", lambda _db: 24.99)
    monkeypatch.setattr(ai_usage, "_check_alerts", lambda _db: (100, "2026-10", 25.01, 25.0, ["admin@example.test"]))
    with pytest.raises(ai_usage.BudgetExceededError, match="hónap végéig szünetel"):
        ai_usage.reserve("u1", "answer", "claude-sonnet-5-5")
    assert issubclass(ai_usage.BudgetExceededError, ai_usage.UsageLimitError)
    assert sent == [(["admin@example.test"], 100, "2026-10", 25.01, 25.0)]
    assert db.events.index(("commit",)) < db.events.index(("mail",))
    assert not any(event == ("sql", "INSERT") for event in db.events)  # no reservation was stored


def test_within_budget_reserves_without_alert(ledger, monkeypatch):
    db, sent = ledger
    monkeypatch.setattr(ai_usage, "_month_spend", lambda _db: 3.0)
    assert ai_usage.reserve("u1", "answer", "claude-sonnet-5-5")
    assert sent == [] and ("sql", "INSERT") in db.events


def test_settle_sends_the_threshold_alert_once_claimed(ledger, monkeypatch):
    db, sent = ledger
    monkeypatch.setattr(ai_usage, "_check_alerts", lambda _db: (80, "2026-10", 20.5, 25.0, ["admin@example.test"]))
    ai_usage.settle("g1", {"input": 1000, "output": 200, "cache_read": 0, "cache_write": 0})
    assert sent == [(["admin@example.test"], 80, "2026-10", 20.5, 25.0)]
    assert db.events.index(("commit",)) < db.events.index(("mail",))


@pytest.mark.parametrize("spent, level", [(10.0, None), (20.0, 80), (24.9, 80), (25.0, 100), (31.0, 100)])
def test_alert_levels(monkeypatch, spent, level):
    claimed = []
    monkeypatch.setattr(ai_usage, "monthly_budget_usd", lambda: 25.0)
    monkeypatch.setattr(ai_usage, "_month_spend", lambda _db: spent)
    monkeypatch.setattr(ai_usage, "_claim_alert", lambda _db, lvl, *_rest: claimed.append(lvl) or "2026-10")
    monkeypatch.setattr(ai_usage, "_admin_recipients", lambda _db: ["admin@example.test"])
    alert = ai_usage._check_alerts(object())
    assert (alert[0] if alert else None) == level
    if level == 100:
        assert claimed == [100, 80]  # jumping straight past 80% sends a single e-mail


def test_already_claimed_alert_sends_nothing(monkeypatch):
    monkeypatch.setattr(ai_usage, "monthly_budget_usd", lambda: 25.0)
    monkeypatch.setattr(ai_usage, "_month_spend", lambda _db: 21.0)
    monkeypatch.setattr(ai_usage, "_claim_alert", lambda *_args: None)
    assert ai_usage._check_alerts(object()) is None


def test_alert_message_has_totals_only():
    subject, text, markup = budget_alert_message(100, "2026-10", 25.2, 25.0)
    assert "szünetel" in subject and "25.20 USD" in text and "AI_MONTHLY_BUDGET_USD" in text
    assert "@" not in text and "<script" not in markup
