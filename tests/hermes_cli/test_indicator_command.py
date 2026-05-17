"""Regression test for issue #27603: /indicator slash command had no handler.

The command is defined in COMMAND_REGISTRY but `HermesCLI.process_command()`
did not dispatch it, causing "Unknown command: /indicator <style>".
"""
from __future__ import annotations

import importlib
import sys
import types

import pytest


def test_indicator_command_registered():
    from hermes_cli.commands import COMMAND_REGISTRY, resolve_command

    names = [c.name for c in COMMAND_REGISTRY]
    assert "indicator" in names

    cdef = resolve_command("indicator")
    assert cdef is not None and cdef.name == "indicator"


def test_indicator_handler_exists_and_dispatched():
    """The HermesCLI class must expose _handle_indicator_command, and
    process_command() must dispatch /indicator to it."""
    import cli as cli_mod

    assert hasattr(cli_mod.HermesCLI, "_handle_indicator_command"), (
        "HermesCLI is missing _handle_indicator_command — /indicator will fall "
        "through to 'Unknown command' (issue #27603)."
    )

    # Source-level check that the dispatch is wired in process_command.
    src = cli_mod.__file__
    with open(src, "r") as f:
        text = f.read()
    assert 'canonical == "indicator"' in text, (
        "process_command() is missing the `elif canonical == \"indicator\"` branch."
    )


def test_indicator_handler_saves_config_value(monkeypatch):
    """Calling _handle_indicator_command with a valid style should call
    save_config_value('display.tui_status_indicator', <style>)."""
    import cli as cli_mod

    calls: list[tuple] = []

    def fake_save(key, value):
        calls.append((key, value))
        return True

    monkeypatch.setattr(cli_mod, "save_config_value", fake_save)
    monkeypatch.setattr(cli_mod, "load_cli_config", lambda: {"display": {}})

    # Build a minimal stand-in for `self`; the handler only uses module-level
    # helpers, so an empty object is sufficient.
    fake_self = types.SimpleNamespace()
    cli_mod.HermesCLI._handle_indicator_command(fake_self, "/indicator unicode")

    assert ("display.tui_status_indicator", "unicode") in calls


def test_indicator_handler_rejects_unknown_style(monkeypatch):
    import cli as cli_mod

    calls: list[tuple] = []
    monkeypatch.setattr(
        cli_mod, "save_config_value",
        lambda k, v: (calls.append((k, v)) or True),
    )
    monkeypatch.setattr(cli_mod, "load_cli_config", lambda: {"display": {}})

    fake_self = types.SimpleNamespace()
    cli_mod.HermesCLI._handle_indicator_command(fake_self, "/indicator bogus")
    # Must not have saved anything for an unknown style.
    assert calls == []
