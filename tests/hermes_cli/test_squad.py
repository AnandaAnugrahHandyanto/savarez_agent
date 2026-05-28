from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from hermes_cli import squad


def test_tmux_session_name_is_stable_and_prefixed():
    assert squad.tmux_session_name("20260528-120000-my.task") == "hermes_squad_20260528-120000-my_task"


def test_build_hermes_command_defaults_to_worktree(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hermes"])
    assert squad.build_hermes_command() == "hermes --worktree"


def test_build_hermes_command_respects_program_and_extra_args():
    command = squad.build_hermes_command(
        program="hermes --provider openrouter",
        worktree=True,
        extra_args=["--model", "anthropic/claude-sonnet-4.6"],
    )
    assert command == "hermes --provider openrouter --worktree --model anthropic/claude-sonnet-4.6"


def test_load_instances_ignores_corrupt_state(tmp_path, monkeypatch):
    monkeypatch.setattr(squad, "get_hermes_home", lambda: tmp_path)
    state = tmp_path / "squad" / "instances.json"
    state.parent.mkdir()
    state.write_text("not json", encoding="utf-8")
    assert squad.load_instances() == []


def test_save_and_load_instances_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(squad, "get_hermes_home", lambda: tmp_path)
    instance = squad.SquadInstance(
        id="abc",
        title="Backend",
        tmux_session="hermes_squad_abc",
        cwd="/repo",
        command="hermes --worktree",
        created_at="2026-05-28T00:00:00+00:00",
        prompt="Build API",
    )
    squad.save_instances([instance])

    loaded = squad.load_instances()

    assert loaded == [instance]
    raw = json.loads((tmp_path / "squad" / "instances.json").read_text(encoding="utf-8"))
    assert raw[0]["title"] == "Backend"


def test_create_instance_records_tmux_session_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(squad, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(squad, "ensure_tmux_available", lambda: None)
    monkeypatch.setattr(squad.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(squad.os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr(squad, "_now_id", lambda title: "20260528-120000-demo")

    calls: list[list[str]] = []

    def fake_run_tmux(args, *, check=True, capture=False):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(squad, "_run_tmux", fake_run_tmux)
    monkeypatch.setattr(squad, "tmux_session_exists", lambda _name: True)

    instance = squad.create_instance(
        title="Demo",
        cwd=str(tmp_path),
        command="hermes --worktree",
        prompt="Hello Hermes",
    )

    assert instance.id == "20260528-120000-demo"
    assert instance.tmux_session == "hermes_squad_20260528-120000-demo"
    assert ["new-session", "-d", "-s", instance.tmux_session, "-c", str(tmp_path.resolve()), "hermes --worktree"] in calls
    assert ["send-keys", "-t", instance.tmux_session, "Hello Hermes", "Enter"] in calls
    assert squad.load_instances()[0].title == "Demo"


def test_cmd_squad_list_prints_running_instances(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(squad, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(squad, "ensure_tmux_available", lambda: None)
    monkeypatch.setattr(squad, "tmux_session_exists", lambda _name: True)
    squad.save_instances([
        squad.SquadInstance(
            id="abc",
            title="Demo",
            tmux_session="hermes_squad_abc",
            cwd="/repo",
            command="hermes --worktree",
            created_at="now",
        )
    ])

    rc = squad.cmd_squad(SimpleNamespace(squad_action="list"))

    assert rc == 0
    assert "Demo" in capsys.readouterr().out
