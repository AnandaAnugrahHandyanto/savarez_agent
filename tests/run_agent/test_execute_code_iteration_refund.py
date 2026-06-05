"""Regression test for the execute_code iteration refund.

When the only tool(s) called in a turn are ``execute_code`` (programmatic
tool calling), that iteration is "free" — it must be refunded against BOTH
the iteration budget AND ``api_call_count``. The while-loop condition in
``run_conversation`` gates on ``api_call_count < max_iterations`` *and*
``iteration_budget.remaining > 0``, so refunding only the budget would let
execute_code burn down ``max_iterations`` anyway.

Bug: the execute_code refund site decremented only the budget, so a run
that made N execute_code-only turns still consumed N toward max_iterations.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from run_agent import AIAgent


class _MockHandler(BaseHTTPRequestHandler):
    # Class-level queues, reset per test.
    response_queue: list = []
    captured: list = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n).decode())
        type(self).captured.append(req)
        is_stream = req.get("stream") is True
        resp = (
            type(self).response_queue.pop(0)
            if type(self).response_queue
            else _text("FALLBACK")
        )
        msg = resp["choices"][0]["message"]
        if is_stream:
            content = msg.get("content") or ""
            tcs = msg.get("tool_calls")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunks = [{"id": "m", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]}]
            if tcs:
                chunks.append({"id": "m", "choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "id": tc["id"], "type": "function",
                     "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                    for tc in tcs]}, "finish_reason": None}]})
                chunks.append({"id": "m", "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]})
            else:
                chunks.append({"id": "m", "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]})
                chunks.append({"id": "m", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
            for c in chunks:
                self.wfile.write(f"data: {json.dumps(c)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            b = json.dumps(resp).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    def log_message(self, *a, **k):
        pass


def _exec_call(i: int) -> dict:
    return {"id": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"c{i}", "type": "function",
         "function": {"name": "execute_code", "arguments": json.dumps({"code": "print(1)"})}}]},
        "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}


def _text(t: str) -> dict:
    return {"id": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": t}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}


@pytest.fixture
def mock_server(monkeypatch, tmp_path):
    _MockHandler.response_queue = []
    _MockHandler.captured = []
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    srv = HTTPServer(("127.0.0.1", 0), _MockHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield port
    finally:
        srv.shutdown()


def _make_agent(port: int) -> AIAgent:
    return AIAgent(
        api_key="test-key",
        base_url=f"http://127.0.0.1:{port}/v1",
        provider="openai-compat",
        model="test-model",
        max_iterations=3,
        enabled_toolsets=["code_execution"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        save_trajectories=False,
        platform="cli",
    )


def test_execute_code_only_turns_are_refunded_against_max_iterations(mock_server):
    """With max_iterations=3, five execute_code-only turns followed by a
    text turn must all run — the refund keeps execute_code from counting
    toward the cap, so the loop exits via a normal text response, not
    iteration exhaustion."""
    port = mock_server
    for i in range(5):
        _MockHandler.response_queue.append(_exec_call(i))
    _MockHandler.response_queue.append(_text("finished"))

    agent = _make_agent(port)
    result = agent.run_conversation("loop", conversation_history=[], task_id="t")

    assert result["final_response"] == "finished"
    assert result["turn_exit_reason"] == "text_response(finish_reason=stop)"
    # All six provider calls were made despite max_iterations=3.
    assert len(_MockHandler.captured) == 6
    # Budget only charged for the single non-execute_code (final) turn.
    assert agent.iteration_budget.used == 1