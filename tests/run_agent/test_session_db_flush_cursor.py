from run_agent import AIAgent


class RecordingSessionDB:
    def __init__(self, existing_rows=0):
        self.appended = []
        self.existing_rows = existing_rows

    def append_message(self, **kwargs):
        self.appended.append(kwargs)

    def get_messages(self, session_id):
        return [{} for _ in range(self.existing_rows + len(self.appended))]


def _agent_with_db(last_flushed_idx, existing_rows=0):
    agent = AIAgent.__new__(AIAgent)
    agent._session_db = RecordingSessionDB(existing_rows=existing_rows)
    agent._session_db_created = True
    agent._last_flushed_db_idx = last_flushed_idx
    agent._ignore_conversation_history_on_next_flush = False
    agent._persist_user_message_idx = None
    agent._persist_user_message_override = None
    agent.session_id = "session-1"
    return agent


def test_flush_clamps_stale_cursor_when_gateway_history_is_shorter():
    """A cached gateway agent may carry a DB cursor from a longer in-memory
    transcript than the conversation_history reloaded from state.db.

    That happens after busy/steer races where the user saw the previous
    assistant response but the next turn's DB history is missing it.  The stale
    cursor must not skip the current turn's user+assistant messages; otherwise
    the gateway also skips its fallback DB write and the assistant response is
    lost again.
    """
    agent = _agent_with_db(last_flushed_idx=10, existing_rows=8)
    history = [
        {"role": "user", "content": f"old user {idx}"}
        if idx % 2 == 0
        else {"role": "assistant", "content": f"old assistant {idx}"}
        for idx in range(8)
    ]
    messages = [
        *history,
        {"role": "user", "content": "current question"},
        {"role": "assistant", "content": "current answer"},
    ]

    agent._flush_messages_to_session_db(messages, conversation_history=history)

    assert [row["role"] for row in agent._session_db.appended] == ["user", "assistant"]
    assert [row["content"] for row in agent._session_db.appended] == [
        "current question",
        "current answer",
    ]
    assert agent._last_flushed_db_idx == len(messages)


def test_flush_keeps_cursor_when_history_matches_cached_prefix():
    agent = _agent_with_db(last_flushed_idx=2)
    history = [
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "old answer"},
    ]
    messages = [
        *history,
        {"role": "user", "content": "current question"},
        {"role": "assistant", "content": "current answer"},
    ]

    agent._flush_messages_to_session_db(messages, conversation_history=history)

    assert [row["content"] for row in agent._session_db.appended] == [
        "current question",
        "current answer",
    ]
