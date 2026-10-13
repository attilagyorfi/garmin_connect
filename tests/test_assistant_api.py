import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest


def endpoint():
    spec = importlib.util.spec_from_file_location("assistant_endpoint", Path(__file__).parents[1] / "api" / "assistant.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    """Records the raw HTTP response the handler writes."""

    def __init__(self, fail_after=None):
        self.status, self.headers, self.chunks, self.flushes, self.fail_after = None, {}, [], 0, fail_after

    def write(self, data):
        if self.fail_after is not None and len(self.chunks) >= self.fail_after:
            raise BrokenPipeError()
        self.chunks.append(data)

    def flush(self):
        self.flushes += 1


def handler_for(module, payload, monkeypatch, recorder):
    raw = json.dumps(payload).encode("utf-8")
    handler = object.__new__(module.handler)
    handler.headers = {"Content-Length": str(len(raw))}
    handler.rfile, handler.wfile = BytesIO(raw), recorder
    handler.send_response = lambda status: setattr(recorder, "status", status)
    handler.send_header = lambda key, value: recorder.headers.__setitem__(key, value)
    handler.end_headers = lambda: None
    monkeypatch.setattr(module, "current_user", lambda _headers: {"id": "u1"})
    return handler


def events(recorder):
    return [json.loads(line) for line in b"".join(recorder.chunks).decode("utf-8").splitlines()]


def test_stream_sends_pieces_reset_and_final_state(monkeypatch):
    module = endpoint()

    def fake_ask(user_id, question, on_delta=None, on_reset=None):
        on_delta("Javaslom")
        on_reset()
        on_delta("Lent ")
        on_delta("jóváhagyhatod.")
        return {"answer": "Lent jóváhagyhatod.", "conversation": [], "usage": {"remaining": 14}}

    monkeypatch.setattr(module, "ask", fake_ask)
    recorder = Recorder()
    handler_for(module, {"action": "ask", "question": "Mi legyen?", "stream": True}, monkeypatch, recorder).do_POST()
    assert recorder.status == 200 and recorder.headers["Content-Type"].startswith("application/x-ndjson")
    assert recorder.headers["Cache-Control"] == "private, no-store" and "Content-Length" not in recorder.headers
    assert [event["type"] for event in events(recorder)] == ["delta", "reset", "delta", "delta", "done"]
    assert events(recorder)[-1]["answer"] == "Lent jóváhagyhatod." and recorder.flushes == 5


def test_checks_before_the_first_piece_get_a_plain_json_error(monkeypatch):
    module = endpoint()
    monkeypatch.setattr(module, "ask", Mock(side_effect=module.AssistantError("Elérted a mai 15 kérdéses keretet.")))
    handler = handler_for(module, {"action": "ask", "question": "Mi legyen?", "stream": True}, monkeypatch, Recorder())
    handler._send = Mock()
    handler.do_POST()
    assert handler._send.call_args.args == ({"error": "Elérted a mai 15 kérdéses keretet."}, 400)


def test_failure_mid_stream_ends_with_an_error_event(monkeypatch):
    module = endpoint()

    def fake_ask(user_id, question, on_delta=None, on_reset=None):
        on_delta("Ma ")
        raise RuntimeError("upstream")

    monkeypatch.setattr(module, "ask", fake_ask)
    recorder = Recorder()
    handler_for(module, {"action": "ask", "question": "Mi legyen?", "stream": True}, monkeypatch, recorder).do_POST()
    assert [event["type"] for event in events(recorder)] == ["delta", "error"]
    assert "upstream" not in events(recorder)[-1]["error"]


def test_closed_connection_does_not_abort_the_answer(monkeypatch):
    module = endpoint()
    finished = []

    def fake_ask(user_id, question, on_delta=None, on_reset=None):
        for piece in ("Ma ", "könnyű ", "nap."):
            on_delta(piece)
        finished.append(True)
        return {"answer": "Ma könnyű nap."}

    monkeypatch.setattr(module, "ask", fake_ask)
    handler_for(module, {"action": "ask", "question": "Mi legyen?", "stream": True}, monkeypatch, Recorder(fail_after=1)).do_POST()
    assert finished == [True]


@pytest.mark.parametrize("payload", [{"action": "ask", "question": "Mi legyen?"}])
def test_non_streaming_ask_still_returns_json(monkeypatch, payload):
    module = endpoint()
    monkeypatch.setattr(module, "ask", lambda user_id, question: {"answer": "ok"})
    handler = handler_for(module, payload, monkeypatch, Recorder())
    handler._send = Mock()
    handler.do_POST()
    assert handler._send.call_args.args == ({"answer": "ok"},)
