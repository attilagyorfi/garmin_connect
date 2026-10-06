"""AI assistant (chat) for the Hybrid Athlete app: consent, daily limits, conversation and memory.

The model only receives the aggregated context from assistant_context (no raw Garmin payloads,
credentials, tokens or e-mail addresses). The deterministic engine computes; the model explains.
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from assistant_context import build_context
from assistant_prompts import MEMORY_TASK, SYSTEM_PROMPT, context_block
from cloud_cache import load_user_json, save_user_json
from cloud_dashboard import DASHBOARD_KEY
from user_state import STATE_KEY

ASSISTANT_KEY = "assistant_v1"
MODEL = "claude-sonnet-5-5"
DAILY_QUESTION_LIMIT = 15
DAILY_TOKEN_LIMIT = 150_000  # input + output tokens per user per day, a cost ceiling beside the question cap
HISTORY_MESSAGES = 40  # stored for display
PROMPT_HISTORY_MESSAGES = 12  # sent back to the model
MAX_QUESTION_CHARS = 1500
MAX_MEMORY_NOTES = 30
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AssistantError(ValueError):
    """User-facing problem (consent missing, limit reached, no data)."""


class MemoryNotes(BaseModel):
    notes: list[str] = Field(description="Tartós megjegyzések a sportolóról, rövid magyar mondatokban")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_assistant_state() -> dict[str, Any]:
    return {"consent": False, "consentAt": None, "memoryEnabled": True, "memory": [], "conversation": [], "usage": {"date": None, "questions": 0, "tokens": 0}}


def load_assistant_state(user_id: str) -> dict[str, Any]:
    stored = load_user_json(user_id, ASSISTANT_KEY) or {}
    state = {**empty_assistant_state(), **stored}
    if state["usage"].get("date") != date.today().isoformat():
        state["usage"] = {"date": date.today().isoformat(), "questions": 0, "tokens": 0}
    return state


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    usage = state["usage"]
    return {
        "consent": state["consent"], "memoryEnabled": state["memoryEnabled"], "memory": state["memory"],
        "conversation": state["conversation"],
        "usage": {"questions": usage["questions"], "limit": DAILY_QUESTION_LIMIT, "remaining": max(0, DAILY_QUESTION_LIMIT - usage["questions"]),
                  "tokenBudgetLeft": usage["tokens"] < DAILY_TOKEN_LIMIT},
    }


def _client() -> Any:
    import anthropic

    return anthropic.Anthropic()


def _usage_tokens(response: Any) -> int:
    usage = response.usage
    return int((usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0)
               + (getattr(usage, "cache_creation_input_tokens", 0) or 0) + (usage.output_tokens or 0))


def _answer(client: Any, context: dict[str, Any], history: list[dict[str, Any]], question: str) -> tuple[str, int]:
    messages = [{"role": item["role"], "content": item["content"]} for item in history[-PROMPT_HISTORY_MESSAGES:]]
    messages.append({"role": "user", "content": question})
    response = client.beta.messages.create(
        model=MODEL, max_tokens=4000,
        # Stable prefix first: the system prompt and the day's context are cached across the conversation.
        system=[{"type": "text", "text": SYSTEM_PROMPT}, {"type": "text", "text": context_block(context), "cache_control": {"type": "ephemeral"}}],
        messages=messages, output_config={"effort": "low"},
        betas=[FALLBACK_BETA], fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "Erre a kérdésre most nem tudok válaszolni. Kérlek, fogalmazd meg másképp, vagy kérdezz az edzéseidről.", _usage_tokens(response)
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n(A válasz hossza elérte a korlátot – kérdezz rá a folytatásra, ha kell.)"
    return text, _usage_tokens(response)


def _extract_memory(client: Any, question: str, previous_answer: str | None) -> tuple[list[str], int]:
    # Durable facts come from what the athlete says, so this runs in parallel with the answer.
    dialogue = (f"Edzőtárs: {previous_answer}\n" if previous_answer else "") + f"Sportoló: {question}"
    response = client.messages.parse(
        model=MODEL, max_tokens=1000, output_config={"effort": "low"}, output_format=MemoryNotes,
        messages=[{"role": "user", "content": f"{MEMORY_TASK}\n\nBESZÉLGETÉS:\n{dialogue}"}],
    )
    notes = response.parsed_output.notes if response.stop_reason != "refusal" and response.parsed_output else []
    return [note.strip() for note in notes if note.strip()][:5], _usage_tokens(response)


def _merge_memory(memory: list[dict[str, Any]], notes: list[str]) -> list[dict[str, Any]]:
    known = {item["text"].casefold() for item in memory}
    for note in notes:
        if note.casefold() not in known:
            memory.append({"id": uuid.uuid4().hex[:12], "text": note[:300], "createdAt": _now()})
            known.add(note.casefold())
    return memory[-MAX_MEMORY_NOTES:]


def ask(user_id: str, question: str, client: Any | None = None) -> dict[str, Any]:
    question = str(question or "").strip()
    if not question:
        raise AssistantError("Írd be a kérdésedet.")
    if len(question) > MAX_QUESTION_CHARS:
        raise AssistantError(f"A kérdés legfeljebb {MAX_QUESTION_CHARS} karakter lehet.")
    state = load_assistant_state(user_id)
    if not state["consent"]:
        raise AssistantError("Az edzőtárs használatához előbb fogadd el az adatkezelési hozzájárulást.")
    if state["usage"]["questions"] >= DAILY_QUESTION_LIMIT or state["usage"]["tokens"] >= DAILY_TOKEN_LIMIT:
        raise AssistantError(f"Elérted a mai {DAILY_QUESTION_LIMIT} kérdéses keretet. Holnap reggel újra kérdezhetsz.")
    dashboard = load_user_json(user_id, DASHBOARD_KEY)
    if not dashboard:
        raise AssistantError("Az edzőtárs a Garmin-adataidból dolgozik; előbb futtass egy szinkront.")
    app_state = load_user_json(user_id, STATE_KEY) or {}
    memory_notes = [item["text"] for item in state["memory"]] if state["memoryEnabled"] else []
    context = build_context(dashboard, memory_notes=memory_notes, app_profile=app_state.get("profile"))
    client = client or _client()
    previous_answer = next((item["content"] for item in reversed(state["conversation"]) if item["role"] == "assistant"), None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        memory_job = pool.submit(_extract_memory, client, question, previous_answer) if state["memoryEnabled"] else None
        answer, tokens = _answer(client, context, state["conversation"], question)
        if memory_job is not None:
            try:
                notes, memory_tokens = memory_job.result()
                state["memory"] = _merge_memory(state["memory"], notes)
                tokens += memory_tokens
            except Exception:  # noqa: BLE001 - memory is best effort; the answer must still arrive
                pass
    stamp = _now()
    state["conversation"] = (state["conversation"] + [{"role": "user", "content": question, "at": stamp},
                                                      {"role": "assistant", "content": answer, "at": stamp}])[-HISTORY_MESSAGES:]
    state["usage"]["questions"] += 1
    state["usage"]["tokens"] += tokens
    save_user_json(user_id, ASSISTANT_KEY, state)
    return {"answer": answer, **public_state(state)}


def update_settings(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    state = load_assistant_state(user_id)
    action = payload.get("action")
    if action == "consent":
        state["consent"] = bool(payload.get("value"))
        state["consentAt"] = _now() if state["consent"] else None
        if not state["consent"]:  # withdrawing consent removes everything the assistant stored
            state.update(memory=[], conversation=[])
    elif action == "memory":
        state["memoryEnabled"] = bool(payload.get("enabled"))
    elif action == "deleteMemory":
        note_id = str(payload.get("id") or "")
        state["memory"] = [] if payload.get("all") else [item for item in state["memory"] if item["id"] != note_id]
    elif action == "resetConversation":
        state["conversation"] = []
    else:
        raise AssistantError("Ismeretlen művelet.")
    save_user_json(user_id, ASSISTANT_KEY, state)
    return public_state(state)
