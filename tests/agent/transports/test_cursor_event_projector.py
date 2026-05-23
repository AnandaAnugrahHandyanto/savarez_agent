"""Tests for Cursor SDK event projection into Hermes messages."""

from agent.transports.cursor_event_projector import CursorEventProjector


def test_assistant_text_buffered_until_finalize():
    projector = CursorEventProjector()
    partial = projector.project(
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Hello "}],
            },
        }
    )
    assert partial.messages == []

    result = projector.finalize(final_text="Hello from Cursor")
    assert len(result.messages) == 1
    assert result.messages[0]["role"] == "assistant"
    assert result.messages[0]["content"] == "Hello from Cursor"
    assert result.final_text == "Hello from Cursor"


def test_streaming_deltas_do_not_create_many_assistant_rows():
    projector = CursorEventProjector()
    for word in ("The", " quick", " brown", " fox"):
        out = projector.project(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": word}]},
            }
        )
        assert out.messages == []

    finalized = projector.finalize(final_text="The quick brown fox")
    assert len(finalized.messages) == 1
    assert finalized.messages[0]["content"] == "The quick brown fox"


def test_thinking_deltas_are_not_persisted():
    projector = CursorEventProjector()
    for word in ("Hmm", " maybe", " search"):
        out = projector.project({"type": "thinking", "text": word})
        assert out.messages == []

    finalized = projector.finalize(final_text="Done.")
    assert len(finalized.messages) == 1
    assert finalized.messages[0]["content"] == "Done."
    assert "reasoning" not in finalized.messages[0]


def test_tool_call_running_then_completed():
    projector = CursorEventProjector()
    running = projector.project(
        {
            "type": "tool_call",
            "call_id": "call-1",
            "name": "web_search",
            "status": "running",
            "args": {"query": "hermes agent"},
        }
    )
    assert running.messages == []

    completed = projector.project(
        {
            "type": "tool_call",
            "call_id": "call-1",
            "name": "web_search",
            "status": "completed",
            "result": {"hits": 1},
        }
    )
    assert completed.is_tool_iteration is True
    assert len(completed.messages) == 2
    assert completed.messages[0]["tool_calls"][0]["function"]["name"] == "web_search"
    assert completed.messages[1]["role"] == "tool"

    finalized = projector.finalize(final_text="Found results.")
    assert len(finalized.messages) == 1
    assert finalized.messages[0]["content"] == "Found results."
