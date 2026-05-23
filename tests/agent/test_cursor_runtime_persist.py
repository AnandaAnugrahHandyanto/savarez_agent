"""Tests for Cursor runtime transcript shaping."""

from agent.transports.cursor_event_projector import CursorEventProjector


def test_finalize_after_tool_loop_produces_single_assistant_reply():
    projector = CursorEventProjector()
    completed = projector.project(
        {
            "type": "tool_call",
            "call_id": "call-1",
            "name": "ideas_list",
            "status": "completed",
            "result": "[]",
        }
    )
    assert len(completed.messages) == 2

    finalized = projector.finalize(final_text="Here are your ideas.")
    assert len(finalized.messages) == 1
    assert finalized.messages[0]["content"] == "Here are your ideas."


def test_projector_tool_call_uses_resolved_mcp_name():
    projector = CursorEventProjector()
    completed = projector.project(
        {
            "type": "tool_call",
            "call_id": "call-1",
            "name": "mcp",
            "status": "completed",
            "args": {"toolName": "ideas_list"},
            "result": {"ok": True},
        }
    )
    assert completed.messages[0]["tool_calls"][0]["function"]["name"] == "ideas_list"
