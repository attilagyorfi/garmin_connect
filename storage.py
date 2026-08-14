"""Versioned SQLite persistence for manual and derived training data."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 3


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS garmin_activities (
                    activity_id TEXT PRIMARY KEY, activity_date TEXT NOT NULL,
                    payload_json TEXT NOT NULL, synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_wellness (
                    day TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    day TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                    calculated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wellness_checkins (
                    day TEXT PRIMARY KEY, soreness INTEGER NOT NULL CHECK(soreness BETWEEN 1 AND 5),
                    stress INTEGER NOT NULL CHECK(stress BETWEEN 1 AND 5),
                    motivation INTEGER NOT NULL CHECK(motivation BETWEEN 1 AND 5),
                    fatigue INTEGER NOT NULL CHECK(fatigue BETWEEN 1 AND 5),
                    pain TEXT NOT NULL CHECK(pain IN ('none','mild','significant')),
                    illness INTEGER NOT NULL CHECK(illness IN (0,1)), note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS session_feedback (
                    activity_id TEXT PRIMARY KEY, rpe INTEGER NOT NULL CHECK(rpe BETWEEN 1 AND 10),
                    feeling TEXT NOT NULL, focus TEXT NOT NULL DEFAULT '', sets_count INTEGER,
                    reps_count INTEGER, volume_kg REAL, pack_kg REAL, note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS goals_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, event_date TEXT,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS training_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, planned_date TEXT NOT NULL,
                    modality TEXT NOT NULL, duration_min INTEGER NOT NULL,
                    intensity TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT '',
                    target_rpe INTEGER, note TEXT NOT NULL DEFAULT '',
                    matched_activity_id TEXT, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_recommendations (
                    day TEXT PRIMARY KEY, payload_json TEXT NOT NULL, generated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS weekly_summaries (
                    week_start TEXT PRIMARY KEY, payload_json TEXT NOT NULL, generated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    id INTEGER PRIMARY KEY CHECK(id=1), last_attempt TEXT, last_success TEXT,
                    status TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS data_quality_flags (
                    day TEXT NOT NULL, code TEXT NOT NULL, severity TEXT NOT NULL,
                    detail TEXT NOT NULL, PRIMARY KEY(day, code)
                );
                """
            )
            feedback_columns = {row[1] for row in db.execute("PRAGMA table_info(session_feedback)").fetchall()}
            for column in ("stability_min", "single_leg_min"):
                if column not in feedback_columns:
                    db.execute(f"ALTER TABLE session_feedback ADD COLUMN {column} INTEGER")
            db.execute(
                "INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version',?)",
                (str(SCHEMA_VERSION),),
            )

    def save_checkin(self, day: date | str, **values: Any) -> None:
        stamp = datetime.now().astimezone().isoformat()
        with self.connect() as db:
            db.execute(
                """INSERT INTO wellness_checkins
                (day,soreness,stress,motivation,fatigue,pain,illness,note,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET
                soreness=excluded.soreness, stress=excluded.stress,
                motivation=excluded.motivation, fatigue=excluded.fatigue,
                pain=excluded.pain, illness=excluded.illness, note=excluded.note,
                updated_at=excluded.updated_at""",
                (str(day), values["soreness"], values["stress"], values["motivation"],
                 values["fatigue"], values["pain"], int(values["illness"]),
                 values.get("note", ""), stamp),
            )

    def get_checkin(self, day: date | str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM wellness_checkins WHERE day=?", (str(day),)).fetchone()
        return dict(row) if row else None

    def list_checkins(self) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM wellness_checkins ORDER BY day").fetchall()
        return {row["day"]: dict(row) for row in rows}

    def save_feedback(self, activity_id: str | int, **values: Any) -> None:
        stamp = datetime.now().astimezone().isoformat()
        with self.connect() as db:
            db.execute(
                """INSERT INTO session_feedback
                (activity_id,rpe,feeling,focus,sets_count,reps_count,volume_kg,pack_kg,stability_min,single_leg_min,note,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET
                rpe=excluded.rpe, feeling=excluded.feeling, focus=excluded.focus,
                sets_count=excluded.sets_count, reps_count=excluded.reps_count,
                volume_kg=excluded.volume_kg, pack_kg=excluded.pack_kg,
                stability_min=excluded.stability_min, single_leg_min=excluded.single_leg_min,
                note=excluded.note, updated_at=excluded.updated_at""",
                (str(activity_id), values["rpe"], values["feeling"], values.get("focus", ""),
                 values.get("sets_count"), values.get("reps_count"), values.get("volume_kg"),
                 values.get("pack_kg"), values.get("stability_min"), values.get("single_leg_min"), values.get("note", ""), stamp),
            )

    def list_feedback(self) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM session_feedback").fetchall()
        return {row["activity_id"]: dict(row) for row in rows}

    def save_goal(self, goal_id: int | None = None, **values: Any) -> int:
        payload = {key: value for key, value in values.items() if key not in {"name", "event_date", "event_type"}}
        with self.connect() as db:
            if goal_id is None:
                cursor = db.execute(
                    "INSERT INTO goals_events(name,event_date,event_type,payload_json) VALUES(?,?,?,?)",
                    (values["name"], values.get("event_date"), values["event_type"], json.dumps(payload, ensure_ascii=False)),
                )
                return int(cursor.lastrowid)
            db.execute(
                "UPDATE goals_events SET name=?,event_date=?,event_type=?,payload_json=? WHERE id=?",
                (values["name"], values.get("event_date"), values["event_type"], json.dumps(payload, ensure_ascii=False), goal_id),
            )
            return goal_id

    def list_goals(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM goals_events ORDER BY event_date IS NULL,event_date,id").fetchall()
        return [{"id": row["id"], "name": row["name"], "event_date": row["event_date"], "event_type": row["event_type"], **json.loads(row["payload_json"])} for row in rows]

    def delete_goal(self, goal_id: int) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM goals_events WHERE id=?", (goal_id,))

    def save_plan(self, plan_id: int | None = None, **values: Any) -> int:
        record = (
            str(values["planned_date"]), values["modality"], int(values["duration_min"]),
            values["intensity"], values.get("purpose", ""), values.get("target_rpe"),
            values.get("note", ""), values.get("matched_activity_id"), datetime.now().astimezone().isoformat(),
        )
        with self.connect() as db:
            if plan_id is None:
                cursor = db.execute(
                    """INSERT INTO training_plans
                    (planned_date,modality,duration_min,intensity,purpose,target_rpe,note,matched_activity_id,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""", record,
                )
                return int(cursor.lastrowid)
            db.execute(
                """UPDATE training_plans SET planned_date=?,modality=?,duration_min=?,intensity=?,
                purpose=?,target_rpe=?,note=?,matched_activity_id=?,updated_at=? WHERE id=?""",
                (*record, plan_id),
            )
            return plan_id

    def list_plans(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM training_plans ORDER BY planned_date,id").fetchall()
        return [dict(row) for row in rows]

    def save_plans(self, plans: list[dict[str, Any]]) -> list[int]:
        """Insert a set of plans atomically."""
        stamp = datetime.now().astimezone().isoformat()
        ids: list[int] = []
        with self.connect() as db:
            for values in plans:
                cursor = db.execute(
                    """INSERT INTO training_plans
                    (planned_date,modality,duration_min,intensity,purpose,target_rpe,note,matched_activity_id,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (str(values["planned_date"]), values["modality"], int(values["duration_min"]), values["intensity"], values.get("purpose", ""), values.get("target_rpe"), values.get("note", ""), values.get("matched_activity_id"), stamp),
                )
                ids.append(int(cursor.lastrowid))
        return ids

    def match_plan(self, plan_id: int, activity_id: str | None) -> None:
        with self.connect() as db:
            db.execute("UPDATE training_plans SET matched_activity_id=?,updated_at=? WHERE id=?", (activity_id, datetime.now().astimezone().isoformat(), plan_id))

    def delete_plan(self, plan_id: int) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM training_plans WHERE id=?", (plan_id,))

    def save_json(self, table: str, key_column: str, key: str, payload: dict[str, Any]) -> None:
        allowed = {
            ("daily_recommendations", "day", "generated_at"),
            ("weekly_summaries", "week_start", "generated_at"),
            ("daily_metrics", "day", "calculated_at"),
        }
        match = next((item for item in allowed if item[0] == table and item[1] == key_column), None)
        if not match:
            raise ValueError("Unsupported persistence target")
        stamp_column = match[2]
        with self.connect() as db:
            db.execute(
                f"INSERT OR REPLACE INTO {table}({key_column},payload_json,{stamp_column}) VALUES(?,?,?)",
                (key, json.dumps(payload, ensure_ascii=False), datetime.now().astimezone().isoformat()),
            )

    def list_json(self, table: str, key_column: str) -> list[dict[str, Any]]:
        allowed = {("daily_recommendations", "day"), ("weekly_summaries", "week_start"), ("daily_metrics", "day")}
        if (table, key_column) not in allowed:
            raise ValueError("Unsupported persistence target")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT {key_column}, payload_json FROM {table} ORDER BY {key_column} DESC"
            ).fetchall()
        return [{key_column: row[key_column], **json.loads(row["payload_json"])} for row in rows]
