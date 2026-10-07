from __future__ import annotations

import json
import logging
from datetime import date
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from auth_store import current_user
from data_export import build_user_export
from user_state import apply_patch, load_state


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200, *, attachment: bool = False) -> None:
        encoded = json.dumps(body, ensure_ascii=False, indent=2 if attachment else None).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if attachment:
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="hybrid-athlete-adatexport-{date.today().isoformat()}.json"',
            )
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = current_user(self.headers)
            if not user:
                self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            query = parse_qs(urlparse(getattr(self, "path", "")).query)
            if query.get("export") == ["1"]:
                self._send(build_user_export(user), attachment=True)
                return
            self._send(load_state(user["id"]))
        except Exception as exc:
            logging.getLogger(__name__).error(
                "state_load_failed type=%s sqlstate=%s",
                type(exc).__name__, getattr(exc, "sqlstate", None),
            )
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
