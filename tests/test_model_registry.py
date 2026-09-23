from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from garmin_sync import demo_data
from api.retrain import authorized_cron
from model_registry import evaluate_retraining


def test_retraining_builds_auditable_candidate_for_new_history():
    result = evaluate_retraining(
        demo_data(365), {"feedback": {}}, [], today=date(2026, 9, 22)
    )
    assert result["status"] == "candidate_ready"
    assert result["due"] is True
    assert result["validation"]["samples"] >= 132
    assert len(result["validation"]["folds"]) == 3
    assert "artifact" in result["validation"]
    assert isinstance(result["promotion"]["promote"], bool)


def test_retraining_does_not_repeat_the_same_data_end():
    raw = demo_data(365)
    first = evaluate_retraining(
        raw, {"feedback": {}}, [], today=date(2026, 9, 22)
    )
    validation = first["validation"]
    versions = [
        {
            "id": 1,
            "trained_at": datetime(2026, 9, 22, tzinfo=timezone.utc),
            "data_end": validation["data_end"],
            "model_mae": validation["model_mae"],
            "active": bool(first["promotion"]["promote"]),
        }
    ]
    repeated = evaluate_retraining(
        raw, {"feedback": {}}, versions, today=date(2026, 9, 22)
    )
    assert repeated["status"] == "unchanged"
    assert repeated["due"] is False
    assert "már készült" in repeated["reasons"][0]


def test_retraining_stays_insufficient_for_short_history():
    result = evaluate_retraining(
        demo_data(45), {"feedback": {}}, [], today=date(2026, 9, 22)
    )
    assert result["status"] == "insufficient"
    assert result["validation"]["eligible"] is False
    assert "Legalább 132" in result["message"]


def test_recent_inactive_candidate_prevents_daily_retraining():
    raw = demo_data(365)
    first = evaluate_retraining(raw, {"feedback": {}}, [], today=date.today())
    candidate_end = date.fromisoformat(first["validation"]["data_end"])
    versions = [
        {
            "id": 2,
            "trained_at": datetime.now(timezone.utc),
            "data_end": str(candidate_end - timedelta(days=1)),
            "model_mae": first["validation"]["model_mae"] + 0.1,
            "active": False,
        },
        {
            "id": 1,
            "trained_at": datetime.now(timezone.utc) - timedelta(days=60),
            "data_end": str(candidate_end - timedelta(days=60)),
            "model_mae": first["validation"]["model_mae"],
            "active": True,
        },
    ]
    result = evaluate_retraining(raw, {"feedback": {}}, versions, today=date.today())
    assert result["status"] == "not_due"
    assert "nem tanít újra feleslegesen" in result["message"]


def test_cron_endpoint_requires_configured_matching_secret(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    assert authorized_cron({"Authorization": "Bearer anything"}) is False
    monkeypatch.setenv("CRON_SECRET", "scheduled-secret")
    assert authorized_cron({"Authorization": "Bearer scheduled-secret"}) is True
    assert authorized_cron({"Authorization": "Bearer wrong"}) is False
