from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from ai_usage import usage_today
from auth_store import current_user, is_ai_enabled


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
            if not is_ai_enabled():
                self._send({"error": "Az AI-asszisztens ebben a zárt kiadásban még nincs bekapcsolva."}, 503)
                return
            self._send(usage_today(user["id"]))
        except Exception:
            self._send({"error": "Az AI-használat most nem kérdezhető le."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        self._send({"error": "A használati elszámolás csak lekérdezhető."}, 405)

    do_PATCH = do_POST
    do_DELETE = do_POST
    do_PUT = do_POST
