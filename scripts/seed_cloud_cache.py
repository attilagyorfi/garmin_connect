"""Seed Neon with the existing local Garmin cache without logging health data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / "frontend" / ".env.local", override=False)
load_dotenv(ROOT / ".env.local", override=False)

from cloud_cache import save_json  # noqa: E402
from cloud_dashboard import DASHBOARD_KEY, RAW_CACHE_KEY  # noqa: E402
from dashboard_api import build_dashboard_payload  # noqa: E402


def main() -> None:
    source = ROOT / "data" / "garmin_cache.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="hybrid-seed-") as directory:
        cache_dir = Path(directory)
        (cache_dir / "garmin_cache.json").write_text(
            json.dumps(raw, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        dashboard = build_dashboard_payload(cache_dir)
    save_json(RAW_CACHE_KEY, raw)
    save_json(DASHBOARD_KEY, dashboard)
    print(
        f"Neon seed kész: {len(raw.get('activities', []))} aktivitás, "
        f"{len(raw.get('wellness', []))} wellness nap."
    )


if __name__ == "__main__":
    main()
