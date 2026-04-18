from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


@pytest.fixture()
def agent():
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("todo", "web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        instance = AIAgent(
            api_key="test-key-1234567890",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        instance.client = MagicMock()
        return instance


class TestOrchestrationContinuationSnapshot:
    def test_snapshot_reports_active_todos_for_incomplete_run(self, agent):
        agent._todo_store.write(
            [
                {"id": "plan", "content": "Inspect runtime logs", "status": "in_progress"},
                {"id": "done", "content": "Document old issue", "status": "completed"},
            ]
        )

        snapshot = agent.get_orchestration_continuation_snapshot(
            {
                "completed": False,
                "interrupted": True,
                "failed": False,
                "final_response": "Interrupted during the final tool call.",
            }
        )

        assert snapshot["outcomeStatus"] == "interrupted"
        assert [item["id"] for item in snapshot["activeTodos"]] == ["plan"]
        assert snapshot["responsePreview"] == "Interrupted during the final tool call."

    def test_snapshot_marks_completed_when_no_open_todos_remain(self, agent):
        agent._todo_store.write(
            [
                {"id": "plan", "content": "Inspect runtime logs", "status": "completed"},
            ]
        )

        snapshot = agent.get_orchestration_continuation_snapshot(
            {
                "completed": True,
                "interrupted": False,
                "failed": False,
                "final_response": "All requested work is complete.",
            }
        )

        assert snapshot["outcomeStatus"] == "completed"
        assert snapshot["activeTodos"] == []
        assert snapshot["responsePreview"] == "All requested work is complete."
