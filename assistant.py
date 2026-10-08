"""AI assistant (chat) for the Hybrid Athlete app: consent, daily limits, conversation, memory and
plan proposals that only take effect after the user approves them.

The model only receives the aggregated context from assistant_context (no raw Garmin payloads,
credentials, tokens, e-mail addresses or stored IDs). The deterministic engine computes; the model explains.
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

import ai_usage
import assistant_actions
from ai_usage import DAILY_QUESTION_LIMIT, DAILY_TOKEN_LIMIT
from assistant_context import build_context
from assistant_prompts import MEMORY_TASK, SYSTEM_PROMPT, context_block
from cloud_cache import load_user_json, save_user_json
from cloud_dashboard import DASHBOARD_KEY
from user_state import STATE_KEY

ASSISTANT_KEY = "assistant_v1"
MODEL = "claude-sonnet-5-5"
MEMORY_RESERVATION_TOKENS = 3_000
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
    return {"consent": False, "consentAt": None, "memoryEnabled": True, "memory": [], "conversation": []}


def load_assistant_state(user_id: str) -> dict[str, Any]:
    stored = load_user_json(user_id, ASSISTANT_KEY) or {}
    state = {**empty_assistant_state(), **stored}
    state.pop("usage", None)  # usage lives in the ai_usage ledger
    return state


def public_state(state: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Conversation with the live status of each proposal, plus today's usage from the ledger."""
    ids = [action_id for item in state["conversation"] for action_id in item.get("actionIds", [])]
    actions = assistant_actions.list_actions(user_id, ids) if ids else {}
    conversation = [{**item, "actions": [actions[action_id] for action_id in item.get("actionIds", []) if action_id in actions]} if item.get("actionIds") else item
                    for item in state["conversation"]]
    return {"consent": state["consent"], "memoryEnabled": state["memoryEnabled"], "memory": state["memory"],
            "conversation": conversation, "usage": ai_usage.usage_today(user_id)}


def _client() -> Any:
    import anthropic

    return anthropic.Anthropic()


def _add_usage(total: dict[str, int], response: Any) -> dict[str, int]:
    for key, value in ai_usage.usage_numbers(response.usage).items():
        total[key] = total.get(key, 0) + value
    return total


REFUSAL_TEXT = "Erre a kérdésre most nem tudok válaszolni. Kérlek, fogalmazd meg másképp, vagy kérdezz az edzéseidről."


def _answer(client: Any, context: dict[str, Any], history: list[dict[str, Any]], question: str,
            on_proposals: Any = None) -> tuple[str, dict[str, int], list[dict[str, Any]]]:
    """One answer; if the model proposes plan changes they are stored as pending actions (on_proposals)
    and the model gets one follow-up turn to tell the athlete what awaits approval."""
    messages: list[dict[str, Any]] = [{"role": item["role"], "content": item.get("promptContent", item["content"])} for item in history[-PROMPT_HISTORY_MESSAGES:]]
    messages.append({"role": "user", "content": question})
    request = dict(
        model=MODEL, max_tokens=4000,
        # Stable prefix first: tools, the system prompt and the day's context are cached across the conversation.
        system=[{"type": "text", "text": SYSTEM_PROMPT}, {"type": "text", "text": context_block(context), "cache_control": {"type": "ephemeral"}}],
        tools=[assistant_actions.PLAN_TOOL], output_config={"effort": "low"},
        betas=[FALLBACK_BETA], fallbacks="default",
    )
    usage: dict[str, int] = {}
    created: list[dict[str, Any]] = []
    response = client.beta.messages.create(messages=messages, **request)
    _add_usage(usage, response)
    if response.stop_reason == "tool_use" and on_proposals is not None:
        calls = [block for block in response.content if block.type == "tool_use" and block.name == assistant_actions.PLAN_TOOL["name"]]
        results = []
        for block in calls:
            stored, problems = on_proposals([block.input])
            created += stored
            text = (f"Rögzítve jóváhagyásra: {stored[0]['summary']}. A sportoló a csevegőben hagyja jóvá vagy utasítja el; addig a Naptár nem változik."
                    if stored else f"Nem rögzíthető: {problems[0] if problems else 'érvénytelen javaslat'}")
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({} if stored else {"is_error": True})})
        messages += [{"role": "assistant", "content": response.content}, {"role": "user", "content": results}]
        # No further proposals in the follow-up: it only explains what was recorded.
        response = client.beta.messages.create(messages=messages, **{**request, "tool_choice": {"type": "none"}})
        _add_usage(usage, response)
    if response.stop_reason == "refusal":
        return REFUSAL_TEXT, usage, created
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n(A válasz hossza elérte a korlátot – kérdezz rá a folytatásra, ha kell.)"
    if not text and created:
        text = "Összeállítottam a javaslatot; lent jóváhagyhatod vagy elutasíthatod."
    return text, usage, created


def _extract_memory(client: Any, question: str, previous_answer: str | None) -> tuple[list[str], dict[str, int]]:
    # Durable facts come from what the athlete says, so this runs in parallel with the answer.
    dialogue = (f"Edzőtárs: {previous_answer}\n" if previous_answer else "") + f"Sportoló: {question}"
    response = client.messages.parse(
        model=MODEL, max_tokens=1000, output_config={"effort": "low"}, output_format=MemoryNotes,
        messages=[{"role": "user", "content": f"{MEMORY_TASK}\n\nBESZÉLGETÉS:\n{dialogue}"}],
    )
    notes = response.parsed_output.notes if response.stop_reason != "refusal" and response.parsed_output else []
    return [note.strip() for note in notes if note.strip()][:5], ai_usage.usage_numbers(response.usage)


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
    dashboard = load_user_json(user_id, DASHBOARD_KEY)
    if not dashboard:
        raise AssistantError("Az edzőtárs a Garmin-adataidból dolgozik; előbb futtass egy szinkront.")
    try:
        generation = ai_usage.reserve(user_id, "answer", MODEL)
    except ai_usage.UsageLimitError as exc:
        raise AssistantError(str(exc)) from exc
    app_state = load_user_json(user_id, STATE_KEY) or {}
    memory_notes = [item["text"] for item in state["memory"]] if state["memoryEnabled"] else []
    context = build_context(dashboard, memory_notes=memory_notes, app_profile=app_state.get("profile"))
    context["tervek"], handles = assistant_actions.plan_handles(app_state.get("plans") or [])
    client = client or _client()
    history, context["tervjavaslatok_előzménye"] = _history_with_proposals(user_id, state["conversation"])
    previous_answer = next((item["content"] for item in reversed(state["conversation"]) if item["role"] == "assistant"), None)
    memory_generation = None
    if state["memoryEnabled"]:
        try:
            memory_generation = ai_usage.reserve(user_id, "memory", MODEL, MEMORY_RESERVATION_TOKENS)
        except ai_usage.UsageLimitError:
            memory_generation = None  # the answer has priority over memory upkeep
    with ThreadPoolExecutor(max_workers=2) as pool:
        memory_job = pool.submit(_extract_memory, client, question, previous_answer) if memory_generation else None
        try:
            answer, usage, created = _answer(client, context, history, question,
                                             on_proposals=lambda proposals: assistant_actions.create_actions(user_id, proposals, handles))
        except Exception:
            ai_usage.release(generation)
            if memory_generation:
                ai_usage.release(memory_generation)
            raise
        ai_usage.settle(generation, usage)
        if memory_job is not None:
            try:
                notes, memory_usage = memory_job.result()
                state["memory"] = _merge_memory(state["memory"], notes)
                ai_usage.settle(memory_generation, memory_usage)
            except Exception:  # noqa: BLE001 - memory is best effort; the answer must still arrive
                ai_usage.release(memory_generation)
    stamp = _now()
    reply = {"role": "assistant", "content": answer, "at": stamp, **({"actionIds": [item["id"] for item in created]} if created else {})}
    state["conversation"] = (state["conversation"] + [{"role": "user", "content": question, "at": stamp}, reply])[-HISTORY_MESSAGES:]
    save_user_json(user_id, ASSISTANT_KEY, state)
    return {"answer": answer, **public_state(state, user_id)}


STATUS_NOTE = {"pending": "jóváhagyásra vár", "applied": "a sportoló jóváhagyta, bekerült a Naptárba", "rejected": "a sportoló elutasította", "expired": "lejárt, nem került a tervbe"}


def _plan_brief(plan: dict[str, Any] | None) -> str | None:
    if not plan:
        return None
    return f"{plan.get('date')} · {plan.get('type')} · {plan.get('title')} · {plan.get('duration')} perc · {plan.get('intensity')} · RPE {plan.get('rpe')}"


def _history_with_proposals(user_id: str, conversation: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The model sees past answers only as text, not its tool calls. Record which plan changes it proposed and
    what became of them — as a note on that answer and as authoritative context data — so later turns neither
    deny an earlier proposal nor assume an unapproved one is already in the plan."""
    window = conversation[-PROMPT_HISTORY_MESSAGES:]
    ids = [action_id for item in window for action_id in item.get("actionIds", [])]
    actions = assistant_actions.list_actions(user_id, ids) if ids else {}
    annotated, record = [], []
    for item in window:
        mine = [actions[action_id] for action_id in item.get("actionIds", []) if action_id in actions]
        for action in mine:
            record.append({"javaslat": action["summary"], "állapot": STATUS_NOTE.get(action["status"], action["status"]),
                           "előtte": _plan_brief(action.get("before")), "javasolt": None if action["action"] == "delete_plan" else _plan_brief(action.get("plan"))})
        notes = "; ".join(f"„{action['summary']}” – {STATUS_NOTE.get(action['status'], action['status'])}" for action in mine)
        annotated.append({**item, "promptContent": item["content"] + f"\n\n[Ebben a válaszban rögzített tervjavaslat(ok): {notes}]"} if mine else item)
    return annotated, record


def decide_proposal(user_id: str, action_id: str, decision: str) -> dict[str, Any]:
    try:
        result = assistant_actions.decide_action(user_id, action_id, decision)
    except ValueError as exc:
        raise AssistantError(str(exc)) from exc
    return {"decision": result, **public_state(load_assistant_state(user_id), user_id)}


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
    return public_state(state, user_id)
