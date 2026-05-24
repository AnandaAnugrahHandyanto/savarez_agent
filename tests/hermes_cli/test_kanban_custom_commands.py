"""Tests for hermes_cli.kanban_custom_commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import kanban_custom_commands as kcc
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def test_save_and_load_board_custom_commands(kanban_home):
    commands = [
        {"id": "cmd_test", "name": "Run tests", "icon": "🧪", "command": "npm test"},
    ]
    saved = kcc.save_board_custom_commands("default", commands)
    assert saved == commands
    assert kcc.load_board_custom_commands("default") == commands


def test_board_custom_commands_are_isolated(kanban_home):
    kb.create_board("ops")
    kb.create_board("dev")
    kcc.save_board_custom_commands(
        "ops",
        [{"id": "cmd_ops", "name": "Deploy", "icon": "🚀", "command": "deploy.sh"}],
    )
    kcc.save_board_custom_commands(
        "dev",
        [{"id": "cmd_dev", "name": "Test", "icon": "🧪", "command": "npm test"}],
    )

    ops_cmds = kcc.load_board_custom_commands("ops")
    dev_cmds = kcc.load_board_custom_commands("dev")
    assert [c["id"] for c in ops_cmds] == ["cmd_ops"]
    assert [c["id"] for c in dev_cmds] == ["cmd_dev"]


def test_find_custom_command():
    commands = [{"id": "cmd_a", "name": "A", "icon": "", "command": "echo a"}]
    assert kcc.find_custom_command(commands, "cmd_a") == commands[0]
    assert kcc.find_custom_command(commands, "missing") is None


def test_run_custom_command_in_workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    marker = ws / "done.txt"
    result = kcc.run_custom_command_in_workspace(
        ws,
        f"echo hello> {marker.name}",
    )
    assert result["ok"] is True
    assert marker.read_text(encoding="utf-8").strip() == "hello"


def test_validate_rejects_empty_name():
    with pytest.raises(ValueError, match="name and command"):
        kcc.validate_custom_commands([{"id": "cmd_x", "name": " ", "command": "echo"}])
