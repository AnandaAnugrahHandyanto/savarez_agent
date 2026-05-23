from __future__ import annotations

from agent.conversation_loop import _inject_ephemeral_context_into_user_message


def test_injects_memory_prefetch_into_current_user_message_without_mutating_history():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "What should Hermes call the user?"},
    ]

    api_msg = _inject_ephemeral_context_into_user_message(
        messages[1],
        messages=messages,
        message_index=1,
        current_turn_user_idx=1,
        memory_prefetch="LLM Wiki relevant context: Mike page",
        plugin_user_context="",
    )

    assert "What should Hermes call the user?" in api_msg["content"]
    assert "LLM Wiki relevant context: Mike page" in api_msg["content"]
    assert messages[1]["content"] == "What should Hermes call the user?"


def test_does_not_inject_memory_prefetch_into_old_user_message():
    old_user = {"role": "user", "content": "old"}

    api_msg = _inject_ephemeral_context_into_user_message(
        old_user,
        messages=[old_user],
        message_index=0,
        current_turn_user_idx=1,
        memory_prefetch="LLM Wiki relevant context: should not appear",
        plugin_user_context="",
    )

    assert api_msg["content"] == "old"


def test_preserves_non_string_user_content_blocks():
    blocks = [{"type": "text", "text": "hello"}]
    user_msg = {"role": "user", "content": blocks}

    api_msg = _inject_ephemeral_context_into_user_message(
        user_msg,
        messages=[user_msg],
        message_index=0,
        current_turn_user_idx=0,
        memory_prefetch="LLM Wiki relevant context: block",
        plugin_user_context="",
    )

    assert api_msg["content"] == blocks
    assert user_msg["content"] == blocks
