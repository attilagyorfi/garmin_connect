from types import SimpleNamespace

import pytest

import ai_usage
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
    def __init__(self, answer="Ma könnyű Zone 2 futás legyen.", notes=("Este 7 után edz.",), stop_reason="end_turn", responses=None, error=None):
        self.calls = []
        outer = self
        queue = list(responses or [])

        class Beta:
            class messages:
                @staticmethod
                def create(**kwargs):
                    outer.calls.append(kwargs)
                    if error:
                        raise error
                    if queue:
                        return queue.pop(0)
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


class FakeLedger:
    """In-memory stand-in for the ai_usage table with the same reserve/settle/release contract."""

    def __init__(self):
        self.rows = {}

    def _counts(self):
        live = [row for row in self.rows.values() if row["status"] != "failed"]
        return sum(1 for row in live if row["kind"] == "answer"), sum(row["total"] or row["reserved"] for row in live)

    def reserve(self, user_id, kind, model, tokens=ai_usage.RESERVATION_TOKENS):
        questions, used = self._counts()
        if (kind == "answer" and questions >= ai_usage.DAILY_QUESTION_LIMIT) or used >= ai_usage.DAILY_TOKEN_LIMIT:
            raise ai_usage.UsageLimitError(f"Elérted a mai {ai_usage.DAILY_QUESTION_LIMIT} kérdéses keretet.")
        key = f"g{len(self.rows)}"
        self.rows[key] = {"kind": kind, "status": "reserved", "reserved": tokens, "total": None}
        return key

    def settle(self, key, numbers):
        self.rows[key].update(status="completed", total=sum(numbers.values()))

    def release(self, key):
        self.rows[key]["status"] = "failed"

    def usage_today(self, user_id):
        questions, _ = self._counts()
        return {"questions": questions, "limit": ai_usage.DAILY_QUESTION_LIMIT, "remaining": ai_usage.DAILY_QUESTION_LIMIT - questions}


@pytest.fixture()
def ledger(monkeypatch):
    fake = FakeLedger()
    for name in ("reserve", "settle", "release", "usage_today"):
        monkeypatch.setattr(assistant.ai_usage, name, getattr(fake, name))
    return fake


@pytest.fixture()
def actions(monkeypatch):
    created = {}

    def create(user_id, proposals, handles):
        stored = []
        for proposal in proposals:
            if proposal.get("target") and proposal["target"] not in handles:
                return [], ["A javaslat ismeretlen edzéstervre hivatkozik."]
            item = {"id": f"a{len(created)}", "action": proposal["action"], "summary": proposal["summary"], "status": "pending",
                    "planId": handles.get(proposal.get("target")), "before": {"date": "2026-10-08", "type": "Futás", "title": "Tempófutás", "duration": 50, "intensity": "közepes–magas", "rpe": 7},
                    "plan": {"date": "2026-10-08", "type": "Futás", "title": "Tempófutás", "duration": proposal.get("duration"), "intensity": proposal.get("intensity"), "rpe": proposal.get("rpe")}}
            created[item["id"]] = item
            stored.append(item)
        return stored, []

    monkeypatch.setattr(assistant.assistant_actions, "create_actions", create)
    monkeypatch.setattr(assistant.assistant_actions, "list_actions", lambda user_id, ids: {key: created[key] for key in ids if key in created})
    return created


@pytest.fixture()
def store(monkeypatch, ledger, actions):
    data = FakeStore()
    monkeypatch.setattr(assistant, "load_user_json", data.load)
    monkeypatch.setattr(assistant, "save_user_json", data.save)
    data[("u1", assistant.DASHBOARD_KEY)] = DASHBOARD
    today = assistant.datetime.now().date().isoformat()
    data[("u1", assistant.STATE_KEY)] = {"profile": {"goal": "Futóteljesítmény", "weeklyHours": 6},
                                        "plans": [{"id": "plan-secret-1", "date": today, "type": "Futás", "title": "Tempófutás",
                                                   "duration": 50, "intensity": "közepes–magas", "rpe": 7}]}
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


def test_daily_question_limit_comes_from_the_ledger(store, ledger):
    update_settings("u1", {"action": "consent", "value": True})
    for _ in range(assistant.DAILY_QUESTION_LIMIT):
        ledger.settle(ledger.reserve("u1", "answer", assistant.MODEL), {"input": 10})
    client = FakeClient()
    with pytest.raises(AssistantError, match="15 kérdéses"):
        ask("u1", "Még egy kérdés?", client)
    assert client.calls == []


def test_failed_model_call_releases_the_reservation(store, ledger):
    update_settings("u1", {"action": "consent", "value": True})
    with pytest.raises(RuntimeError):
        ask("u1", "Mit eddzek?", FakeClient(error=RuntimeError("down")))
    assert ledger.rows and all(row["status"] == "failed" for row in ledger.rows.values())
    assert ledger.usage_today("u1")["remaining"] == assistant.DAILY_QUESTION_LIMIT


def test_plan_proposal_is_stored_for_approval_not_applied(store, actions):
    update_settings("u1", {"action": "consent", "value": True})
    proposal = {"action": "upsert_plan", "target": "T1", "date": None, "type": None, "title": None, "duration": 35,
                "intensity": "könnyű", "rpe": 4, "purpose": None, "summary": "A mai tempófutás 35 perces könnyű futás lesz", "reason": "Alacsony HRV"}
    tool_turn = SimpleNamespace(stop_reason="tool_use", usage=usage(), content=[
        SimpleNamespace(type="text", text="Javaslom, hogy könnyíts."),
        SimpleNamespace(type="tool_use", id="tu1", name="propose_plan_change", input=proposal)])
    final_turn = SimpleNamespace(stop_reason="end_turn", usage=usage(), content=[SimpleNamespace(type="text", text="A javaslatot lent jóváhagyhatod.")])
    client = FakeClient(responses=[tool_turn, final_turn])
    result = ask("u1", "Könnyítsd a mai edzést", client)
    first, second = client.calls
    assert first["tools"][0]["name"] == "propose_plan_change" and first["tools"][0]["strict"] is True
    context_text = first["system"][-1]["text"]
    assert "T1" in context_text and "plan-secret-1" not in context_text  # handles, never stored IDs
    assert second["tool_choice"] == {"type": "none"}
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "tu1" and "jóváhagyásra" in tool_result["content"] and "is_error" not in tool_result
    assert actions["a0"]["planId"] == "plan-secret-1"
    reply = result["conversation"][-1]
    assert reply["content"] == "A javaslatot lent jóváhagyhatod." and reply["actions"][0]["status"] == "pending"
    actions["a0"]["status"] = "applied"
    ask("u1", "És a holnapi?", client)
    remembered = client.calls[-1]["messages"][1]["content"]
    assert "A mai tempófutás 35 perces könnyű futás lesz" in remembered and "jóváhagyta" in remembered
    context_record = client.calls[-1]["system"][-1]["text"]
    assert "tervjavaslatok_előzménye" in context_record and "jóváhagyta" in context_record and "50 perc" in context_record
    assert "promptContent" not in str(result["conversation"])


def test_invalid_proposal_is_reported_back_to_the_model(store, actions):
    update_settings("u1", {"action": "consent", "value": True})
    bad = {"action": "delete_plan", "target": "T9", "summary": "x", "reason": "y"}
    tool_turn = SimpleNamespace(stop_reason="tool_use", usage=usage(), content=[SimpleNamespace(type="tool_use", id="tu1", name="propose_plan_change", input=bad)])
    final_turn = SimpleNamespace(stop_reason="end_turn", usage=usage(), content=[SimpleNamespace(type="text", text="Ezt nem tudtam rögzíteni.")])
    client = FakeClient(responses=[tool_turn, final_turn])
    result = ask("u1", "Töröld", client)
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True
    assert actions == {} and "actions" not in result["conversation"][-1]


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
