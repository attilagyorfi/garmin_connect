from __future__ import annotations

import json
from datetime import date
from http.server import BaseHTTPRequestHandler

from auth_store import current_user
from data_export import build_user_export


class handler(BaseHTTPRequestHandler):
    def _send_json(self, body: dict, status: int = 200, *, attachment: bool = False) -> None:
        encoded = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
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
                self._send_json({"error": "A művelethez bejelentkezés szükséges."}, 401)
                return
            self._send_json(build_user_export(user), attachment=True)
        except Exception:
            self._send_json({"error": "A saját adatok exportja jelenleg nem készíthető el."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        self._send_json({"error": "Nem támogatott művelet."}, 405)

    do_DELETE = do_POST
    do_PATCH = do_POST
    do_PUT = do_POST
