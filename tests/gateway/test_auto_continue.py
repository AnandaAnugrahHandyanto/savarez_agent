"""Tests for the auto-continue feature (#4493).

When the gateway restarts mid-agent-work, the session transcript ends on a
tool result that the agent never processed.  The auto-continue logic detects
this and prepends a system note to the next user message so the model
finishes the interrupted work before addressing the new input.
"""

import pytest


def _simulate_auto_continue(agent_history: list, user_message: str) -> str:
    """Reproduce the auto-continue injection logic from _run_agent().

    This mirrors the exact code in gateway/run.py so we can test the
    detection and message transformation without spinning up a full
    gateway runner.
    """
    message = user_message
    if agent_history and agent_history[-1].get("role") == "tool":
        message = (
            "[System note: Address the user's new message below as the primary task. "
            "An orphaned tool result from a previous interrupted turn exists in history — "
            "reference or summarize it ONLY if it is directly relevant to the user's new message. "
            "If the new message is on a different topic, treat the orphan as resolved and ignore it. "
            "Do NOT lead your reply with stale-topic content.]\n\n"
            + message
        )
    return message


class TestAutoDetection:
    """Test that trailing tool results are correctly detected."""

    def test_trailing_tool_result_triggers_note(self):
        history = [
            {"role": "user", "content": "deploy the app"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "function": {"name": "terminal", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "deployed successfully"},
        ]
        result = _simulate_auto_continue(history, "what happened?")
        assert "[System note:" in result
        assert "interrupted" in result
        assert "what happened?" in result

    def test_trailing_assistant_message_no_note(self):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = _simulate_auto_continue(history, "how are you?")
        assert "[System note:" not in result
        assert result == "how are you?"

    def test_empty_history_no_note(self):
        result = _simulate_auto_continue([], "hello")
        assert result == "hello"

    def test_trailing_user_message_no_note(self):
        """Shouldn't happen in practice, but ensure no false positive."""
        history = [
            {"role": "user", "content": "hello"},
        ]
        result = _simulate_auto_continue(history, "hello again")
        assert result == "hello again"

    def test_multiple_tool_results_still_triggers(self):
        """Multiple tool calls in a row — last one is still role=tool."""
        history = [
            {"role": "user", "content": "search and read"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "function": {"name": "search", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "read", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "found it"},
            {"role": "tool", "tool_call_id": "call_2", "content": "file content here"},
        ]
        result = _simulate_auto_continue(history, "continue")
        assert "[System note:" in result

    def test_original_message_preserved_after_note(self):
        """The user's actual message must appear after the system note."""
        history = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "function": {"name": "t", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "done"},
        ]
        result = _simulate_auto_continue(history, "now do X")
        # System note comes first, then user's message
        note_end = result.index("]\n\n")
        user_msg_start = result.index("now do X")
        assert user_msg_start > note_end

    def test_prompt_prioritizes_new_message_and_allows_ignoring_orphan(self):
        """Regression: the recovery prompt must lead with the new message as
        the primary task and explicitly allow ignoring topic-mismatched
        orphan tool results, to prevent stale-topic drift (see fix:
        reorder interrupt-recovery prompt to prevent topic drift).
        """
        history = [
            {"role": "user", "content": "probe the weather API"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "function": {"name": "http_get", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "{\"temp\": 72}"},
        ]
        # New user message is on a totally different topic
        result = _simulate_auto_continue(history, "what's 2+2?")

        # The new message must be present and the system note must instruct
        # the model to treat the new message as the primary task.
        assert "what's 2+2?" in result
        lowered = result.lower()
        assert "primary task" in lowered
        assert "new message" in lowered
        # Must permit ignoring the orphan when topics differ.
        assert "ignore" in lowered or "treat the orphan as resolved" in lowered
        assert "different topic" in lowered
        # Must explicitly forbid leading the reply with stale-topic content.
        assert "stale-topic" in lowered or "do not lead" in lowered
        # Must NOT contain the old "process old results first" framing.
        assert "finish processing" not in lowered
        assert "process them first" not in lowered
        # System note still comes before the user's actual message.
        note_end = result.index("]\n\n")
        user_msg_start = result.index("what's 2+2?")
        assert user_msg_start > note_end
