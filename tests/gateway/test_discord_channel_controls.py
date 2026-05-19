"""Tests for Discord ignored_channels and no_thread_channels config."""

from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import sys

import pytest

from gateway.config import PlatformConfig


def _ensure_discord_mock():
    """Install a mock discord module when discord.py isn't available."""
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return

    discord_mod = MagicMock()
    discord_mod.Intents.default.return_value = MagicMock()
    discord_mod.Client = MagicMock
    discord_mod.File = MagicMock
    discord_mod.DMChannel = type("DMChannel", (), {})
    discord_mod.Thread = type("Thread", (), {})
    discord_mod.ForumChannel = type("ForumChannel", (), {})
    discord_mod.ui = SimpleNamespace(View=object, button=lambda *a, **k: (lambda fn: fn), Button=object)
    discord_mod.ButtonStyle = SimpleNamespace(success=1, primary=2, secondary=2, danger=3, green=1, grey=2, blurple=2, red=3)
    discord_mod.Color = SimpleNamespace(orange=lambda: 1, green=lambda: 2, blue=lambda: 3, red=lambda: 4, purple=lambda: 5)
    discord_mod.Interaction = object
    discord_mod.Embed = MagicMock
    discord_mod.app_commands = SimpleNamespace(
        describe=lambda **kwargs: (lambda fn: fn),
        choices=lambda **kwargs: (lambda fn: fn),
        Choice=lambda **kwargs: SimpleNamespace(**kwargs),
    )

    ext_mod = MagicMock()
    commands_mod = MagicMock()
    commands_mod.Bot = MagicMock
    ext_mod.commands = commands_mod

    sys.modules.setdefault("discord", discord_mod)
    sys.modules.setdefault("discord.ext", ext_mod)
    sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()

import gateway.platforms.discord as discord_platform  # noqa: E402
from gateway.platforms.discord import DiscordAdapter  # noqa: E402


class FakeDMChannel:
    def __init__(self, channel_id: int = 1, name: str = "dm"):
        self.id = channel_id
        self.name = name


class FakeTextChannel:
    def __init__(self, channel_id: int = 1, name: str = "general", guild_name: str = "Hermes Server"):
        self.id = channel_id
        self.name = name
        self.guild = SimpleNamespace(name=guild_name)
        self.topic = None


class FakeThread:
    def __init__(self, channel_id: int = 1, name: str = "thread", parent=None, guild_name: str = "Hermes Server"):
        self.id = channel_id
        self.name = name
        self.parent = parent
        self.parent_id = getattr(parent, "id", None)
        self.guild = getattr(parent, "guild", None) or SimpleNamespace(name=guild_name)
        self.topic = None


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", FakeThread, raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    adapter = DiscordAdapter(config)
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=999))
    adapter._text_batch_delay_seconds = 0  # disable batching for tests
    adapter.handle_message = AsyncMock()
    return adapter


def make_message(*, channel, content: str, mentions=None):
    author = SimpleNamespace(id=42, display_name="TestUser", name="TestUser")
    return SimpleNamespace(
        id=123,
        content=content,
        mentions=list(mentions or []),
        attachments=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        channel=channel,
        author=author,
    )


# ── ignored_channels ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ignored_channel_blocks_message(adapter, monkeypatch):
    """Messages in ignored channels are silently dropped."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    message = make_message(channel=FakeTextChannel(channel_id=500), content="hello")
    await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_ignored_channel_blocks_even_with_mention(adapter, monkeypatch):
    """Ignored channels take priority — even @mentions are dropped."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500")

    bot_user = adapter._client.user
    message = make_message(
        channel=FakeTextChannel(channel_id=500),
        content=f"<@{bot_user.id}> hello",
        mentions=[bot_user],
    )
    await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_ignored_channel_processes_normally(adapter, monkeypatch):
    """Channels not in the ignored list process normally."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500,600")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    message = make_message(channel=FakeTextChannel(channel_id=700), content="hello")
    await adapter._handle_message(message)

    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_ignored_channels_csv_parsing(adapter, monkeypatch):
    """Multiple channel IDs are parsed correctly from CSV."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500, 600 , 700")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    for ch_id in (500, 600, 700):
        adapter.handle_message.reset_mock()
        message = make_message(channel=FakeTextChannel(channel_id=ch_id), content="hello")
        await adapter._handle_message(message)
        adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_ignored_channels_empty_string_ignores_nothing(adapter, monkeypatch):
    """Empty DISCORD_IGNORED_CHANNELS means nothing is ignored."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    message = make_message(channel=FakeTextChannel(channel_id=500), content="hello")
    await adapter._handle_message(message)

    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_ignored_channel_thread_parent_match(adapter, monkeypatch):
    """Thread whose parent channel is ignored should also be ignored."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    parent = FakeTextChannel(channel_id=500, name="ignored-channel")
    thread = FakeThread(channel_id=501, name="thread-in-ignored", parent=parent)
    message = make_message(channel=thread, content="hello from thread")
    await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_dms_unaffected_by_ignored_channels(adapter, monkeypatch):
    """DMs should never be affected by ignored_channels."""
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "500")
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    message = make_message(channel=FakeDMChannel(channel_id=500), content="dm hello")
    await adapter._handle_message(message)

    adapter.handle_message.assert_awaited_once()


# ── no_thread_channels ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_thread_channel_skips_auto_thread(adapter, monkeypatch):
    """Channels in no_thread_channels should not auto-create threads."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_NO_THREAD_CHANNELS", "800")
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    monkeypatch.delenv("DISCORD_IGNORED_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    adapter._auto_create_thread = AsyncMock(return_value=FakeThread(channel_id=999))

    message = make_message(channel=FakeTextChannel(channel_id=800), content="hello")
    await adapter._handle_message(message)

    adapter._auto_create_thread.assert_not_awaited()
    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.source.chat_type == "group"


@pytest.mark.asyncio
async def test_normal_channel_still_auto_threads(adapter, monkeypatch):
    """Channels NOT in no_thread_channels still get auto-threading."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_NO_THREAD_CHANNELS", "800")
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    monkeypatch.delenv("DISCORD_IGNORED_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    fake_thread = FakeThread(channel_id=999, name="auto-thread")
    adapter._auto_create_thread = AsyncMock(return_value=fake_thread)

    message = make_message(channel=FakeTextChannel(channel_id=900), content="hello")
    await adapter._handle_message(message)

    adapter._auto_create_thread.assert_awaited_once()
    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.source.chat_type == "thread"


@pytest.mark.asyncio
async def test_no_thread_channels_csv_parsing(adapter, monkeypatch):
    """Multiple no_thread channel IDs parsed from CSV."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_NO_THREAD_CHANNELS", "800, 900")
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    monkeypatch.delenv("DISCORD_IGNORED_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    adapter._auto_create_thread = AsyncMock(return_value=FakeThread(channel_id=999))

    for ch_id in (800, 900):
        adapter._auto_create_thread.reset_mock()
        adapter.handle_message.reset_mock()
        message = make_message(channel=FakeTextChannel(channel_id=ch_id), content="hello")
        await adapter._handle_message(message)
        adapter._auto_create_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_thread_with_auto_thread_disabled_is_noop(adapter, monkeypatch):
    """no_thread_channels is a no-op when auto_thread is globally disabled."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "false")
    monkeypatch.setenv("DISCORD_AUTO_THREAD", "false")
    monkeypatch.setenv("DISCORD_NO_THREAD_CHANNELS", "800")
    monkeypatch.delenv("DISCORD_IGNORED_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)

    adapter._auto_create_thread = AsyncMock()

    message = make_message(channel=FakeTextChannel(channel_id=800), content="hello")
    await adapter._handle_message(message)

    adapter._auto_create_thread.assert_not_awaited()
    adapter.handle_message.assert_awaited_once()


# ── config.py bridging ───────────────────────────────────────────────


def test_config_bridges_ignored_channels(monkeypatch, tmp_path):
    """gateway/config.py bridges discord.ignored_channels to env var."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "ignored_channels": ["111", "222"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Use setenv (not delenv) so monkeypatch registers cleanup even when
    # the var doesn't exist yet — load_gateway_config will overwrite it.
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("DISCORD_IGNORED_CHANNELS") == "111,222"


def test_config_bridges_no_thread_channels(monkeypatch, tmp_path):
    """gateway/config.py bridges discord.no_thread_channels to env var."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "no_thread_channels": ["333"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_NO_THREAD_CHANNELS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("DISCORD_NO_THREAD_CHANNELS") == "333"


def test_config_env_var_takes_precedence(monkeypatch, tmp_path):
    """Env vars should take precedence over config.yaml values."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "ignored_channels": ["111"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "999")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    # Env var should NOT be overwritten
    assert os.getenv("DISCORD_IGNORED_CHANNELS") == "999"


def test_workspace_prompt_map_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    channel = SimpleNamespace(id=321, name="2026-05-13-discord-task", guild=SimpleNamespace(id=999))

    adapter_config = PlatformConfig(enabled=True, token="fake-token")
    workspace_adapter = DiscordAdapter(adapter_config)
    workspace_adapter._register_workspace_channel(channel, prompt="Fix Discord workflow", created_by=42, source_channel_id=7)

    prompt = workspace_adapter._resolve_channel_prompt("321")
    assert prompt is not None
    assert "Fix Discord workflow" in prompt


def test_workspace_channel_name_uses_hermes_local_day(monkeypatch):
    monkeypatch.setattr(
        discord_platform,
        "_hermes_now",
        lambda: datetime(2026, 5, 15, 17, 33, tzinfo=timezone.utc),
    )

    channel_name = discord_platform._derive_workspace_channel_name("Next MixesDB issue")

    assert channel_name.startswith("2026-05-15-")


@pytest.mark.asyncio
async def test_workspace_goal_creates_channel_and_dispatches(adapter, monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_WORKSPACE_HOME_CHANNELS", "jarvis")
    monkeypatch.setenv("DISCORD_WORKSPACE_CATEGORIES", "Hermes Agent,BuyWander")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    created_category = SimpleNamespace(name="Hermes Agent")
    created_channel = SimpleNamespace(
        id=654,
        name="2026-05-13-discord-no-threads-workflow",
        guild=SimpleNamespace(id=777, name="Hermes Server"),
        topic="",
        send=AsyncMock(),
    )
    guild = SimpleNamespace(
        categories=[],
        create_category=AsyncMock(return_value=created_category),
        create_text_channel=AsyncMock(return_value=created_channel),
    )
    interaction = SimpleNamespace(
        channel=SimpleNamespace(name="jarvis", id=111, category=None),
        guild=guild,
        user=SimpleNamespace(id=42, display_name="Matt"),
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    adapter._check_slash_authorization = AsyncMock(return_value=True)
    adapter.handle_message.reset_mock()

    await adapter._handle_workspace_goal_slash(interaction, "Get rid of Discord threads for project work in Hermes Agent")

    guild.create_category.assert_awaited_once_with(
        name="Hermes Agent",
        reason="Jarvis workspace category requested by Matt",
    )
    guild.create_text_channel.assert_awaited_once()
    assert guild.create_text_channel.await_args.kwargs["category"] is created_category
    interaction.followup.send.assert_awaited_once()
    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.text == "Get rid of Discord threads for project work in Hermes Agent"
    assert event.source.chat_id == "654"
    assert event.channel_prompt and "Get rid of Discord threads" in event.channel_prompt


@pytest.mark.asyncio
async def test_workspace_complete_rejects_non_workspace_channel(adapter):
    interaction = SimpleNamespace(
        channel=SimpleNamespace(id=999, name="general"),
        response=SimpleNamespace(send_message=AsyncMock()),
    )
    adapter._check_slash_authorization = AsyncMock(return_value=True)

    await adapter._handle_workspace_complete_slash(interaction)

    interaction.response.send_message.assert_awaited_once()
    assert "not registered" in interaction.response.send_message.await_args.args[0]
