from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from user_state import apply_patch, load_state


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
            self._send(load_state(user["id"]))
        except Exception:
            self._send({"error": "A személyes beállítások jelenleg nem tölthetők be."}, 503)

    def do_PATCH(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 262_144:
                raise ValueError("Érvénytelen kérésméret.")
            self._send(apply_patch(json.loads(self.rfile.read(size)), user["id"]))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen személyes adat."}, 400)
        except Exception:
            self._send({"error": "A személyes beállítások mentése sikertelen."}, 500)
