from datetime import datetime

from gateway.run import (
    _gateway_tool_tail_recovery_ack_matches,
    _gateway_tool_tail_recovery_key,
)
from gateway.session import Platform, SessionEntry


def test_tool_tail_recovery_key_changes_with_tail_content():
    history = [
        {"role": "user", "content": "run it"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "call_1", "function": {"name": "terminal"}}],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "terminal",
            "content": "partial output",
        },
    ]

    key = _gateway_tool_tail_recovery_key(history)

    assert key
    assert key == _gateway_tool_tail_recovery_key(list(history))

    changed = [*history]
    changed[-1] = {**changed[-1], "content": "different output"}
    assert _gateway_tool_tail_recovery_key(changed) != key


def test_tool_tail_recovery_ack_survives_session_entry_round_trip():
    entry = SessionEntry(
        session_key="agent:main:telegram:dm:chat",
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        auto_continue_tool_tail_key="tail-key",
        auto_continue_tool_tail_ack_at=datetime.now(),
    )

    restored = SessionEntry.from_dict(entry.to_dict())

    assert _gateway_tool_tail_recovery_ack_matches(restored, "tail-key")
    assert not _gateway_tool_tail_recovery_ack_matches(restored, "other-key")


def test_tool_tail_recovery_ack_blocks_repeated_recovery_for_same_tail():
    history = [
        {"role": "assistant", "tool_calls": [{"id": "call_1"}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "output"},
    ]
    key = _gateway_tool_tail_recovery_key(history)
    entry = SessionEntry(
        session_key="agent:main:telegram:dm:chat",
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        auto_continue_tool_tail_key=key,
        auto_continue_tool_tail_ack_at=datetime.now(),
    )

    should_recover = bool(key and not _gateway_tool_tail_recovery_ack_matches(entry, key))

    assert should_recover is False
