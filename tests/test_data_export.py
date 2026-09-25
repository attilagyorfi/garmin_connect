from data_export import build_user_export


def test_export_is_scoped_and_excludes_credentials(monkeypatch):
    monkeypatch.setattr(
        "data_export.load_state",
        lambda user_id: {
            "profile": {"name": "Teszt Sportoló"},
            "accent": "teal",
            "plans": [{"id": "plan-1"}],
            "checkins": {"2026-09-25": {"fatigue": 2}},
            "feedback": {"activity-1": {"rpe": 6}},
            "assistant": {"memoryEnabled": False, "messages": []},
        } if user_id == "user-1" else (_ for _ in ()).throw(AssertionError("wrong user")),
    )
    def load_export_state(user_id, key):
        assert user_id == "user-1"
        if key == "dashboard_snapshot_v1":
            return {"sessions": [{"id": "activity-1"}]}
        if key == "garmin_sync_job_v2":
            return {"status": "completed", "progress": 100, "secret_internal_field": "nem exportálható"}
        raise AssertionError("unexpected state key")

    monkeypatch.setattr("data_export.load_user_json", load_export_state)

    result = build_user_export({"id": "user-1", "email": "sportolo@example.com", "name": "Teszt Sportoló", "role": "member"})

    assert result["account"] == {"email": "sportolo@example.com", "name": "Teszt Sportoló", "role": "member"}
    assert result["planning"]["plans"] == [{"id": "plan-1"}]
    assert result["garmin"]["syncStatus"] == {"status": "completed", "progress": 100}
    serialized = repr(result).lower()
    assert "password_hash" not in serialized
    assert "encrypted_tokenstore" not in serialized
    assert "session-token" not in serialized


def test_export_marks_missing_dashboard_without_inventing_data(monkeypatch):
    monkeypatch.setattr("data_export.load_state", lambda _user_id: {})
    monkeypatch.setattr("data_export.load_user_json", lambda _user_id, _key: None)

    result = build_user_export({"id": "user-1", "email": "sportolo@example.com", "name": "Sportoló"})

    assert result["garmin"]["dashboard"] is None
    assert result["garmin"]["syncStatus"]["status"] == "idle"
