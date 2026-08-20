import pytest

import user_state


@pytest.fixture
def memory_store(monkeypatch):
    stored = {}
    monkeypatch.setattr(user_state, "load_json", lambda key: stored.get(key))
    monkeypatch.setattr(user_state, "save_json", lambda key, value: stored.update({key: value}))
    return stored


def test_profile_accent_checkin_and_feedback_are_merged(memory_store):
    state = user_state.apply_patch({"profile": {
        "name": "Attila", "experience": "középhaladó", "goal": "Hibrid teljesítmény",
        "weeklyHours": 9, "strengthRatio": 35, "trainingDays": ["H", "Sze", "P"],
        "restDay": "V", "preference": "kiegyensúlyozott",
    }})
    assert state["profile"]["weeklyHours"] == 9

    user_state.apply_patch({"accent": "blue"})
    user_state.apply_patch({"checkin": {"date": "2026-08-20", "value": {
        "soreness": 3, "fatigue": 4, "motivation": 2, "stress": 3,
        "pain": False, "illness": False, "note": "Fáradt", "savedAt": "2026-08-20T08:00:00Z",
    }}})
    final = user_state.apply_patch({"feedback": {"activityId": "4242", "value": {
        "rpe": 8, "feeling": "nehéz", "note": "Erős befejezés",
    }}})

    assert final["accent"] == "blue"
    assert final["checkins"]["2026-08-20"]["fatigue"] == 4
    assert final["feedback"]["4242"]["rpe"] == 8
    assert final["profile"]["name"] == "Attila"


@pytest.mark.parametrize("patch", [
    {"accent": "script"},
    {"checkin": {"date": "nem-dátum", "value": {}}},
    {"feedback": {"activityId": "", "value": {}}},
    {"profile": {"experience": "profi"}},
    {"plan": {"date": "2026-08-24", "type": "Úszás"}},
    {"deletePlan": ""},
])
def test_invalid_state_is_rejected(memory_store, patch):
    with pytest.raises((ValueError, TypeError)):
        user_state.apply_patch(patch)


def test_local_history_can_be_imported_once(memory_store):
    state = user_state.apply_patch({
        "profile": {"name": "Attila", "experience": "haladó", "goal": "Hegyi állóképesség", "restDay": "V", "preference": "teljesítmény"},
        "accent": "teal",
        "checkins": {"2026-08-19": {"fatigue": 3}},
        "feedbackMap": {"activity-1": {"rpe": 7, "feeling": "rendben"}},
    })
    assert state["checkins"]["2026-08-19"]["fatigue"] == 3
    assert state["feedback"]["activity-1"]["rpe"] == 7


def test_training_plan_full_crud_and_bulk_template(memory_store):
    created = user_state.apply_patch({"plan": {
        "id": "plan-1", "date": "2026-08-24", "type": "Futás", "title": "Zone 2 futás",
        "duration": 55, "intensity": "könnyű", "rpe": 4, "purpose": "Aerob alap", "matchedActivityId": "garmin-42",
    }})
    assert created["plans"][0]["title"] == "Zone 2 futás"
    assert created["plans"][0]["matchedActivityId"] == "garmin-42"

    updated = user_state.apply_patch({"plan": {
        **created["plans"][0], "duration": 65, "note": "Sík útvonal",
    }})
    assert len(updated["plans"]) == 1
    assert updated["plans"][0]["duration"] == 65

    templated = user_state.apply_patch({"plans": [{
        "id": "template-2026-08-25", "date": "2026-08-25", "type": "Erő",
        "title": "Teljes testes erő", "duration": 45, "intensity": "közepes", "rpe": 6,
    }]})
    assert len(templated["plans"]) == 2

    deleted = user_state.apply_patch({"deletePlan": "plan-1"})
    assert [plan["id"] for plan in deleted["plans"]] == ["template-2026-08-25"]
