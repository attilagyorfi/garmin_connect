from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

from auth_email import EmailError, _public_base_url, _validated_base_url, password_reset_message, send_email  # noqa: F401 (re-exported for tests)
from auth_store import (
    RateLimitError, client_ip_from, change_password, clear_cookie_header, cookie_header, delete_account,
    TOKEN_MINUTES, current_user, login, logout, register, request_password_reset, reset_password, verify_email,
)


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
            protocol = self.headers.get("X-Forwarded-Proto", "https")
            secure = protocol != "http"
            if action == "register":
                client_ip = client_ip_from(self.headers, getattr(self, "client_address", None))
                user, token = register(
                    payload.get("email", ""), payload.get("password", ""),
                    payload.get("name", ""), payload.get("inviteToken", ""),
                    self.headers.get("User-Agent", ""), client_ip,
                )
                status = 201
            elif action == "login":
                client_id = client_ip_from(self.headers, getattr(self, "client_address", None))
                user, token = login(
                    payload.get("email", ""), payload.get("password", ""), client_id,
                    self.headers.get("User-Agent", ""), client_id,
                )
                status = 200
            elif action == "verify_email":
                client_ip = client_ip_from(self.headers, getattr(self, "client_address", None))
                user, token = verify_email(
                    payload.get("token", ""), self.headers.get("User-Agent", ""), client_ip,
                )
                status = 200
            elif action == "resend_verification":
                self._send({"error": "A zárt rendszerben nincs e-mailes megerősítés."}, 403)
                return
            elif action == "request_password_reset":
                # Same answer whether or not the address has an account, so accounts cannot be enumerated.
                client_ip = client_ip_from(self.headers, getattr(self, "client_address", None))
                result = request_password_reset(payload.get("email", ""), client_ip)
                if result:
                    subject, text, markup = password_reset_message(_public_base_url(self.headers) + f"/?auth=reset&token={quote(result[1])}", TOKEN_MINUTES)
                    try:
                        send_email(result[0], subject, text, markup)
                    except EmailError as exc:
                        sys.stderr.write(f"password reset e-mail not sent: {exc}\n")
                self._send({"ok": True, "message": "Ha ehhez a címhez tartozik aktív fiók, néhány percen belül megérkezik a jelszó-visszaállító levél. Nézd meg a spam mappát is."})
                return
            elif action == "reset_password":
                reset_password(payload.get("token", ""), payload.get("password", ""))
                self._send({"ok": True, "message": "A jelszó megváltozott. Most már bejelentkezhetsz."})
                return
            elif action == "change_password":
                authenticated = current_user(self.headers)
                if not authenticated:
                    self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                    return
                client_id = client_ip_from(self.headers, getattr(self, "client_address", None))
                change_password(
                    authenticated["id"], payload.get("currentPassword", ""),
                    payload.get("newPassword", ""), client_id,
                )
                self._send(
                    {"ok": True, "message": "A jelszavad megváltozott. Biztonsági okból minden eszközről kijelentkeztettünk."},
                    200, clear_cookie_header(),
                )
                return
            elif action == "delete_account":
                authenticated = current_user(self.headers)
                if not authenticated:
                    self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
                    return
                client_id = client_ip_from(self.headers, getattr(self, "client_address", None))
                delete_account(
                    authenticated["id"], payload.get("currentPassword", ""),
                    payload.get("confirmation", ""), client_id,
                )
                self._send(
                    {
                        "ok": True,
                        "message": "A fiók és a hozzá tartozó személyes adatok véglegesen törlődtek.",
                    },
                    200, clear_cookie_header(),
                )
                return
            else:
                raise ValueError("Ismeretlen fiókművelet.")
            self._send({"user": user}, status, cookie_header(token, secure))
        except RateLimitError as exc:
            self._send({"error": str(exc)}, 429)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen fiókadat."}, 400)
        except Exception:
            self._send({"error": "A fiókművelet jelenleg nem hajtható végre."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            logout(self.headers)
        finally:
            self._send({"ok": True}, 200, clear_cookie_header())
