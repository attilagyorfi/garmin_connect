from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from auth_store import list_sessions, revoke_session


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
            self._send({"sessions": list_sessions(self.headers)})
        except ValueError as exc:
            self._send({"error": str(exc)}, 401)
        except Exception:
            self._send({"error": "A munkamenetek jelenleg nem tölthetők be."}, 503)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 4096:
                raise ValueError("Érvénytelen kérésméret.")
            payload = json.loads(self.rfile.read(size))
            session_id = str(payload.get("sessionId", "")).strip()
            if not session_id:
                raise ValueError("Hiányzik a munkamenet azonosítója.")
            revoke_session(self.headers, session_id)
            self._send({"ok": True})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc)}, 400)
        except Exception:
            self._send({"error": "A munkamenet visszavonása sikertelen."}, 500)
