from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from cloud_dashboard import dashboard_snapshot


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                body, status = {"error": "A művelethez bejelentkezés szükséges."}, 401
            else:
                body, status = dashboard_snapshot(user["id"]), 200
        except Exception:
            body, status = {"error": "A Garmin-adatok jelenleg nem tölthetők be."}, 503
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
