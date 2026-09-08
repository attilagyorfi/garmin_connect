import pytest

import assistant_actions


PLAN = {
    "id": "plan-1", "date": "2026-09-10", "type": "Futás",
    "title": "Könnyű futás", "duration": 45, "intensity": "könnyű",
    "rpe": 4, "purpose": "Alapozás", "note": "",
}


@pytest.fixture(autouse=True)
def state(monkeypatch):
    monkeypatch.setattr(assistant_actions, "load_state", lambda user_id: {"plans": [PLAN]})


def test_existing_plan_update_is_normalized_and_keeps_id():
    action_type, payload, summary, _, before = assistant_actions._normalize({
        "action": "upsert_plan", "plan": {**PLAN, "duration": 60},
        "summary": "Futás hosszabbítása", "reason": "Felhasználói kérés",
    }, "user-1")
    assert action_type == "upsert_plan"
    assert payload["plan"]["id"] == "plan-1"
    assert payload["plan"]["duration"] == 60
    assert summary == "Futás hosszabbítása"
    assert before == PLAN


def test_unknown_existing_plan_cannot_be_modified():
    with pytest.raises(ValueError, match="nem található"):
        assistant_actions._normalize({
            "action": "upsert_plan", "plan": {**PLAN, "id": "plan-other"},
        }, "user-1")


def test_delete_requires_users_existing_plan():
    action_type, payload, _, _, before = assistant_actions._normalize({
        "action": "delete_plan", "targetPlanId": "plan-1",
    }, "user-1")
    assert action_type == "delete_plan"
    assert payload == {"deletePlan": "plan-1"}
    assert before == PLAN
