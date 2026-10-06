from types import SimpleNamespace

import pytest

import assistant
from assistant import AssistantError, ask, update_settings
from assistant_context import build_context


class FakeStore(dict):
    def load(self, user_id, key, connection=None):
        return self.get((user_id, key))

    def save(self, user_id, key, payload, connection=None):
        self[(user_id, key)] = payload


def usage(**extra):
    return SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0, **extra)


class FakeClient:
    def __init__(self, answer="Ma könnyű Zone 2 futás legyen.", notes=("Este 7 után edz.",), stop_reason="end_turn"):
        self.calls = []
        outer = self

        class Beta:
            class messages:
                @staticmethod
                def create(**kwargs):
                    outer.calls.append(kwargs)
                    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=answer)], usage=usage())

        class Messages:
            @staticmethod
            def parse(**kwargs):
                return SimpleNamespace(stop_reason="end_turn", parsed_output=assistant.MemoryNotes(notes=list(notes)), usage=usage())

        self.beta, self.messages = Beta(), Messages()


DASHBOARD = {"today": "2026-10-06", "source": "garmin", "readiness": 80, "band": "terhelhető", "decision": {"title": "Zone 2 alapozás"},
             "benchmarks": {"profile": {"sex": "male", "age": 35}, "cards": [{"key": "vo2max", "title": "VO2max", "status": "missing", "headline": "Nincs adat."}]},
             "sessions": [{"date": "2026-10-05", "type": "Futás", "name": "Könnyű futás", "durationMin": 40, "avgHr": 140, "load": 60, "distanceKm": 7.2, "id": "123456"}],
             "metrics": [], "trends": [], "coaching": {"tips": [], "weekly": None}}


@pytest.fixture()
def store(monkeypatch):
    data = FakeStore()
    monkeypatch.setattr(assistant, "load_user_json", data.load)
    monkeypatch.setattr(assistant, "save_user_json", data.save)
    data[("u1", assistant.DASHBOARD_KEY)] = DASHBOARD
    data[("u1", assistant.STATE_KEY)] = {"profile": {"goal": "Futóteljesítmény", "weeklyHours": 6}}
    return data


def test_consent_is_required_before_any_model_call(store):
    client = FakeClient()
    with pytest.raises(AssistantError, match="hozzájárulás"):
        ask("u1", "Mit eddzek?", client)
    assert client.calls == []


def test_ask_sends_cached_context_and_stores_conversation_and_memory(store):
    update_settings("u1", {"action": "consent", "value": True})
    client = FakeClient()
    result = ask("u1", "Mit eddzek holnap?", client)
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5" and call["fallbacks"] == "default" and call["betas"] == [assistant.FALLBACK_BETA]
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"} and "Futóteljesítmény" in call["system"][-1]["text"]
    assert call["messages"][-1] == {"role": "user", "content": "Mit eddzek holnap?"}
    assert result["answer"].startswith("Ma könnyű") and result["usage"]["remaining"] == assistant.DAILY_QUESTION_LIMIT - 1
    assert [item["role"] for item in result["conversation"]] == ["user", "assistant"]
    assert [item["text"] for item in result["memory"]] == ["Este 7 után edz."]
    ask("u1", "És utána?", client)
    assert [item["text"] for item in store[("u1", assistant.ASSISTANT_KEY)]["memory"]] == ["Este 7 után edz."]  # deduplicated
    assert client.calls[1]["messages"][0]["content"] == "Mit eddzek holnap?"  # history goes back to the model


def test_daily_question_limit(store):
    update_settings("u1", {"action": "consent", "value": True})
    state = store[("u1", assistant.ASSISTANT_KEY)]
    state["usage"] = {"date": assistant.date.today().isoformat(), "questions": assistant.DAILY_QUESTION_LIMIT, "tokens": 0}
    client = FakeClient()
    with pytest.raises(AssistantError, match="15 kérdéses"):
        ask("u1", "Még egy kérdés?", client)
    assert client.calls == []


def test_memory_can_be_disabled_deleted_and_consent_withdrawn(store):
    update_settings("u1", {"action": "consent", "value": True})
    update_settings("u1", {"action": "memory", "enabled": False})
    result = ask("u1", "Szia", FakeClient())
    assert result["memory"] == [] and result["memoryEnabled"] is False
    update_settings("u1", {"action": "memory", "enabled": True})
    result = ask("u1", "Szia", FakeClient())
    note_id = result["memory"][0]["id"]
    assert update_settings("u1", {"action": "deleteMemory", "id": note_id})["memory"] == []
    ask("u1", "Szia", FakeClient())
    withdrawn = update_settings("u1", {"action": "consent", "value": False})
    assert withdrawn["memory"] == [] and withdrawn["conversation"] == [] and withdrawn["consent"] is False


def test_refusal_returns_friendly_text(store):
    update_settings("u1", {"action": "consent", "value": True})
    assert "nem tudok válaszolni" in ask("u1", "?", FakeClient(stop_reason="refusal"))["answer"]


def test_context_has_no_identifiers_and_marks_missing_metrics():
    context = build_context(DASHBOARD, memory_notes=["Tömör válaszokat kér."])
    flat = str(context)
    assert "123456" not in flat and "@" not in flat
    assert {"mutató": "VO2max", "érték": "nincs adat", "ok": "Nincs adat."} in context["korosztályos_összevetés"]
    assert context["memória"] == ["Tömör válaszokat kér."]
