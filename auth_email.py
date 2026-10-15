"""Transactional e-mails (password reset, invite) through the Resend HTTP API.

No extra dependency: a single JSON POST with urllib. With AUTH_EMAIL_TEST_MODE set (local development,
tests) nothing is sent. Links and tokens are never logged.
"""
from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote, urlsplit

RESEND_URL = "https://api.resend.com/emails"
APP_NAME = "Hybrid Athlete"


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


def public_link(headers: object, query: str) -> str:
    """Absolute link to the app with the given query (e.g. "auth=reset&token=…")."""
    return f"{_public_base_url(headers)}/?{query}"


class EmailError(RuntimeError):
    """The message could not be handed to the e-mail provider."""


def test_mode() -> bool:
    return os.getenv("AUTH_EMAIL_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    return test_mode() or bool(os.getenv("RESEND_API_KEY", "").strip() and os.getenv("AUTH_EMAIL_FROM", "").strip())


def _layout(title: str, paragraphs: list[str], link: str, button: str, footer: str) -> tuple[str, str]:
    text = "\n\n".join([title, *paragraphs, f"{button}: {link}", footer, f"– {APP_NAME}"])
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{html.escape(item)}</p>' for item in paragraphs)
    markup = (
        '<div style="font-family:Arial,sans-serif;color:#1d2321;max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(title)}</h1>{body}'
        f'<p style="margin:22px 0"><a href="{html.escape(link, quote=True)}" '
        'style="display:inline-block;padding:12px 18px;border-radius:8px;background:#14b8a6;color:#04201c;'
        f'font-weight:bold;text-decoration:none">{html.escape(button)}</a></p>'
        f'<p style="margin:0 0 8px;color:#5b6461;font-size:13px;line-height:1.5">Ha a gomb nem működik, másold a böngészőbe: {html.escape(link)}</p>'
        f'<p style="margin:18px 0 0;color:#5b6461;font-size:13px;line-height:1.5">{html.escape(footer)}</p>'
        f'<p style="margin:18px 0 0;color:#5b6461;font-size:13px">– {APP_NAME}</p></div>'
    )
    return text, markup


def password_reset_message(link: str, minutes: int) -> tuple[str, str, str]:
    subject = f"{APP_NAME}: új jelszó"
    text, markup = _layout(
        "Új jelszó beállítása",
        ["Valaki új jelszót kért a fiókodhoz. Ha te voltál, kattints a gombra.",
         f"A link {minutes} percig érvényes, és csak egyszer használható. Az új jelszó után minden eszközödről kijelentkeztetünk."],
        link, "Új jelszó beállítása",
        "Ha nem te kérted, nyugodtan töröld ezt a levelet. A jelszavad nem változik.",
    )
    return subject, text, markup


def verification_message(link: str, hours: int) -> tuple[str, str, str]:
    subject = f"{APP_NAME}: erősítsd meg az e-mail-címedet"
    text, markup = _layout(
        "E-mail-cím megerősítése",
        ["Köszi, hogy regisztráltál! Már csak azt kell megerősítened, hogy ez a te címed.",
         f"A link {hours} óráig érvényes, és csak egyszer használható. Utána rögtön be is léptetünk."],
        link, "E-mail-cím megerősítése",
        "Ha nem te regisztráltál, töröld ezt a levelet. Megerősítés nélkül a fiók nem használható.",
    )
    return subject, text, markup


def sender() -> str:
    """AUTH_EMAIL_FROM tidied up: surrounding quotes/spaces and a bare "<address>" (which Resend rejects with 422)."""
    value = os.getenv("AUTH_EMAIL_FROM", "").strip().strip("'\"").strip()
    if value.startswith("<") and value.endswith(">") and value.count("<") == 1:
        value = value[1:-1].strip()
    return value


def status() -> dict[str, Any]:
    """Admin overview of the e-mail setup; never contains the API key."""
    return {"configured": is_configured() and not test_mode(), "testMode": test_mode(), "hasApiKey": bool(os.getenv("RESEND_API_KEY", "").strip()),
            "sender": sender() or None, "verificationRequired": verification_required()}


def test_message() -> tuple[str, str, str]:
    subject = f"{APP_NAME}: próbalevél"
    lines = ["Ez egy próbalevél az adminoldalról.", "Ha megkaptad, rendben megy a levelezés: a megerősítő, a jelszó-visszaállító, a meghívó és a keretriasztó levelek is kimennek."]
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{html.escape(item)}</p>' for item in lines)
    markup = (f'<div style="font-family:Arial,sans-serif;color:#1d2321;max-width:520px;margin:0 auto;padding:24px">'
              f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(subject)}</h1>{body}<p style="margin:18px 0 0;color:#5b6461;font-size:13px">– {APP_NAME}</p></div>')
    return subject, "\n\n".join([subject, *lines, f"– {APP_NAME}"]), markup


def verification_required() -> bool:
    """New accounts must confirm their address only when real e-mail delivery is set up; otherwise (local
    development, test mode, missing Resend settings) nobody could ever receive the link."""
    return is_configured() and not test_mode()


def invite_message(link: str, days: int) -> tuple[str, str, str]:
    subject = f"Meghívót kaptál a {APP_NAME}-be"
    text, markup = _layout(
        "Meghívtak a Hybrid Athlete-be",
        ["A Hybrid Athlete a Garmin-adataidból megmondja, mit eddz ma, hogyan fejlődsz, és hogyan készülj a versenyedre.",
         f"A meghívó {days} napig érvényes, és egy fiókot lehet vele létrehozni."],
        link, "Fiók létrehozása",
        "Ha nem számítottál erre a levélre, nyugodtan töröld.",
    )
    return subject, text, markup


def budget_alert_message(level: int, month: str, spent: float, budget: float) -> tuple[str, str, str]:
    """Operator e-mail for the monthly AI budget (no user data, only totals)."""
    paused = level >= 100
    subject = f"{APP_NAME}: {'elfogyott a havi AI-keret, az Edzőtárs szünetel' if paused else f'elment a havi AI-keret {level}%-a'}"
    text_lines = [
        f"{month} hónapban eddig kb. {spent:.2f} USD ment el AI-ra, a keret {budget:.2f} USD.",
        "Az Edzőtárs a hónap végéig szünetel. A felhasználók látják ezt, minden más működik."
        if paused else "Ha elfogy a keret, az Edzőtárs a hónap végéig szünetel.",
        "A keretet a Vercelen, az AI_MONTHLY_BUDGET_USD változóval tudod átállítani. A részleteket a Beállítások › Adminisztráció oldalon látod.",
    ]
    body = "".join(f'<p style="margin:0 0 14px;line-height:1.6">{html.escape(item)}</p>' for item in text_lines)
    markup = (f'<div style="font-family:Arial,sans-serif;color:#1d2321;max-width:520px;margin:0 auto;padding:24px">'
              f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(subject)}</h1>{body}'
              f'<p style="margin:18px 0 0;color:#5b6461;font-size:13px">– {APP_NAME}</p></div>')
    return subject, "\n\n".join([subject, *text_lines, f"– {APP_NAME}"]), markup


def _provider_reason(exc: urllib.error.HTTPError) -> str:
    """Resend's own explanation (e.g. "Invalid `from` field…"), so an admin can fix the setting; never the request."""
    try:
        message = json.loads(exc.read() or b"{}").get("message")
    except (ValueError, OSError, AttributeError):
        return ""
    return f": {str(message)[:200]}" if message else ""


def send_email(to: str, subject: str, text: str, markup: str, *, opener: Any = None) -> dict[str, Any]:
    """Hand one message to Resend. Returns {"sent": bool, "testMode": bool}; raises EmailError on failure."""
    if test_mode():
        return {"sent": False, "testMode": True}
    api_key, from_address = os.getenv("RESEND_API_KEY", "").strip(), sender()
    if not api_key or not from_address:
        raise EmailError("Az e-mail-küldés nincs beállítva.")
    request = urllib.request.Request(
        RESEND_URL,
        data=json.dumps({"from": from_address, "to": [to], "subject": subject, "text": text, "html": markup}).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "hybrid-athlete/1.0"},
        method="POST",
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=10) as response:
            if response.status >= 300:
                raise EmailError(f"Az e-mail-szolgáltató hibát jelzett ({response.status}).")
    except urllib.error.HTTPError as exc:
        raise EmailError(f"Az e-mail-szolgáltató hibát jelzett ({exc.code}){_provider_reason(exc)}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EmailError("Az e-mail-szolgáltató nem érhető el.") from exc
    return {"sent": True, "testMode": False}
