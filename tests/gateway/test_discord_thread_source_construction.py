"""Fake-object Discord source construction tests for thread memory scope.

These tests avoid Discord clients, network calls, gateway sessions, and live
state. They only exercise adapter source construction with lightweight fakes.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.session import build_session_key


def _ensure_discord_mock() -> None:
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return

    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.Forbidden = type("Forbidden", (Exception,), {})
    discord_mod.MessageType = SimpleNamespace(default=object(), reply=object())
    discord_mod.ui = SimpleNamespace(
        View=object,
        button=lambda *a, **k: (lambda fn: fn),
        Button=object,
    )
    discord_mod.ButtonStyle = SimpleNamespace(
        success=1,
        primary=2,
        secondary=2,
        danger=3,
        green=1,
        grey=2,
        blurple=2,
        red=3,
    )
    discord_mod.Color = SimpleNamespace(
        orange=lambda: 1,
        green=lambda: 2,
        blue=lambda: 3,
        red=lambda: 4,
        purple=lambda: 5,
    )
    discord_mod.Interaction = object
    discord_mod.Embed = MagicMock
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        autocomplete=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
        Command=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()

import plugins.platforms.discord.adapter as discord_adapter_module  # noqa: E402
from plugins.platforms.discord.adapter import DiscordAdapter  # noqa: E402


EXPECTED_THREAD_KEY = (
    "agent:main:discord:thread:222222222222222222:222222222222222222"
)


class FakeDMChannel:
    pass


class FakeThread:
    def __init__(self, *, channel_id: str, name: str, parent=None, guild=None):
        self.id = int(channel_id)
        self.name = name
        self.parent = parent
        self.parent_id = getattr(parent, "id", None)
        self.guild = guild
        self.topic = None


class FakeTextChannel:
    def __init__(self, *, channel_id: str, name: str, guild=None, topic=None):
        self.id = int(channel_id)
        self.name = name
        self.guild = guild
        self.topic = topic


@pytest.fixture(autouse=True)
def isolated_discord_environment(monkeypatch, tmp_path):
    """Keep adapter tests away from production Hermes state and env config."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    for name in (
        "DISCORD_ALLOWED_CHANNELS",
        "DISCORD_IGNORED_CHANNELS",
        "DISCORD_FREE_RESPONSE_CHANNELS",
        "DISCORD_NO_THREAD_CHANNELS",
        "DISCORD_HISTORY_BACKFILL",
        "DISCORD_THREAD_REQUIRE_MENTION",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(discord_adapter_module.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_adapter_module.discord, "Thread", FakeThread, raising=False)
    monkeypatch.setattr(
        discord_adapter_module.discord,
        "MessageType",
        SimpleNamespace(default=object(), reply=object()),
        raising=False,
    )


@pytest.fixture
def adapter():
    config = PlatformConfig(
        enabled=True,
        token="fake-token",
        extra={
            "require_mention": False,
            "history_backfill": False,
            "slash_commands": False,
        },
    )
    instance = DiscordAdapter(config)
    instance._client = SimpleNamespace(user=SimpleNamespace(id=999999999999999999))
    instance._text_batch_delay_seconds = 0
    instance.handle_message = AsyncMock()
    return instance


def _assert_stable_thread_source(source):
    assert source.platform == Platform.DISCORD
    assert source.chat_type == "thread"
    assert source.chat_id == "222222222222222222"
    assert source.thread_id == "222222222222222222"
    assert build_session_key(source) == EXPECTED_THREAD_KEY


@pytest.mark.asyncio
async def test_message_inside_existing_discord_thread_builds_full_thread_source(adapter):
    guild = SimpleNamespace(id=999999999999999999, name="Jenny Guild")
    parent = FakeTextChannel(
        channel_id="111111111111111111",
        name="project-parent",
        guild=guild,
    )
    thread = FakeThread(
        channel_id="222222222222222222",
        name="project-thread",
        parent=parent,
        guild=guild,
    )
    author = SimpleNamespace(
        id=333333333333333333,
        name="Jenny",
        display_name="Jenny",
        bot=False,
    )
    message = SimpleNamespace(
        id=444444444444444444,
        content="thread update",
        mentions=[],
        attachments=[],
        message_snapshots=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        channel=thread,
        author=author,
        guild=guild,
        type=discord_adapter_module.discord.MessageType.default,
    )

    await adapter._handle_message(message)

    event = adapter.handle_message.await_args.args[0]
    source = event.source
    _assert_stable_thread_source(source)
    assert source.parent_chat_id == "111111111111111111"
    assert source.guild_id == "999999999999999999"
    assert source.message_id == "444444444444444444"


def test_slash_command_inside_discord_thread_builds_full_thread_source(adapter):
    guild = SimpleNamespace(id=999999999999999999, name="Jenny Guild")
    parent = FakeTextChannel(
        channel_id="111111111111111111",
        name="project-parent",
        guild=guild,
    )
    thread = FakeThread(
        channel_id="222222222222222222",
        name="project-thread",
        parent=parent,
        guild=guild,
    )
    interaction = SimpleNamespace(
        id=444444444444444444,
        channel_id=222222222222222222,
        channel=thread,
        guild=guild,
        guild_id=999999999999999999,
        user=SimpleNamespace(id=333333333333333333, display_name="Jenny"),
    )

    event = adapter._build_slash_event(interaction, "/status")

    source = event.source
    _assert_stable_thread_source(source)
    assert source.parent_chat_id == "111111111111111111"
    assert source.guild_id == "999999999999999999"
    assert source.message_id == "444444444444444444"


@pytest.mark.asyncio
async def test_thread_starter_dispatch_builds_full_thread_source(adapter):
    guild = SimpleNamespace(id=999999999999999999, name="Jenny Guild")
    parent = FakeTextChannel(
        channel_id="111111111111111111",
        name="project-parent",
        guild=guild,
    )
    interaction = SimpleNamespace(
        id=444444444444444444,
        channel_id=111111111111111111,
        channel=parent,
        guild=guild,
        guild_id=999999999999999999,
        user=SimpleNamespace(id=333333333333333333, display_name="Jenny"),
    )

    await adapter._dispatch_thread_session(
        interaction,
        "222222222222222222",
        "project-thread",
        "start this thread",
    )

    event = adapter.handle_message.await_args.args[0]
    source = event.source
    _assert_stable_thread_source(source)
    assert source.parent_chat_id == "111111111111111111"
    assert source.guild_id == "999999999999999999"
    assert source.message_id == "444444444444444444"


@pytest.mark.asyncio
async def test_auto_thread_flow_builds_full_thread_source_without_live_discord(adapter):
    guild = SimpleNamespace(id=999999999999999999, name="Jenny Guild")
    parent = FakeTextChannel(
        channel_id="111111111111111111",
        name="project-parent",
        guild=guild,
    )
    thread = FakeThread(
        channel_id="222222222222222222",
        name="project-thread",
        parent=parent,
        guild=guild,
    )
    bot_user = adapter._client.user
    author = SimpleNamespace(
        id=333333333333333333,
        name="Jenny",
        display_name="Jenny",
        bot=False,
    )
    message = SimpleNamespace(
        id=444444444444444444,
        content=f"<@{bot_user.id}> start a thread",
        mentions=[bot_user],
        attachments=[],
        message_snapshots=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        channel=parent,
        author=author,
        guild=guild,
        type=discord_adapter_module.discord.MessageType.default,
    )
    adapter._auto_create_thread = AsyncMock(return_value=thread)

    await adapter._handle_message(message)

    event = adapter.handle_message.await_args.args[0]
    source = event.source
    _assert_stable_thread_source(source)
    assert source.parent_chat_id == "111111111111111111"
    assert source.guild_id == "999999999999999999"
    assert source.message_id == "444444444444444444"


def test_discord_batch_key_matches_session_key_only_when_thread_setting_matches(adapter):
    source = adapter.build_source(
        chat_id="222222222222222222",
        chat_type="thread",
        user_id="333333333333333333",
        thread_id="222222222222222222",
    )
    event = SimpleNamespace(source=source)
    gateway_config = GatewayConfig(thread_sessions_per_user=True)
    store_key = build_session_key(
        source,
        thread_sessions_per_user=gateway_config.thread_sessions_per_user,
    )

    assert adapter._text_batch_key(event) != store_key

    adapter.config.extra["thread_sessions_per_user"] = gateway_config.thread_sessions_per_user
    assert adapter._text_batch_key(event) == store_key


def test_discord_batch_key_matches_session_key_only_when_group_setting_matches(adapter):
    source = adapter.build_source(
        chat_id="111111111111111111",
        chat_type="group",
        user_id="333333333333333333",
    )
    event = SimpleNamespace(source=source)
    gateway_config = GatewayConfig(group_sessions_per_user=False)
    store_key = build_session_key(
        source,
        group_sessions_per_user=gateway_config.group_sessions_per_user,
    )

    assert adapter._text_batch_key(event) != store_key

    adapter.config.extra["group_sessions_per_user"] = gateway_config.group_sessions_per_user
    assert adapter._text_batch_key(event) == store_key
