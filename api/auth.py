from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import clear_cookie_header, cookie_header, current_user, login, logout, register


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200, cookie: str | None = None) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            self._send({"user": user}, 200 if user else 401)
        except Exception:
            self._send({"error": "A munkamenet jelenleg nem ellenőrizhető."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 16_384:
                raise ValueError("Érvénytelen kérésméret.")
            payload = json.loads(self.rfile.read(size))
            action = payload.get("action")
            if action == "register":
                user, token = register(payload.get("email", ""), payload.get("password", ""), payload.get("name", ""))
                status = 201
            elif action == "login":
                user, token = login(payload.get("email", ""), payload.get("password", ""))
                status = 200
            else:
                raise ValueError("Ismeretlen fiókművelet.")
            secure = self.headers.get("X-Forwarded-Proto", "https") != "http"
            self._send({"user": user}, status, cookie_header(token, secure))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen fiókadat."}, 400)
        except Exception:
            self._send({"error": "A fiókművelet jelenleg nem hajtható végre."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            logout(self.headers)
        finally:
            self._send({"ok": True}, 200, clear_cookie_header())
