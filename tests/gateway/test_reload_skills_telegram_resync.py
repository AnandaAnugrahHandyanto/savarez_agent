"""Tests for `/reload-skills` resyncing Telegram BotCommand menus.

Skill slash commands are resolved dynamically by the gateway, so a newly
created skill can work when typed manually. Telegram's client-side `/` menu,
however, is stored by Telegram through ``set_my_commands``. Without an adapter
refresh hook, `/reload-skills` refreshed Hermes' in-process skill registry but
left Telegram's visible command picker stale until a gateway restart.
"""
from __future__ import annotations

import asyncio

import pytest


def _make_adapter(bot):
    """Construct a TelegramAdapter without going through __init__ / token checks."""
    pytest.importorskip("telegram")
    from gateway.platforms.base import Platform
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter._bot = bot
    adapter.platform = Platform.TELEGRAM
    return adapter


class RecordingBot:
    def __init__(self):
        self.calls = []

    async def set_my_commands(self, commands, scope=None):
        self.calls.append(
            {
                "commands": [(cmd.command, cmd.description) for cmd in commands],
                "scope": type(scope).__name__ if scope is not None else None,
            }
        )


class TestTelegramRefreshSkillGroup:
    def test_refresh_re_registers_bot_commands_for_default_and_private_scopes(
        self, monkeypatch
    ) -> None:
        bot = RecordingBot()
        adapter = _make_adapter(bot)

        def fake_menu(max_commands=100):
            assert max_commands == 100
            return (
                [
                    ("example_skill", "Run example skill"),
                    ("sample_report", "Create sample report"),
                    ("demo_lookup", "Look up demo data"),
                    ("test_helper", "Run test helper"),
                ],
                0,
            )

        monkeypatch.setattr("hermes_cli.commands.telegram_menu_commands", fake_menu)

        import telegram

        class BotCommand:
            def __init__(self, command, description):
                self.command = command
                self.description = description

        class BotCommandScopeDefault:
            pass

        class BotCommandScopeAllPrivateChats:
            pass

        monkeypatch.setattr(telegram, "BotCommand", BotCommand)
        monkeypatch.setattr(telegram, "BotCommandScopeDefault", BotCommandScopeDefault)
        monkeypatch.setattr(
            telegram,
            "BotCommandScopeAllPrivateChats",
            BotCommandScopeAllPrivateChats,
        )

        count, hidden = asyncio.run(adapter.refresh_skill_group())

        assert (count, hidden) == (4, 0)
        assert len(bot.calls) == 2
        assert {call["scope"] for call in bot.calls} == {
            "BotCommandScopeDefault",
            "BotCommandScopeAllPrivateChats",
        }
        for call in bot.calls:
            assert [name for name, _desc in call["commands"]] == [
                "example_skill",
                "sample_report",
                "demo_lookup",
                "test_helper",
            ]

    def test_refresh_without_connected_bot_is_safe(self) -> None:
        adapter = _make_adapter(None)

        result = asyncio.run(adapter.refresh_skill_group())

        assert result == (0, 0)
