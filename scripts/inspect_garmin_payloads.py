"""Print the *shape* of Garmin profile-metric payloads for a local user, without any values.

Use it to check the defensive parsers in garmin_profile.py against a real account:

    python scripts/inspect_garmin_payloads.py EMAIL

The user must be registered in the local app and have a connected Garmin account. Output contains
only keys, types and list lengths, plus which normalized fields the parsers could fill.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(ROOT / ".env.local", override=False)

from cloud_cache import connect  # noqa: E402
from cloud_sync_job import _authenticated_sync  # noqa: E402
from garmin_profile import fetch_profile_metrics, is_strength_activity  # noqa: E402


def shape(value: Any, depth: int = 0, max_depth: int = 4) -> Any:
    if isinstance(value, dict):
        return {key: shape(item, depth + 1) for key, item in value.items()} if depth < max_depth else "dict"
    if isinstance(value, list):
        return [f"list[{len(value)}]", shape(value[0], depth + 1)] if value else "list[0]"
    return type(value).__name__


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    db = connect()
    try:
        row = db.execute("SELECT id FROM hybrid_users WHERE email = %s", (sys.argv[1].strip().lower(),)).fetchone()
    finally:
        db.close()
    if not row:
        raise SystemExit("Nincs ilyen regisztrált helyi felhasználó.")
    sync = _authenticated_sync(str(row[0]), "inspect")
    client, today = sync.client, date.today()
    iso, year_ago = today.isoformat(), (today - timedelta(days=365)).isoformat()
    activities = client.get_activities(0, 50)
    strength = next((item for item in activities if is_strength_activity(item)), None)
    calls = {
        "user_profile": lambda: client.get_user_profile(),
        "max_metrics_range": lambda: client.get_max_metrics_range(year_ago, iso),
        "fitness_age": lambda: client.get_fitnessage_data(iso),
        "body_composition": lambda: client.get_body_composition(year_ago, iso),
        "weekly_intensity_minutes": lambda: client.get_weekly_intensity_minutes((today - timedelta(days=83)).isoformat(), iso),
        "daily_steps": lambda: client.get_daily_steps((today - timedelta(days=27)).isoformat(), iso),
        "personal_record": lambda: client.get_personal_record(),
        "race_predictions": lambda: client.get_race_predictions(),
        "endurance_score": lambda: client.get_endurance_score(iso),
    }
    if strength:
        calls["exercise_sets"] = lambda: client.get_activity_exercise_sets(strength["activityId"])
    for name, call in calls.items():
        try:
            print(f"\n== {name}\n{shape(call())}")
        except Exception as exc:  # noqa: BLE001 - diagnostic output only
            print(f"\n== {name}\nHIBA: {type(exc).__name__}")
    errors: list[str] = []
    profile = fetch_profile_metrics(client, sync._safe_call, errors, today)
    print("\n== feldolgozás")
    print("források:", profile["sources"])
    print("kitöltött mezők:", sorted(key for key, value in profile.items() if value not in (None, [], {}) and key not in ("sources", "fetched_at", "version")))
    print("üres mezők:", sorted(key for key, value in profile.items() if value in (None, [], {})))
    print("hibák:", errors)


if __name__ == "__main__":
    main()
