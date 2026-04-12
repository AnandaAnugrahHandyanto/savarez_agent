from hermes_state import SessionDB


def test_upsert_and_list_live_sessions(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    db.upsert_live_session(
        "sess_a",
        source="cli",
        role="orchestrator",
        display_name="planner",
        model="gpt-5.4",
        provider="openai",
        cwd="/tmp/project",
        pid=111,
        host="box",
        agent_running=True,
    )

    rows = db.list_live_sessions()
    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == "sess_a"
    assert row["role"] == "orchestrator"
    assert row["display_name"] == "planner"
    assert row["agent_running"] is True
    assert row["is_active"] is True


def test_resolve_live_session_supports_prefix_role_and_label(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    db.upsert_live_session("20260412_aaaaaa", source="cli", role="orchestrator", display_name="planner")
    db.upsert_live_session("20260412_bbbbbb", source="cli", role="executor", display_name="coder")

    row, error = db.resolve_live_session("20260412_b")
    assert error is None
    assert row["session_id"] == "20260412_bbbbbb"

    row, error = db.resolve_live_session("executor")
    assert error is None
    assert row["session_id"] == "20260412_bbbbbb"

    row, error = db.resolve_live_session("planner")
    assert error is None
    assert row["session_id"] == "20260412_aaaaaa"


def test_claim_live_messages_marks_them_consumed(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    db.upsert_live_session("receiver", source="cli")
    msg_id = db.queue_live_message(
        target_session_id="receiver",
        sender_session_id="sender",
        sender_label="orchestrator",
        sender_model="gpt-5.4",
        body="Implement the patch",
    )

    claimed = db.claim_live_messages("receiver")
    assert [row["id"] for row in claimed] == [msg_id]
    assert claimed[0]["body"] == "Implement the patch"
    assert claimed[0]["sender_label"] == "orchestrator"

    assert db.claim_live_messages("receiver") == []
