from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from model_registry import model_status


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
            self._send(model_status(user["id"]))
        except Exception:
            self._send({"error": "A modell állapota jelenleg nem kérdezhető le."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        self._send({"error": "A modell állapota csak lekérdezhető."}, 405)
