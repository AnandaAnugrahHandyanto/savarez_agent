"""Regression tests for foreground CLI mobile-control bridge."""

from __future__ import annotations

import queue

from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj._foreground_bridge_key = "cli-test"
    cli_obj._foreground_bridge_commands = {}
    cli_obj._pending_input = queue.Queue()
    cli_obj._agent_running = False
    cli_obj._command_running = False
    cli_obj.session_id = "session-test"
    return cli_obj


def test_foreground_bridge_does_not_claim_command_while_agent_busy(monkeypatch):
    """Busy CLI must leave pending command visible instead of fetching then dropping it."""
    cli_obj = _make_cli()
    cli_obj._agent_running = True

    calls = []

    class FakeBridge:
        @staticmethod
        def register_client(*args, **kwargs):
            calls.append(("register", args, kwargs))

        @staticmethod
        def fetch_next_command(client_key):  # pragma: no cover - should not run
            calls.append(("fetch", client_key))
            raise AssertionError("busy CLI must not fetch/claim pending commands")

    monkeypatch.setitem(__import__("sys").modules, "gateway.foreground_cli_bridge", FakeBridge)

    cli_obj._check_foreground_bridge_commands()

    assert [name for name, *_ in calls] == ["register"]
    assert cli_obj._pending_input.empty()
    assert cli_obj._foreground_bridge_commands == {}


def test_foreground_bridge_updates_last_user_when_idle(monkeypatch):
    cli_obj = _make_cli()
    updates = []
    completed = []
    command = {"id": "cmd-1", "text": "真实用户最后指令"}

    class FakeBridge:
        @staticmethod
        def register_client(*args, **kwargs):
            pass

        @staticmethod
        def fetch_next_command(client_key):
            return command

        @staticmethod
        def update_client(client_key, **fields):
            updates.append((client_key, fields))

        @staticmethod
        def complete_command(command_id, response=None, error=None):
            completed.append((command_id, response, error))

    monkeypatch.setitem(__import__("sys").modules, "gateway.foreground_cli_bridge", FakeBridge)

    cli_obj._check_foreground_bridge_commands()

    assert cli_obj._pending_input.get_nowait() == "真实用户最后指令"
    assert cli_obj._foreground_bridge_commands["真实用户最后指令"] == command
    assert updates == [
        (
            "cli-test",
            {
                "status": "running",
                "last_user": "真实用户最后指令",
                "session_id": "session-test",
            },
        )
    ]
    assert completed == []
