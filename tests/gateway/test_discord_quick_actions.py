"""Tests for Discord quick-action command palette V1."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from gateway.config import PlatformConfig
import gateway.platforms.discord as discord_platform
from gateway.platforms.discord import (
    DISCORD_QUICK_ACTION_COMMANDS,
    DISCORD_QUICK_ACTION_CONFIRM_COMMANDS,
    _quick_action_label,
    _quick_action_row,
)
from hermes_cli.commands import GATEWAY_QUICK_ACTION_COMMANDS


EXPECTED_V1_COMMANDS = {
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
}


def test_discord_quick_actions_use_shared_gateway_command_set():
    assert DISCORD_QUICK_ACTION_COMMANDS == GATEWAY_QUICK_ACTION_COMMANDS
    assert set(DISCORD_QUICK_ACTION_COMMANDS) == EXPECTED_V1_COMMANDS


def test_discord_quick_actions_order_is_stable_for_v1_layout():
    assert DISCORD_QUICK_ACTION_COMMANDS == (
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


def test_discord_quick_actions_excludes_arg_and_risky_commands_not_in_palette():
    excluded = {
        "commands",
        "reset",
        "queue",
        "background",
        "steer",
        "goal",
        "rollback",
        "restart",
        "update",
        "approve",
        "deny",
    }
    assert excluded.isdisjoint(DISCORD_QUICK_ACTION_COMMANDS)


def test_discord_quick_actions_confirm_destructive_actions():
    assert DISCORD_QUICK_ACTION_CONFIRM_COMMANDS == frozenset({"new", "undo", "stop", "yolo"})


@pytest.mark.parametrize(
    ("command", "label"),
    [
        ("status", "Status"),
        ("usage", "Usage"),
        ("help", "Help"),
        ("model", "Model"),
        ("agents", "Agents"),
        ("profile", "Profile"),
        ("whoami", "Who Am I"),
        ("insights", "Insights"),
        ("new", "New"),
        ("retry", "Retry"),
        ("undo", "Undo"),
        ("stop", "Stop"),
        ("compress", "Compress"),
        ("fast", "Fast"),
        ("yolo", "YOLO"),
    ],
)
def test_discord_quick_action_labels(command, label):
    assert _quick_action_label(command) == label
    assert len(label) <= 80


def test_discord_quick_action_rows_match_v1_layout():
    rows = {command: _quick_action_row(command) for command in DISCORD_QUICK_ACTION_COMMANDS}
    assert [cmd for cmd, row in rows.items() if row == 0] == ["status", "usage", "help"]
    assert [cmd for cmd, row in rows.items() if row == 1] == ["model", "agents", "profile"]
    assert [cmd for cmd, row in rows.items() if row == 2] == ["whoami", "insights", "new"]
    assert [cmd for cmd, row in rows.items() if row == 3] == ["retry", "undo", "stop"]
    assert [cmd for cmd, row in rows.items() if row == 4] == ["compress", "fast", "yolo"]


def test_discord_quick_action_rows_stay_within_discord_v1_limit():
    assert max(_quick_action_row(command) for command in DISCORD_QUICK_ACTION_COMMANDS) <= 4


@pytest.mark.asyncio
async def test_quick_action_button_dispatches_direct_commands_without_deleting_palette():
    if not hasattr(discord_platform, "CommandQuickActionsView"):
        pytest.skip("discord.py UI classes are not available")

    adapter = discord_platform.DiscordAdapter(PlatformConfig(enabled=True, token="***"))
    adapter._run_simple_slash = AsyncMock()
    view = discord_platform.CommandQuickActionsView(adapter)
    status_button = next(child for child in view.children if child.label == "Status")
    if not callable(getattr(status_button, "callback", None)):
        pytest.skip("discord.py Button callback binding is not available")
    interaction = object()

    await status_button.callback(interaction)

    adapter._run_simple_slash.assert_awaited_once_with(
        interaction,
        "/status",
        cleanup_response=False,
    )


@pytest.mark.asyncio
async def test_quick_action_button_uses_confirmation_for_yolo():
    if not hasattr(discord_platform, "CommandQuickActionsView"):
        pytest.skip("discord.py UI classes are not available")

    adapter = discord_platform.DiscordAdapter(PlatformConfig(enabled=True, token="***"))
    adapter._run_simple_slash = AsyncMock()
    view = discord_platform.CommandQuickActionsView(adapter)
    yolo_button = next(child for child in view.children if child.label == "YOLO")
    if not callable(getattr(yolo_button, "callback", None)):
        pytest.skip("discord.py Button callback binding is not available")
    interaction = type(
        "InteractionStub",
        (),
        {"response": type("ResponseStub", (), {"send_message": AsyncMock()})()},
    )()

    await yolo_button.callback(interaction)

    adapter._run_simple_slash.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()
    _args, kwargs = interaction.response.send_message.await_args
    assert kwargs["ephemeral"] is True
    assert isinstance(kwargs["view"], discord_platform.QuickActionConfirmView)
