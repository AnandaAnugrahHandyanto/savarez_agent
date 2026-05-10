"""Regression tests for persistence-time unanswered tool-call backfill."""

from copy import deepcopy

from run_agent import AIAgent


def _agent():
    agent = AIAgent.__new__(AIAgent)
    agent.session_id = "test-session"
    return agent


def _tool_call(raw_id: str, name: str = "terminal", **extra):
    return {
        "id": raw_id,
        "type": "function",
        "function": {"name": name, "arguments": "{}"},
        **extra,
    }


def _assistant_with_tools(*call_ids: str):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [_tool_call(call_id) for call_id in call_ids],
    }


def _tool_result(call_id: str, content: str = "ok"):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _agent_with_stubbed_persistence():
    agent = _agent()
    agent._persist_user_message_idx = None
    agent._persist_user_message_override = None
    agent._session_messages = []
    agent.saved_session_logs = []
    agent.flushed_session_db_messages = []
    agent._save_session_log = lambda messages: agent.saved_session_logs.append(
        [m.copy() for m in messages]
    )
    agent._flush_messages_to_session_db = lambda messages, conversation_history=None: (
        agent.flushed_session_db_messages.append([m.copy() for m in messages])
    )
    return agent


class _RecordingSessionDB:
    def __init__(self):
        self.appended = []

    def append_message(self, **kwargs):
        self.appended.append(kwargs)


def _agent_with_recording_db():
    agent = _agent()
    agent._persist_user_message_idx = None
    agent._persist_user_message_override = None
    agent._session_messages = []
    agent._session_db = _RecordingSessionDB()
    agent._session_db_created = True
    agent._last_flushed_db_idx = 0
    agent._save_session_log = lambda messages: None
    return agent


def test_sanitize_unanswered_tool_calls_inserts_tail_stubs():
    agent = _agent()
    messages = [
        {"role": "user", "content": "run two things"},
        _assistant_with_tools("c1", "c2"),
    ]

    inserted = agent._sanitize_unanswered_tool_calls(messages)

    assert inserted == 2
    assert [m.get("role") for m in messages] == ["user", "assistant", "tool", "tool"]
    assert [m.get("tool_call_id") for m in messages[2:]] == ["c1", "c2"]
    assert all("interrupted" in m["content"] for m in messages[2:])


def test_sanitize_unanswered_tool_calls_fills_only_missing_parallel_result():
    agent = _agent()
    messages = [
        _assistant_with_tools("c1", "c2"),
        _tool_result("c1", "real result"),
    ]

    inserted = agent._sanitize_unanswered_tool_calls(messages)

    assert inserted == 1
    assert messages[1] == _tool_result("c1", "real result")
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_call_id"] == "c2"


def test_sanitize_unanswered_tool_calls_inserts_before_next_user():
    agent = _agent()
    messages = [
        _assistant_with_tools("c1"),
        {"role": "user", "content": "interrupt follow-up"},
    ]

    inserted = agent._sanitize_unanswered_tool_calls(messages)

    assert inserted == 1
    assert [m.get("role") for m in messages] == ["assistant", "tool", "user"]
    assert messages[1]["tool_call_id"] == "c1"
    assert messages[2]["content"] == "interrupt follow-up"


def test_sanitize_unanswered_tool_calls_is_idempotent():
    agent = _agent()
    messages = [_assistant_with_tools("c1", "c2")]

    first = agent._sanitize_unanswered_tool_calls(messages)
    second = agent._sanitize_unanswered_tool_calls(messages)

    assert first == 2
    assert second == 0
    assert [m.get("tool_call_id") for m in messages if m.get("role") == "tool"] == [
        "c1",
        "c2",
    ]


def test_sanitize_unanswered_tool_calls_uses_call_id_over_id():
    agent = _agent()
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                _tool_call(
                    "fc_123",
                    call_id="call_123",
                    response_item_id="fc_123",
                )
            ],
        }
    ]

    inserted = agent._sanitize_unanswered_tool_calls(messages)

    assert inserted == 1
    assert messages[1]["tool_call_id"] == "call_123"


def test_sanitize_unanswered_tool_calls_preserves_complete_turn():
    agent = _agent()
    messages = [
        _assistant_with_tools("c1"),
        _tool_result("c1"),
        {"role": "assistant", "content": "done"},
    ]
    original = deepcopy(messages)

    inserted = agent._sanitize_unanswered_tool_calls(messages)

    assert inserted == 0
    assert messages == original


def test_sanitize_unanswered_tool_calls_uses_custom_error_content():
    agent = _agent()
    messages = [_assistant_with_tools("c1")]

    inserted = agent._sanitize_unanswered_tool_calls(
        messages,
        content="Error executing tool: boom",
    )

    assert inserted == 1
    assert messages[1]["content"] == "Error executing tool: boom"


def test_persist_session_backfills_before_log_and_db_flush():
    agent = _agent_with_stubbed_persistence()
    messages = [
        {"role": "user", "content": "run two things"},
        _assistant_with_tools("c1", "c2"),
        _tool_result("c1", "real result"),
    ]

    agent._persist_session(messages, conversation_history=[])

    assert [m.get("tool_call_id") for m in messages if m.get("role") == "tool"] == [
        "c1",
        "c2",
    ]
    assert agent.saved_session_logs[-1] == messages
    assert agent.flushed_session_db_messages[-1] == messages


def test_persist_session_flushes_backfill_after_conversation_history_boundary():
    agent = _agent_with_recording_db()
    conversation_history = [{"role": "user", "content": "old"}]
    messages = [
        *conversation_history,
        {"role": "user", "content": "run"},
        _assistant_with_tools("c1"),
    ]

    agent._persist_session(messages, conversation_history=conversation_history)

    assert [m["role"] for m in agent._session_db.appended] == [
        "user",
        "assistant",
        "tool",
    ]
    assert agent._session_db.appended[-1]["tool_call_id"] == "c1"
    assert "interrupted" in agent._session_db.appended[-1]["content"]


def test_persist_session_strips_empty_scaffolding_before_backfill():
    agent = _agent_with_stubbed_persistence()
    messages = [
        {"role": "user", "content": "run the task"},
        _assistant_with_tools("c1"),
        {"role": "assistant", "content": "(empty)", "_empty_terminal_sentinel": True},
    ]

    agent._persist_session(messages, conversation_history=[])

    assert messages == [{"role": "user", "content": "run the task"}]
    assert agent.saved_session_logs[-1] == messages
    assert agent.flushed_session_db_messages[-1] == messages


def test_persist_session_applies_user_override_before_backfill_shifts_indices():
    agent = _agent_with_stubbed_persistence()
    agent._persist_user_message_idx = 1
    agent._persist_user_message_override = "clean user text"
    messages = [
        _assistant_with_tools("c1"),
        {"role": "user", "content": "api-only user text"},
    ]

    agent._persist_session(messages, conversation_history=[])

    assert [m.get("role") for m in messages] == ["assistant", "tool", "user"]
    assert messages[2]["content"] == "clean user text"
    assert agent.saved_session_logs[-1] == messages
