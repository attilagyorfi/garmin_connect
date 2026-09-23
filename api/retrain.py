from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler

from model_registry import run_scheduled_retraining


def authorized_cron(headers: object) -> bool:
    secret = os.getenv("CRON_SECRET", "")
    provided = getattr(headers, "get")("Authorization", "") if headers else ""
    return bool(secret) and hmac.compare_digest(provided, f"Bearer {secret}")


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
        if not authorized_cron(self.headers):
            self._send({"error": "Érvénytelen cron-hitelesítés."}, 401)
            return
        try:
            self._send(run_scheduled_retraining())
        except Exception:
            self._send({"error": "Az ütemezett modellfrissítés sikertelen."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        self._send({"error": "A végpont kizárólag Vercel Cron hívással használható."}, 405)
