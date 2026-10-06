"""Compact, aggregated context for the AI assistant.

Only derived numbers leave the server: no raw Garmin payloads, credentials, tokens, e-mail
addresses or activity IDs. The deterministic engine computes; the model interprets.
"""
from __future__ import annotations

from typing import Any

RECENT_SESSIONS = 10
TREND_WEEKS = 8


def _metrics(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"név": item.get("name"), "érték": item.get("value"), "pont": item.get("score")} for item in dashboard.get("metrics") or []]


def _benchmarks(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    cards = ((dashboard.get("benchmarks") or {}).get("cards")) or []
    rows = []
    for card in cards:
        if card.get("status") != "ok":
            # Missing metrics stay visible so the model can say what is absent instead of silently skipping it.
            rows.append({"mutató": card.get("title"), "érték": "nincs adat", "ok": card.get("headline")})
            continue
        rows.append({key: value for key, value in {
            "mutató": card.get("title"), "érték": card.get("valueText"), "szint": card.get("category"),
            "percentilis": card.get("percentile"), "összevetés": card.get("headline"), "következő_cél": card.get("nextGoal"),
            "megbízhatóság": card.get("confidence"),
        }.items() if value not in (None, "")})
    return rows


def _tips(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    tips = ((dashboard.get("coaching") or {}).get("tips")) or []
    return [{"jelzés": tip.get("title"), "típus": tip.get("tone"), "miért": tip.get("why"), "javaslat": tip.get("action")} for tip in tips]


def build_context(dashboard: dict[str, Any], memory_notes: list[str] | None = None, app_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    benchmarks = dashboard.get("benchmarks") or {}
    person = benchmarks.get("profile") or {}
    decision = dashboard.get("decision") or {}
    weekly = (dashboard.get("coaching") or {}).get("weekly") or {}
    profile = app_profile or {}
    return {
        "dátum": dashboard.get("today"),
        "adatforrás": "bemutató adat" if dashboard.get("source") == "demo" else "Garmin",
        "sportoló": {key: value for key, value in {
            "nem": {"male": "férfi", "female": "nő"}.get(person.get("sex")), "életkor": person.get("age"),
            "cél": profile.get("goal"), "esemény": profile.get("eventName"), "esemény_dátuma": profile.get("eventDate"),
            "heti_órakeret": profile.get("weeklyHours"), "erő_arány_cél_%": profile.get("strengthRatio"),
            "tapasztalat": profile.get("experience"), "korlátozások": profile.get("limitations"),
        }.items() if value not in (None, "")},
        "mai_döntés": {"readiness": dashboard.get("readiness"), "sáv": dashboard.get("band"), "bizonyosság": dashboard.get("confidence"),
                       "javaslat": decision.get("title"), "időtartam": decision.get("duration"), "intenzitás": decision.get("intensity"),
                       "indoklás": decision.get("rationale")},
        "readiness_összetevők": _metrics(dashboard),
        "korosztályos_összevetés": _benchmarks(dashboard),
        "aktív_jelzések": _tips(dashboard),
        "múlt_hét": {key: weekly.get(key) for key in ("weekStart", "weekEnd", "sessions", "minutes", "changePct", "sleepHours", "hrvChangePct", "summary")} if weekly else None,
        "legutóbbi_edzések": [
            {"dátum": item.get("date"), "típus": item.get("type"), "név": item.get("name"), "perc": item.get("durationMin"),
             "átlagpulzus": item.get("avgHr"), "terhelés": item.get("load"), "táv_km": item.get("distanceKm") or None}
            for item in (dashboard.get("sessions") or [])[:RECENT_SESSIONS]
        ],
        "heti_terhelés_trend": (dashboard.get("trends") or [])[-TREND_WEEKS:],
        "memória": memory_notes or [],
    }
