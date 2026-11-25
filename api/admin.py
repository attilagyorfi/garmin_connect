from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import quote

from ai_usage import admin_summary
from auth_email import EmailError, invite_message, password_reset_message, public_link, send_email, test_message
from auth_email import status as email_status
from auth_store import (
    EMAIL_PATTERN,
    INVITE_DAYS,
    TOKEN_MINUTES,
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
            self._send({"error": "Ehhez be kell jelentkezned."}, 401)
            return None
        if user.get("role") != "admin":
            self._send({"error": "Ehhez a művelethez adminisztrátori jogosultság szükséges."}, 403)
            return None
        return user

    def _mail(self, recipient: str, subject: str, text: str, markup: str) -> dict:
        """Send one admin-initiated e-mail; a failure is reported, the copyable link still works."""
        try:
            result = send_email(recipient, subject, text, markup)
        except EmailError as exc:
            return {"emailSent": False, "emailError": f"{exc} Másold ki a linket, és küldd el kézzel."}
        if result["testMode"]:
            return {"emailSent": False, "emailError": "Teszt üzemmódban vagyunk (AUTH_EMAIL_TEST_MODE), ezért nem ment ki levél."}
        return {"emailSent": True, "emailTo": recipient}

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
                self._send({**list_access_admin(user["id"]), "aiUsage": admin_summary(30), "email": email_status()})
        except Exception:
            self._send({"error": "Most nem tudjuk betölteni a fiókokat. Próbáld újra pár perc múlva."}, 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = self._admin()
            if not user:
                return
            payload = self._payload()
            action = payload.get("action")
            if action == "send_test_email":
                self._send(self._mail(user["email"], *test_message()))
                return
            if action == "create_invite":
                recipient = str(payload.get("email") or "").strip().lower()[:254]
                if recipient and not EMAIL_PATTERN.fullmatch(recipient):
                    raise ValueError("Adj meg egy érvényes e-mail-címet a meghívónak.")
                token, invite = create_invite(user["id"])
                query = f"invite={quote(token)}"
                body = {**invite, "path": f"/?{query}"}
                if recipient:
                    body.update(self._mail(recipient, *invite_message(public_link(self.headers, query), INVITE_DAYS)))
                self._send(body, 201)
                return
            if action == "create_password_reset":
                result = create_admin_password_reset(user["id"], payload.get("email", ""))
                if not result:
                    raise ValueError("Ezzel a címmel nincs fiók.")
                query = f"auth=reset&token={quote(result[1])}"
                body = {"email": result[0], "path": f"/?{query}"}
                if payload.get("sendEmail"):
                    body.update(self._mail(result[0], *password_reset_message(public_link(self.headers, query), TOKEN_MINUTES)))
                self._send(body, 201)
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
            self._send({"error": "Ez most nem sikerült. Próbáld újra pár perc múlva."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        self._send({"error": "Nem támogatott művelet."}, 405)

    do_PATCH = do_DELETE
    do_PUT = do_DELETE
