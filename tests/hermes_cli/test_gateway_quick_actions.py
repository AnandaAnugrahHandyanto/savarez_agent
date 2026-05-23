"""Tests for shared gateway command-palette quick actions."""

from __future__ import annotations

import pytest

from hermes_cli.commands import (
    GATEWAY_QUICK_ACTION_COMMANDS,
    GATEWAY_QUICK_ACTION_CONFIRM_COMMANDS,
    gateway_quick_action_label,
    resolve_command,
)


EXPECTED_GATEWAY_QUICK_ACTIONS = (
    "status",
    "usage",
    "help",
    "model",
    "agents",
    "profile",
    "whoami",
    "insights",
    "new",
    "retry",
    "undo",
    "stop",
    "compress",
    "fast",
    "yolo",
)


def test_gateway_quick_actions_include_common_session_controls():
    assert GATEWAY_QUICK_ACTION_COMMANDS == EXPECTED_GATEWAY_QUICK_ACTIONS
    assert {"stop", "undo", "fast", "compress"}.issubset(GATEWAY_QUICK_ACTION_COMMANDS)


@pytest.mark.parametrize("command", GATEWAY_QUICK_ACTION_COMMANDS)
def test_gateway_quick_actions_are_registered_slash_commands(command: str):
    command_def = resolve_command(command)
    assert command_def is not None
    assert command_def.name == command


@pytest.mark.parametrize("command", GATEWAY_QUICK_ACTION_COMMANDS)
def test_gateway_quick_actions_have_short_labels(command: str):
    label = gateway_quick_action_label(command)
    assert label
    assert len(label) <= 80


def test_gateway_quick_actions_confirm_destructive_commands():
    assert GATEWAY_QUICK_ACTION_CONFIRM_COMMANDS == frozenset({"new", "undo", "stop", "yolo"})


def test_gateway_quick_action_confirm_commands_are_visible_actions():
    assert GATEWAY_QUICK_ACTION_CONFIRM_COMMANDS.issubset(set(GATEWAY_QUICK_ACTION_COMMANDS))
