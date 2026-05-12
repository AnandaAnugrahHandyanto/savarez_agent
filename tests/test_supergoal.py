from types import SimpleNamespace


def test_create_supergoal_creates_kanban_parent_and_subscription(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.delenv("HERMES_KANBAN_BOARD", raising=False)

    from hermes_cli import kanban_db as kb
    kb._INITIALIZED_PATHS.clear()

    from hermes_cli.supergoal import create_supergoal

    source = SimpleNamespace(
        platform="telegram",
        chat_id="-100123",
        thread_id="42",
        user_id="nacho",
    )

    result = create_supergoal(
        "ship PairJoy TestFlight",
        source=source,
        created_by="nacho",
    )

    assert result.task_id.startswith("t_")
    assert "orchestrate supergoal" in result.kickoff_prompt
    assert result.task_id in result.kickoff_prompt

    with kb.connect() as conn:
        task = kb.get_task(conn, result.task_id)
        assert task is not None
        assert task.title == "Supergoal: ship PairJoy TestFlight"
        assert task.status == "ready"
        assert task.created_by == "nacho"
        assert "Acceptance criteria" in (task.body or "")
        assert "No worker may mark work done without proof" in (task.body or "")

        subs = kb.list_notify_subs(conn, result.task_id)
        assert len(subs) == 1
        assert subs[0]["platform"] == "telegram"
        assert subs[0]["chat_id"] == "-100123"
        assert subs[0]["thread_id"] == "42"


def test_supergoal_command_is_registered():
    from hermes_cli.commands import resolve_command

    cmd = resolve_command("supergoal")
    assert cmd is not None
    assert cmd.category == "Session"
    assert "status" in (cmd.args_hint or "")
