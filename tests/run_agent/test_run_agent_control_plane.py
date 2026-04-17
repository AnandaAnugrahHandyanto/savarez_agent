from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent
from tools.memory_tool import MemoryStore


class _FakeDB:
    def search_messages(self, **kwargs):
        return [
            {
                "session_id": "sess-1",
                "content": "We decided proof receipts needed one canonical format.",
                "session_started": 1710000000,
                "source": "cli",
                "model": "gpt-test",
            }
        ]

    def get_session(self, session_id):
        return {"session_id": session_id, "parent_session_id": None, "started_at": 1710000000}


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _mock_response(content="ok"):
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    resp = SimpleNamespace(choices=[choice], model="test/model", usage=None)
    return resp


@pytest.fixture()
def agent(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search", "memory")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
        return agent


def test_run_conversation_injects_control_plane_recall_and_stores_receipt(agent, tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    store = MemoryStore()
    store.load_from_disk()
    store.add("memory", "Never claim done without proof.", kind="constraint", source="test")

    agent._memory_store = store
    agent._session_db = _FakeDB()
    agent._pending_clerk_recall_context = "next: verify the proof receipt path"
    agent.client.chat.completions.create.return_value = _mock_response("ack")

    result = agent.run_conversation("what did we decide about proof before reset?")

    assert result["final_response"] == "ack"
    messages = agent.client.chat.completions.create.call_args.kwargs["messages"]
    user_messages = [m for m in messages if m.get("role") == "user"]
    assert user_messages
    current_user = user_messages[-1]["content"]
    assert "<memory-context>" in current_user
    assert "Never claim done without proof." in current_user
    assert "proof receipts needed one canonical format" in current_user
    assert "next: verify the proof receipt path" in current_user
    assert "sqlite_memory" in agent._last_recall_receipt["lanes_used"]
    assert "session_search" in agent._last_recall_receipt["lanes_used"]
    assert "clerk_reset" in agent._last_recall_receipt["lanes_used"]
