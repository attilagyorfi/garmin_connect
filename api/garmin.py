from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace

from garminconnect import Garmin
import requests
from curl_cffi import requests as cffi_requests

from auth_store import current_user
from garmin_connection import (
    clear_mfa_state,
    connection_status,
    delete_connection,
    load_mfa_state,
    save_mfa_state,
    save_token_connection,
)


def _cookie_dict(session) -> dict[str, str]:
    try:
        return dict(session.cookies.get_dict())
    except AttributeError:
        return {cookie.name: cookie.value for cookie in session.cookies}


def _serializable_mfa_state(client: Garmin) -> dict:
    native = client.client
    session = native._mfa_session
    widget = getattr(native, "_widget_last_resp", None)
    return {
        "flow": getattr(native, "_mfa_flow", "portal"),
        "method": getattr(native, "_mfa_method", "email"),
        "login_params": dict(getattr(native, "_mfa_login_params", {}) or {}),
        "post_headers": dict(getattr(native, "_mfa_post_headers", {}) or {}),
        "service_url": getattr(native, "_mfa_service_url", None),
        "session_kind": "cffi" if session.__class__.__module__.startswith("curl_cffi") else "requests",
        "cookies": _cookie_dict(session),
        "widget_html": getattr(widget, "text", None),
        "widget_url": getattr(widget, "url", None),
    }


def _restore_mfa_client(state: dict) -> Garmin:
    client = Garmin(return_on_mfa=True)
    native = client.client
    session = (
        cffi_requests.Session(impersonate="chrome", timeout=30)
        if state.get("session_kind") == "cffi"
        else requests.Session()
    )
    for name, value in dict(state.get("cookies") or {}).items():
        session.cookies.set(name, value)
    native._mfa_session = session
    native._mfa_login_params = dict(state.get("login_params") or {})
    native._mfa_post_headers = dict(state.get("post_headers") or {})
    native._mfa_service_url = state.get("service_url")
    native._mfa_flow = state.get("flow", "portal")
    native._mfa_method = state.get("method", "email")
    native._mfa_pending = True
    if state.get("widget_html") and state.get("widget_url"):
        native._widget_last_resp = SimpleNamespace(
            text=state["widget_html"], url=state["widget_url"],
        )
    return client


class handler(BaseHTTPRequestHandler):
    def _send(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _user(self) -> dict | None:
        user = current_user(self.headers)
        if not user:
            self._send({"error": "A művelethez bejelentkezés szükséges."}, 401)
        return user

    def do_GET(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if user:
                self._send(connection_status(user["id"]))
        except Exception:
            self._send({"error": "A Garmin-kapcsolat állapota jelenleg nem tölthető be."}, 503)

    def do_POST(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if not user:
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 16_384:
                raise ValueError("Érvénytelen kérésméret.")
            payload = json.loads(self.rfile.read(size))
            action = payload.get("action", "connect")
            if action == "verify_mfa":
                code = str(payload.get("code", "")).strip()
                if not code:
                    raise ValueError("Add meg a Garmin által küldött ellenőrző kódot.")
                email, mfa_state = load_mfa_state(user["id"])
                client = _restore_mfa_client(mfa_state)
                client.resume_login({}, code)
                result = save_token_connection(
                    user["id"], email, client.client.dumps(),
                )
                self._send(result, 201)
                return

            email = str(payload.get("email", "")).strip().lower()
            password = str(payload.get("password", ""))
            if "@" not in email or not password:
                raise ValueError("Add meg a Garmin e-mail-címedet és jelszavadat.")
            client = Garmin(email, password, return_on_mfa=True)
            mfa_status, _ = client.login()
            if mfa_status == "needs_mfa":
                save_mfa_state(user["id"], email, _serializable_mfa_state(client))
                client.password = None
                self._send({
                    "status": "mfa_required",
                    "message": "Add meg a Garmin által küldött egyszer használatos kódot.",
                }, 202)
                return
            client.password = None
            self._send(save_token_connection(user["id"], email, client.client.dumps()), 201)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send({"error": str(exc) or "Érvénytelen Garmin-fiókadat."}, 400)
        except Exception as exc:
            message = str(exc).lower()
            if "429" in message or "rate" in message:
                error = "A Garmin átmenetileg korlátozta a belépési kísérleteket. Várj néhány percet."
            elif "auth" in message or "401" in message or "password" in message:
                error = "A Garmin-hitelesítés sikertelen. Ellenőrizd az e-mail-címet és a jelszót."
            elif "mfa" in message:
                error = "Az MFA-ellenőrzés sikertelen vagy lejárt. Indítsd újra a csatlakoztatást."
            else:
                error = "A Garmin-kapcsolat létrehozása sikertelen. Próbáld újra később."
            self._send({"error": error}, 502)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            user = self._user()
            if user:
                clear_mfa_state(user["id"])
                delete_connection(user["id"])
                self._send({"status": "disconnected"})
        except Exception:
            self._send({"error": "A Garmin-kapcsolat leválasztása sikertelen."}, 500)
