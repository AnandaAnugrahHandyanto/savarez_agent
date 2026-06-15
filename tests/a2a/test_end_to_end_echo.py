"""End-to-end JSON-RPC over the real Starlette app, in-process, no LLM.

Builds the actual A2A app (card + DefaultRequestHandler + InMemoryTaskStore)
around an echo agent and drives a ``message/send`` request through it via the
Starlette test client — exercising the full transport path (routing, JSON-RPC
decode, executor, event consumption, task assembly).
"""

from __future__ import annotations

import json

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from starlette.testclient import TestClient

from a2a_adapter.card import build_agent_card
from a2a_adapter.executor import HermesAgentExecutor
from a2a_adapter.sessions import ContextSessionStore


def _build_echo_client(fakes) -> TestClient:
    store = ContextSessionStore(agent_factory=fakes.FakeAgent)
    handler = DefaultRequestHandler(
        agent_executor=HermesAgentExecutor(store),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=build_agent_card("http://test/"),
        http_handler=handler,
    ).build()
    return TestClient(app)


def test_message_send_returns_completed_task_with_echo(fakes):
    client = _build_echo_client(fakes)
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "kind": "message",
                "messageId": "m1",
                "parts": [{"kind": "text", "text": "ping"}],
            }
        },
    }
    resp = client.post("/", json=request)
    assert resp.status_code == 200
    body = resp.json()
    assert "error" not in body, body
    result = body["result"]

    # message/send returns the final Task once it reaches a terminal state.
    assert result["kind"] == "task"
    assert result["status"]["state"] == "completed"

    # The echo response is delivered as an artifact.
    text = result["artifacts"][0]["parts"][0]["text"]
    assert text == "echo: ping"
    # Sanity: the whole payload mentions the echo.
    assert "echo: ping" in json.dumps(body)
