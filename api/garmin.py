from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from garmin_connection import connection_status, delete_connection, save_connection


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _user(self) -> dict | None:
        user = current_user(self.headers)
        if not user:
            self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
        return user

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if user:
                self._send(connection_status(user["id"]))
        except Exception:
            self._send({"error": "A Garmin-kapcsolat állapota jelenleg nem tölthető be."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if not user:
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 16_384:
                raise ValueError("Érvénytelen kérésméret.")
            payload = json.loads(self.rfile.read(size))
            self._send(save_connection(user["id"], payload.get("email", ""), payload.get("password", "")), 201)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen Garmin-fiókadat."}, 400)
        except Exception:
            self._send({"error": "A Garmin-kapcsolat mentése sikertelen."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if user:
                delete_connection(user["id"])
                self._send({"status": "disconnected"})
        except Exception:
            self._send({"error": "A Garmin-kapcsolat leválasztása sikertelen."}, 500)
