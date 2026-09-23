from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from auth_store import (
    RateLimitError, clear_cookie_header, cookie_header, current_user, login,
    logout, register, reset_password, verify_email,
)


def _validated_base_url(raw: str, *, allow_local_http: bool = False) -> str:
    value = str(raw or "").strip().rstrip("/")
    parsed = urlsplit(value)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or parsed.scheme not in ({"https", "http"} if allow_local_http else {"https"})
        or (parsed.scheme == "http" and parsed.hostname not in local_hosts)
    ):
        raise RuntimeError("A nyilvános alkalmazáscím nincs biztonságosan beállítva.")
    return value


def _public_base_url(headers: object) -> str:
    configured = os.getenv("AUTH_PUBLIC_URL", "").strip()
    if configured:
        return _validated_base_url(configured, allow_local_http=True)

    vercel_host = (
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
        or os.getenv("VERCEL_URL", "").strip()
    )
    if vercel_host:
        return _validated_base_url(f"https://{vercel_host.lstrip('/')}")

    host = str(headers.get("Host", "") if hasattr(headers, "get") else "").strip()
    protocol = str(headers.get("X-Forwarded-Proto", "http") if hasattr(headers, "get") else "http").strip().lower()
    candidate = f"{protocol}://{host}"
    parsed = urlsplit(candidate)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Állítsd be az AUTH_PUBLIC_URL környezeti változót.")
    return _validated_base_url(candidate, allow_local_http=True)


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
                client_ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
                user, token = register(
                    payload.get("email", ""), payload.get("password", ""),
                    payload.get("name", ""), payload.get("inviteToken", ""),
                    self.headers.get("User-Agent", ""), client_ip,
                )
                status = 201
            elif action == "login":
                client_id = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
                user, token = login(
                    payload.get("email", ""), payload.get("password", ""), client_id,
                    self.headers.get("User-Agent", ""), client_id,
                )
                status = 200
            elif action == "verify_email":
                client_ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
                user, token = verify_email(
                    payload.get("token", ""), self.headers.get("User-Agent", ""), client_ip,
                )
                status = 200
            elif action == "resend_verification":
                self._send({"error": "A zárt rendszerben nincs e-mailes megerősítés."}, 403)
                return
            elif action == "request_password_reset":
                self._send({"error": "Kérj egyszer használható jelszó-visszaállító hivatkozást az adminisztrátortól."}, 403)
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
