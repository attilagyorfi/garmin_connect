from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from cloud_dashboard import sync_cloud_dashboard
from garmin_sync import GarminSyncError


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        try:
            body, status = sync_cloud_dashboard(), 200
        except GarminSyncError as exc:
            body, status = {"error": str(exc)}, 409
        except Exception:
            body, status = {"error": "A Garmin-szinkron váratlan hiba miatt megszakadt."}, 500
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
