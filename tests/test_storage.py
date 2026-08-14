from storage import Database, SCHEMA_VERSION


def test_database_initialization_and_checkin(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    db.save_checkin("2026-08-13", soreness=2, stress=3, motivation=4, fatigue=2, pain="none", illness=False, note="ok")
    assert db.get_checkin("2026-08-13")["motivation"] == 4
    with db.connect() as connection:
        version = connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    assert version == str(SCHEMA_VERSION)


def test_session_feedback_roundtrip(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    db.save_feedback("42", rpe=8, feeling="planned", focus="lower body", volume_kg=5000, stability_min=12, single_leg_min=8)
    assert db.list_feedback()["42"]["rpe"] == 8
    assert db.list_feedback()["42"]["stability_min"] == 12


def test_generated_snapshots_roundtrip(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    db.save_json("daily_recommendations", "day", "2026-08-14", {"type": "Zone 2", "confidence": "magas"})
    rows = db.list_json("daily_recommendations", "day")
    assert rows == [{"day": "2026-08-14", "type": "Zone 2", "confidence": "magas"}]


def test_goal_and_training_plan_crud(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    goal_id = db.save_goal(name="Mátra 30", event_date="2026-10-01", event_type="terepfutás", weekly_hours=7, cardio_target_pct=65)
    assert db.list_goals()[0]["weekly_hours"] == 7
    db.save_goal(goal_id, name="Mátra 35", event_date="2026-10-01", event_type="terepfutás", weekly_hours=8)
    assert db.list_goals()[0]["name"] == "Mátra 35"

    plan_id = db.save_plan(planned_date="2026-08-15", modality="Cardio", duration_min=60, intensity="közepes", purpose="Zone 2", target_rpe=5)
    db.match_plan(plan_id, "123")
    assert db.list_plans()[0]["matched_activity_id"] == "123"
    db.delete_plan(plan_id)
    db.delete_goal(goal_id)
    assert db.list_plans() == []
    assert db.list_goals() == []


def test_bulk_plan_insert_is_available_for_weekly_templates(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    ids = db.save_plans([
        {"planned_date": "2026-08-17", "modality": "Cardio", "duration_min": 45, "intensity": "közepes", "purpose": "Zone 2", "target_rpe": 5},
        {"planned_date": "2026-08-18", "modality": "Strength / Functional", "duration_min": 40, "intensity": "közepes", "purpose": "Erő", "target_rpe": 6},
    ])
    assert len(ids) == 2
    assert len(db.list_plans()) == 2


def test_model_versions_keep_one_active_artifact(tmp_path):
    db = Database(tmp_path / "training.sqlite3")
    first = db.save_model_version({"data_start":"2025-01-01", "data_end":"2026-01-01", "samples":300, "model_mae":.8, "artifact":{"coefficients":[1]}}, activate=True)
    second = db.save_model_version({"data_start":"2025-02-01", "data_end":"2026-02-01", "samples":330, "model_mae":.7, "artifact":{"coefficients":[2]}}, activate=True)
    versions = db.list_model_versions()
    assert first != second
    assert sum(item["active"] for item in versions) == 1
    assert next(item for item in versions if item["active"])["artifact"]["coefficients"] == [2]
    db.activate_model_version(first)
    assert next(item for item in db.list_model_versions() if item["active"])["id"] == first
