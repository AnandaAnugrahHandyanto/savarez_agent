"""Tests for the shared action-stall wire-protocol module."""

from agent.action_stall import (
    ACTION_STALL_EVENT_PREFIX,
    latest_user_message_is_stall_continuation,
)


class TestActionStallEventPrefix:
    def test_prefix_is_stable_protocol_string(self):
        # Producer (gateway.run._build_action_stall_continuation) and consumer
        # (agent.transports.codex.build_kwargs) both depend on this exact text.
        # Changing it is a wire-protocol break — assert it explicitly.
        assert ACTION_STALL_EVENT_PREFIX == (
            "[System corrective continuation: tool execution required]"
        )


class TestLatestUserMessageIsStallContinuation:
    def test_empty_messages_returns_false(self):
        assert latest_user_message_is_stall_continuation([]) is False
        assert latest_user_message_is_stall_continuation(None) is False

    def test_string_content_with_prefix_returns_true(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_string_content_without_prefix_returns_false(self):
        messages = [{"role": "user", "content": "just a normal request"}]
        assert latest_user_message_is_stall_continuation(messages) is False

    def test_leading_whitespace_tolerated(self):
        messages = [
            {"role": "user", "content": f"  \n  {ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_list_content_parts_with_prefix_returns_true(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
                ],
            },
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_only_inspects_latest_user_message(self):
        """An older user message with the prefix must not trigger on a later
        normal user turn — the stall force is per-turn."""
        messages = [
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
            {"role": "assistant", "content": "tool call happened"},
            {"role": "user", "content": "thanks, do this next thing"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is False

    def test_skips_non_user_trailing_entries(self):
        """Tool/assistant entries after the latest user message must not hide
        the user message we care about."""
        messages = [
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
            {"role": "assistant", "content": "..."},
            {"role": "tool", "content": "result"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_non_dict_entries_ignored(self):
        messages = [
            "not a dict",
            None,
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_missing_content_returns_false(self):
        messages = [{"role": "user"}]
        assert latest_user_message_is_stall_continuation(messages) is False

    def test_returns_false_when_prior_assistant_already_emitted_tool_calls(self):
        """Defensive check: if work was already done on the previous turn,
        forcing tool_choice=required now would either loop or contradict the
        agent's just-completed action.  The stall guard is only meant to
        recover narration-without-tool_use turns.
        """
        messages = [
            {"role": "user", "content": "send the report"},
            {"role": "assistant", "tool_calls": [{"id": "c1", "function": {"name": "send"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is False

    def test_returns_true_when_prior_assistant_had_no_tool_calls(self):
        """Normal stall-recovery case: assistant turn emitted only prose."""
        messages = [
            {"role": "user", "content": "send the report"},
            {"role": "assistant", "content": "I will now send the report."},
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True

    def test_returns_true_when_no_prior_assistant_turn_at_all(self):
        """First-turn edge case: stall continuation as the very first user
        entry (shouldn't happen in production but defend against it).
        """
        messages = [
            {"role": "user", "content": f"{ACTION_STALL_EVENT_PREFIX}\nAttempt: 1/2"},
        ]
        assert latest_user_message_is_stall_continuation(messages) is True
