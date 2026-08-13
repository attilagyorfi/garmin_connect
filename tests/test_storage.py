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
    db.save_feedback("42", rpe=8, feeling="planned", focus="lower body", volume_kg=5000)
    assert db.list_feedback()["42"]["rpe"] == 8
