from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from cloud_sync_job import advance_sync, sync_status
from garmin_sync import GarminSyncError


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            self._send(sync_status(user["id"]))
        except Exception:
            self._send({"error": "A szinkron állapota jelenleg nem tölthető be."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size)) if size else {}
            body, status = advance_sync(user["id"], payload.get("run_id"))
        except GarminSyncError as exc:
            body, status = {"error": str(exc)}, 409
        except Exception:
            body, status = {"error": "A Garmin-szinkron váratlan hiba miatt megszakadt."}, 500
        self._send(body, status)
