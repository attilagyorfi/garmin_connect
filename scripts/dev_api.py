"""Local development server for every Vercel function under api/.

Serves /api/<name> with the same handler classes Vercel runs, so the Vite dev server
(which proxies /api to 127.0.0.1:8765) works end to end with a local Postgres.

    python scripts/dev_api.py                      # serve on 127.0.0.1:8765
    python scripts/dev_api.py --seed-demo EMAIL    # store demo dashboard data for a registered user

Configuration comes from the git-ignored .env.local (DATABASE_URL, GARMIN_CREDENTIALS_KEY).
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(ROOT / ".env.local", override=False)

ENDPOINTS = ("admin", "assistant", "auth", "dashboard", "garmin", "sessions", "state", "sync")
HANDLERS = {name: importlib.import_module(f"api.{name}").handler for name in ENDPOINTS}


class Router(BaseHTTPRequestHandler):
    """Delegates each request to the matching Vercel handler class."""

    def _dispatch(self, method: str) -> None:
        name = urlparse(self.path).path.removeprefix("/api/").strip("/")
        target = HANDLERS.get(name)
        if target is None:
            self.send_error(404)
            return
        if not hasattr(target, f"do_{method}"):
            self.send_error(405)
            return
        # Plain-http localhost: lets auth_store issue the session cookie without the Secure flag.
        if not self.headers.get("X-Forwarded-Proto"):
            self.headers["X-Forwarded-Proto"] = "http"
        self.__class__ = target
        try:
            getattr(target, f"do_{method}")(self)
        finally:
            self.__class__ = Router

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")


def seed_demo(email: str) -> None:
    from cloud_cache import connect, save_user_json
    from cloud_dashboard import DASHBOARD_KEY
    from dashboard_api import build_dashboard_payload

    db = connect()
    try:
        row = db.execute("SELECT id FROM hybrid_users WHERE email = %s", (email.strip().lower(),)).fetchone()
    finally:
        db.close()
    if not row:
        raise SystemExit(f"Nincs ilyen regisztrált felhasználó: {email}")
    with tempfile.TemporaryDirectory(prefix="hybrid-demo-") as directory:
        dashboard = build_dashboard_payload(directory)
    save_user_json(str(row[0]), DASHBOARD_KEY, dashboard)
    print(f"Demó dashboard elmentve: {email} ({len(dashboard['sessions'])} edzés)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_API_PORT", "8765")))
    parser.add_argument("--seed-demo", metavar="EMAIL")
    args = parser.parse_args()
    if args.seed_demo:
        seed_demo(args.seed_demo)
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Router)
    print(f"Dev API: http://127.0.0.1:{args.port}/api/{{{','.join(ENDPOINTS)}}}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
