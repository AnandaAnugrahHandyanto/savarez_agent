"""Telegram /project intake should create Kanban triage cards, not dispatch work."""

from types import SimpleNamespace

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli.commands import resolve_command, should_bypass_active_session
from hermes_cli import kanban_db as kb


class _FakeProjectIntakeAdapter:
    platform = Platform.TELEGRAM

    def __init__(self):
        self.calls = []
        self.callback = None

    async def send_project_intake_prompt(
        self,
        *,
        chat_id,
        title,
        state,
        session_key,
        on_intake_selected,
        metadata=None,
    ):
        self.calls.append(
            {
                "chat_id": chat_id,
                "title": title,
                "state": state,
                "session_key": session_key,
                "metadata": metadata,
            }
        )
        self.callback = on_intake_selected
        return SimpleNamespace(success=True, message_id="project-intake-msg")


def _runner(adapter):
    runner = object.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner.session_store = None
    runner.config = SimpleNamespace(
        group_sessions_per_user=True,
        thread_sessions_per_user=False,
    )
    return runner


def _event(text="/project Build OUZY KB intake"):
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="12345",
            chat_type="dm",
            user_id="42",
            user_name="Joseph",
            message_id="m-1",
        ),
    )


def test_project_command_is_registered_and_bypasses_active_sessions():
    cmd = resolve_command("project")

    assert cmd is not None
    assert cmd.gateway_only is True
    assert should_bypass_active_session("project") is True


@pytest.mark.asyncio
async def test_project_command_creates_non_dispatchable_triage_card(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "default")
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    kb._INITIALIZED_PATHS.clear()

    adapter = _FakeProjectIntakeAdapter()
    runner = _runner(adapter)

    result = await GatewayRunner._handle_project_command(runner, _event())

    assert result is None
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["title"] == "Build OUZY KB intake"
    assert callable(adapter.callback)

    confirmation = await adapter.callback(
        {
            "title": "Build OUZY KB intake",
            "description": "Create a mobile intake path for new projects.",
            "answers": {
                "kind": "feature",
                "board": "control",
                "scope": "spec",
                "risk": "manual",
            },
            "source": {
                "platform": "telegram",
                "chat_id": "12345",
            },
        }
    )

    assert "Project intake card created" in confirmation
    assert "Status: triage" in confirmation
    assert "not dispatchable" in confirmation.lower()

    with kb.connect(board="default") as conn:
        rows = conn.execute(
            "SELECT id, title, body, assignee, status, created_by FROM tasks"
        ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row["title"] == "Project intake: Build OUZY KB intake"
    assert row["status"] == "triage"
    assert row["assignee"] is None
    assert row["created_by"] == "telegram-project-intake"
    assert "TRIAGE / INTAKE / NOT DISPATCHABLE" in row["body"]
    assert "Dispatch gate: do not assign or dispatch" in row["body"]
    assert "Kind: Feature / UX improvement" in row["body"]
    assert "Risk gate: Human review before any dispatch" in row["body"]
