from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from assistant import AssistantError, ask, decide_proposal, load_assistant_state, public_state, update_settings
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

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            self._send(public_state(load_assistant_state(user["id"]), user["id"]))
        except Exception:
            self._send({"error": "Az edzőtárs állapota jelenleg nem tölthető be."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 16_384:
                raise AssistantError("Érvénytelen kérésméret.")
            payload = json.loads(self.rfile.read(size))
            if payload.get("action") == "ask":
                self._send(ask(user["id"], payload.get("question", "")))
            elif payload.get("action") == "decideProposal":
                self._send(decide_proposal(user["id"], str(payload.get("id", "")), str(payload.get("decision", ""))))
            else:
                self._send(update_settings(user["id"], payload))
        except (AssistantError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen kérés."}, 400)
        except Exception:
            self._send({"error": "Az edzőtárs most nem érhető el. Próbáld újra egy kicsit később."}, 502)
