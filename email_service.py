"""Minimal transactional email client for the Resend HTTPS API."""
from __future__ import annotations

import html
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _send(to: str, subject: str, heading: str, copy: str, action: str, url: str, idempotency_key: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Az e-mail-küldés még nincs beállítva.")
    sender = os.getenv("AUTH_EMAIL_FROM", "Hybrid Athlete <onboarding@resend.dev>").strip()
    safe_url = html.escape(url, quote=True)
    body = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": f"""<!doctype html><html lang=\"hu\"><body style=\"margin:0;background:#0d0e0e;color:#f5f5f4;font-family:Arial,sans-serif\"><div style=\"max-width:560px;margin:auto;padding:48px 24px\"><p style=\"color:#14b8a6;font-size:12px;letter-spacing:2px\">HYBRID ATHLETE</p><h1 style=\"font-size:28px\">{html.escape(heading)}</h1><p style=\"color:#b8bcba;line-height:1.65\">{html.escape(copy)}</p><p style=\"margin:32px 0\"><a href=\"{safe_url}\" style=\"display:inline-block;background:#14b8a6;color:#071b18;text-decoration:none;font-weight:bold;padding:14px 20px;border-radius:8px\">{html.escape(action)}</a></p><p style=\"color:#777;font-size:12px;line-height:1.5\">A hivatkozás 30 percig és csak egyszer használható. Ha nem te kérted, hagyd figyelmen kívül ezt az üzenetet.</p></div></body></html>""",
    }
    request = Request(
        "https://api.resend.com/emails", data=json.dumps(body).encode(), method="POST",
        headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key[:256],
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError("Az e-mail-küldés sikertelen.")
    except (HTTPError, URLError) as exc:
        raise RuntimeError("Az e-mail-küldés átmenetileg nem érhető el.") from exc


def send_verification(to: str, token: str, base_url: str) -> None:
    url = f"{base_url}/?auth=verify&token={token}"
    _send(to, "Erősítsd meg az e-mail-címedet", "E-mail-cím megerősítése", "Ezzel fejezheted be a Hybrid Athlete-fiókod létrehozását.", "E-mail-cím megerősítése", url, f"verify-{token}")


def send_password_reset(to: str, token: str, base_url: str) -> None:
    url = f"{base_url}/?auth=reset&token={token}"
    _send(to, "Hybrid Athlete jelszó-visszaállítás", "Új jelszó beállítása", "Kérés érkezett a Hybrid Athlete-fiókod jelszavának megváltoztatására.", "Új jelszó beállítása", url, f"reset-{token}")
