from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from assistant_actions import create_action, decide_action
from auth_store import current_user


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _payload(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 32_768:
            raise ValueError("Érvénytelen kérésméret.")
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError("Érvénytelen kérés.")
        return value

    def do_POST(self) -> None:  # noqa: N802
        self._handle("create")

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle("decide")

    def _handle(self, operation: str) -> None:
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            payload = self._payload()
            result = create_action(user["id"], payload.get("proposal")) if operation == "create" else decide_action(
                user["id"], str(payload.get("id", "")), str(payload.get("decision", ""))
            )
            self._send(result)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen asszisztensművelet."}, 400)
        except Exception:
            self._send({"error": "Az asszisztensművelet most nem hajtható végre."}, 500)
