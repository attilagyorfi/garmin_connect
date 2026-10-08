from datetime import date, datetime, timedelta, timezone

import pytest

import ai_usage
import assistant_actions
from assistant_actions import create_actions, decide_action, plan_handles

TODAY = date(2026, 10, 8)
PLAN = {"id": "plan-1", "date": "2026-10-09", "type": "Futás", "title": "Tempófutás", "duration": 50, "intensity": "közepes–magas",
        "rpe": 7, "purpose": "", "note": "", "matchedActivityId": "", "status": "planned", "updatedAt": "2026-10-07T10:00:00+00:00"}


class FakeDb:
    """Just enough of a psycopg connection for the action table."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        text = " ".join(sql.split())
        self.result = None
        if text.startswith("INSERT INTO hybrid_assistant_actions"):
            action_id, user_id, action_type, payload, summary, reason, before, expires_at = params
            import json
            self.rows[action_id] = {"user_id": user_id, "payload": json.loads(payload), "status": "pending", "before": json.loads(before),
                                    "expires_at": expires_at, "after": None}
        elif text.startswith("SELECT payload, status, expires_at, before_payload"):
            row = self.rows.get(params[0])
            self.result = (row["payload"], row["status"], row["expires_at"], row["before"]) if row and row["user_id"] == params[1] else None
        elif text.startswith("UPDATE hybrid_assistant_actions SET status = 'applying'"):
            row = self.rows.get(params[0])
            if row and row["status"] == "pending":
                row["status"] = "applying"
                self.result = (params[0],)
        elif text.startswith("UPDATE hybrid_assistant_actions SET status = 'applied'"):
            self.rows[params[1]].update(status="applied", after=params[0])
        elif text.startswith("UPDATE hybrid_assistant_actions SET status = 'rejected'"):
            self.rows[params[0]]["status"] = "rejected"
        elif text.startswith("UPDATE hybrid_assistant_actions SET status = 'expired'"):
            self.rows[params[0]]["status"] = "expired"
        elif text.startswith("UPDATE hybrid_assistant_actions SET status = 'pending'"):
            self.rows[params[0]]["status"] = "pending"
        return self

    def fetchone(self):
        return self.result

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture()
def world(monkeypatch):
    rows, state = {}, {"plans": [dict(PLAN)]}
    applied = []
    monkeypatch.setattr(assistant_actions, "connect", lambda: FakeDb(rows))
    monkeypatch.setattr(assistant_actions, "_initialize", lambda db: None)
    monkeypatch.setattr(assistant_actions, "load_state", lambda user_id: {"plans": [dict(item) for item in state["plans"]]})

    def apply(patch, user_id):
        applied.append(patch)
        if "deletePlan" in patch:
            state["plans"] = [item for item in state["plans"] if item["id"] != patch["deletePlan"]]
        else:
            state["plans"] = [item for item in state["plans"] if item["id"] != patch["plan"]["id"]] + [patch["plan"]]
        return {"plans": state["plans"]}

    monkeypatch.setattr(assistant_actions, "apply_patch", apply)
    return {"rows": rows, "state": state, "applied": applied}


def proposal(**overrides):
    return {"action": "upsert_plan", "target": "T1", "date": None, "type": None, "title": None, "duration": 35, "intensity": "könnyű",
            "rpe": 4, "purpose": None, "summary": "Könnyítés", "reason": "Alacsony HRV", **overrides}


def test_context_uses_handles_for_upcoming_plans_only():
    plans = [dict(PLAN), {**PLAN, "id": "old", "date": "2026-09-01"}, {**PLAN, "id": "far", "date": "2026-12-31"}]
    listing, handles = plan_handles(plans, TODAY)
    assert handles == {"T1": "plan-1"}
    assert listing[0]["jel"] == "T1" and "plan-1" not in str(listing)


def test_proposal_is_pending_and_nothing_is_written(world):
    created, problems = create_actions("u1", [proposal()], {"T1": "plan-1"})
    assert problems == [] and created[0]["status"] == "pending"
    assert created[0]["plan"]["id"] == "plan-1" and created[0]["plan"]["duration"] == 35 and created[0]["plan"]["title"] == "Tempófutás"
    assert world["applied"] == [] and world["state"]["plans"][0]["duration"] == 50


def test_unknown_handle_and_invalid_values_are_rejected(world):
    created, problems = create_actions("u1", [proposal(target="T7"), proposal(target=None, date="2026-10-10", type="Úszás", title="x")], {"T1": "plan-1"})
    assert created == [] and len(problems) == 2


def test_approval_applies_once_and_reject_never_applies(world):
    created, _ = create_actions("u1", [proposal()], {"T1": "plan-1"})
    assert decide_action("u1", created[0]["id"], "approve")["status"] == "applied"
    assert world["state"]["plans"][0]["duration"] == 35
    with pytest.raises(ValueError, match="már döntöttél"):
        decide_action("u1", created[0]["id"], "approve")
    other, _ = create_actions("u1", [proposal(target=None, date="2026-10-11", type="Mobilitás", title="Nyújtás")], {})
    assert decide_action("u1", other[0]["id"], "reject")["status"] == "rejected"
    assert len(world["applied"]) == 1


def test_stale_preview_never_overwrites_a_newer_edit(world):
    created, _ = create_actions("u1", [proposal()], {"T1": "plan-1"})
    world["state"]["plans"][0] = {**PLAN, "duration": 70, "updatedAt": "2026-10-08T06:00:00+00:00"}
    with pytest.raises(ValueError, match="megváltozott"):
        decide_action("u1", created[0]["id"], "approve")
    assert world["applied"] == []


def test_expired_and_foreign_actions_are_refused(world):
    created, _ = create_actions("u1", [proposal()], {"T1": "plan-1"})
    world["rows"][created[0]["id"]]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(ValueError, match="lejárt"):
        decide_action("u1", created[0]["id"], "approve")
    fresh, _ = create_actions("u1", [proposal()], {"T1": "plan-1"})
    with pytest.raises(ValueError, match="nem található"):
        decide_action("someone-else", fresh[0]["id"], "approve")
    with pytest.raises(ValueError):
        decide_action("u1", "not-a-uuid", "approve")


def test_cost_estimate_uses_all_token_kinds():
    numbers = {"input": 1_000_000, "output": 100_000, "cache_read": 1_000_000, "cache_write": 0}
    assert ai_usage.estimated_cost(numbers) == pytest.approx(2.0 + 1.0 + 0.2)
