from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

from auth_store import (
    RateLimitError, clear_cookie_header, cookie_header, create_password_reset,
    current_user, login, logout, register, resend_verification, reset_password,
    verify_email,
)
from email_service import send_password_reset, send_verification


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
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "localhost")
            base_url = os.getenv("AUTH_PUBLIC_URL", "").rstrip("/") or f"{protocol}://{host}"
            if not base_url.startswith(("https://", "http://")):
                raise ValueError("Érvénytelen nyilvános alkalmazáscím.")
            secure = protocol != "http"
            if action == "register":
                if not os.getenv("RESEND_API_KEY", "").strip():
                    self._send({"error": "A regisztrációs e-mail-küldés még nincs beállítva."}, 503)
                    return
                user, verification_token = register(payload.get("email", ""), payload.get("password", ""), payload.get("name", ""))
                send_verification(user["email"], verification_token, base_url)
                status = 201
                self._send({"user": None, "requiresVerification": True, "message": "Elküldtük a megerősítő e-mailt."}, status)
                return
            elif action == "login":
                client_id = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
                user, token = login(payload.get("email", ""), payload.get("password", ""), client_id)
                status = 200
            elif action == "verify_email":
                user, token = verify_email(payload.get("token", ""))
                status = 200
            elif action == "resend_verification":
                result = resend_verification(payload.get("email", ""))
                if result:
                    try:
                        send_verification(result[0], result[1], base_url)
                    except RuntimeError:
                        pass
                self._send({"ok": True, "message": "Ha a címhez ellenőrizetlen fiók tartozik, elküldtük az üzenetet."})
                return
            elif action == "request_password_reset":
                result = create_password_reset(payload.get("email", ""))
                if result:
                    try:
                        send_password_reset(result[0], result[1], base_url)
                    except RuntimeError:
                        pass
                self._send({"ok": True, "message": "Ha a címhez fiók tartozik, elküldtük a visszaállító hivatkozást."})
                return
            elif action == "reset_password":
                reset_password(payload.get("token", ""), payload.get("password", ""))
                self._send({"ok": True, "message": "A jelszó megváltozott. Most már bejelentkezhetsz."})
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
