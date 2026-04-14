import json
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


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


def test_memory_add_is_mirrored_into_knowledge_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("memory")),
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
        agent._memory_store = MagicMock()

        with patch(
            "tools.memory_tool.memory_tool",
            return_value=json.dumps({"success": True, "message": "Entry added."}),
        ):
            agent._invoke_tool(
                "memory",
                {
                    "action": "add",
                    "target": "memory",
                    "content": "Tiger Smart Invest likely uses post-spend replenishment, not true instant redemption.",
                },
                effective_task_id="test",
            )

    payload = json.loads((tmp_path / "knowledge" / "knowledge_lanes.json").read_text())
    assert len(payload["draft_items"]) == 1
    draft = payload["draft_items"][0]
    assert draft["source"] == "memory_tool:memory:add"
    assert draft["status"] == "draft"


def test_failed_memory_write_does_not_create_knowledge_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("memory")),
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
        agent._memory_store = MagicMock()

        with patch(
            "tools.memory_tool.memory_tool",
            return_value=json.dumps({"success": False, "error": "blocked"}),
        ):
            agent._invoke_tool(
                "memory",
                {
                    "action": "add",
                    "target": "memory",
                    "content": "bad",
                },
                effective_task_id="test",
            )

    assert not (tmp_path / "knowledge" / "knowledge_lanes.json").exists()
