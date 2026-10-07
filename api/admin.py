from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

from auth_store import (
    create_admin_password_reset,
    create_invite,
    current_user,
    list_access_admin,
    revoke_invite,
    set_user_access,
)


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _admin(self) -> dict | None:
        user = current_user(self.headers)
        if not user:
            self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
            return None
        if user.get("role") != "admin":
            self._send({"error": "Ehhez a művelethez adminisztrátori jogosultság szükséges."}, 403)
            return None
        return user

    def _payload(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 16_384:
            raise ValueError("Érvénytelen kérésméret.")
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError("Érvénytelen kérés.")
        return value

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = self._admin()
            if user:
                self._send(list_access_admin(user["id"]))
        except Exception:
            self._send({"error": "A hozzáférések most nem kérdezhetők le."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = self._admin()
            if not user:
                return
            payload = self._payload()
            action = payload.get("action")
            if action == "create_invite":
                token, invite = create_invite(user["id"])
                self._send({**invite, "path": f"/?invite={quote(token)}"}, 201)
                return
            if action == "create_password_reset":
                result = create_admin_password_reset(user["id"], payload.get("email", ""))
                if not result:
                    raise ValueError("Ehhez az e-mail-címhez nem tartozik fiók.")
                self._send({"email": result[0], "path": f"/?auth=reset&token={quote(result[1])}"}, 201)
                return
            if action == "revoke_invite":
                revoke_invite(user["id"], payload.get("id", ""))
                self._send({"ok": True})
                return
            if action == "set_user_access":
                set_user_access(user["id"], payload.get("id", ""), payload.get("status", ""))
                self._send({"ok": True})
                return
            raise ValueError("Ismeretlen adminisztrátori művelet.")
        except PermissionError as exc:
            self._send({"error": str(exc)}, 403)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen kérés."}, 400)
        except Exception:
            self._send({"error": "Az adminisztrátori művelet most nem hajtható végre."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        self._send({"error": "Nem támogatott művelet."}, 405)

    do_PATCH = do_DELETE
    do_PUT = do_DELETE
