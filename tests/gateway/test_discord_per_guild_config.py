"""Tests for per-guild/per-server Discord configuration overrides.

Guild-scoped config under ``discord.guilds:<guild_id>:`` allows different
mention rules, channel lists, and threading behavior per Discord server.
Resolution priority: per-guild → global config → env var → default.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
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


class FakeGuild:
    def __init__(self, guild_id: int = 100, name: str = "Guild 100"):
        self.id = guild_id
        self.name = name


class FakeTextChannel:
    def __init__(self, channel_id: int = 1, name: str = "general", guild_name: str = "Hermes Server", guild_id: int = 100):
        self.id = channel_id
        self.name = name
        self.guild = FakeGuild(guild_id=guild_id, name=guild_name)
        self.topic = None


class FakeForumChannel:
    def __init__(self, channel_id: int = 1, name: str = "support-forum", guild_name: str = "Hermes Server", guild_id: int = 100):
        self.id = channel_id
        self.name = name
        self.guild = FakeGuild(guild_id=guild_id, name=guild_name)
        self.type = 15
        self.topic = None


class FakeThread:
    def __init__(self, channel_id: int = 1, name: str = "thread", parent=None, guild_name: str = "Hermes Server", guild_id: int = 100):
        self.id = channel_id
        self.name = name
        self.parent = parent
        self.parent_id = getattr(parent, "id", None)
        self.guild = getattr(parent, "guild", None) or FakeGuild(guild_id=guild_id, name=guild_name)
        self.topic = None


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", FakeThread, raising=False)
    monkeypatch.setattr(discord_platform.discord, "ForumChannel", FakeForumChannel, raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    adapter = DiscordAdapter(config)
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=999))
    adapter._text_batch_delay_seconds = 0  # disable batching for tests
    adapter.handle_message = AsyncMock()
    return adapter


def make_message(*, channel, content: str, mentions=None, msg_type=None):
    author = SimpleNamespace(id=42, display_name="Jezza", name="Jezza")
    guild = getattr(channel, "guild", None)
    return SimpleNamespace(
        id=123,
        content=content,
        mentions=list(mentions or []),
        attachments=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        channel=channel,
        author=author,
        guild=guild,
        type=msg_type if msg_type is not None else discord_platform.discord.MessageType.default,
    )


# ---------------------------------------------------------------------------
# _discord_guild_config
# ---------------------------------------------------------------------------

def test_guild_config_returns_entry(adapter):
    adapter.config.extra["guilds"] = {
        "100": {"require_mention": False},
    }
    assert adapter._discord_guild_config("100") == {"require_mention": False}


def test_guild_config_returns_empty_for_unknown(adapter):
    adapter.config.extra["guilds"] = {"100": {"require_mention": False}}
    assert adapter._discord_guild_config("999") == {}


def test_guild_config_returns_empty_for_none(adapter):
    adapter.config.extra["guilds"] = None
    assert adapter._discord_guild_config("100") == {}


def test_guild_config_returns_empty_for_missing_key(adapter):
    assert adapter._discord_guild_config("100") == {}


def test_guild_config_returns_empty_for_dm(adapter):
    adapter.config.extra["guilds"] = {"100": {"require_mention": False}}
    assert adapter._discord_guild_config(None) == {}


# ---------------------------------------------------------------------------
# _resolve_discord_setting – priority chain
# ---------------------------------------------------------------------------

def test_resolve_setting_per_guild_wins(adapter):
    adapter.config.extra["guilds"] = {"100": {"require_mention": False}}
    adapter.config.extra["require_mention"] = True  # global
    assert adapter._resolve_discord_setting("100", "require_mention") is False


def test_resolve_setting_falls_back_to_global(adapter):
    adapter.config.extra["require_mention"] = False
    assert adapter._resolve_discord_setting("100", "require_mention") is False


def test_resolve_setting_falls_back_to_env(adapter, monkeypatch):
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    adapter.config.extra["guilds"] = {}
    adapter.config.extra.pop("free_response_channels", None)
    monkeypatch.setenv("DISCORD_FREE_RESPONSE_CHANNELS", "111,222")
    result = adapter._resolve_discord_setting("100", "free_response_channels")
    assert result == "111,222"


def test_resolve_setting_returns_default(adapter, monkeypatch):
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    adapter.config.extra.pop("auto_thread", None)
    adapter.config.extra["guilds"] = {}
    result = adapter._resolve_discord_setting("100", "auto_thread", default="true")
    assert result == "true"


# ---------------------------------------------------------------------------
# Per-guild require_mention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_requirement_false_allows_unmentioned(adapter, monkeypatch):
    """Guild A has require_mention: false → messages pass without @mention."""
    monkeypatch.delenv("DISCORD_REQUIRE_MENTION", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    adapter.config.extra["require_mention"] = True  # global: require mention
    adapter.config.extra["guilds"] = {
        "100": {"require_mention": False},  # Guild 100: no mention needed
    }

    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=100),
        content="hello without mention",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_per_guild_requirement_true_blocks_unmentioned(adapter, monkeypatch):
    """Guild B has require_mention: true → messages without mention are ignored."""
    monkeypatch.delenv("DISCORD_REQUIRE_MENTION", raising=False)
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    adapter.config.extra.pop("require_mention", None)  # no global
    adapter.config.extra["guilds"] = {
        "200": {"require_mention": True},  # Guild 200: must mention
    }

    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=200),
        content="ignored without mention",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Per-guild free_response_channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_free_response_allows_unmentioned(adapter, monkeypatch):
    """Guild A lists a channel in free_response_channels → mention not required."""
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_REQUIRE_MENTION", raising=False)
    adapter.config.extra["require_mention"] = True  # global
    adapter.config.extra["guilds"] = {
        "100": {"free_response_channels": [42]},  # channel 42 is free in Guild 100
    }

    message = make_message(
        channel=FakeTextChannel(channel_id=42, guild_id=100),
        content="free response without mention",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_per_guild_free_response_wildcard(adapter, monkeypatch):
    """Guild A with free_response_channels: '*' → every channel is free."""
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    adapter.config.extra["require_mention"] = True
    adapter.config.extra["guilds"] = {
        "100": {"free_response_channels": "*"},
    }

    message = make_message(
        channel=FakeTextChannel(channel_id=9999, guild_id=100),
        content="any channel is free",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_awaited_once()


# ---------------------------------------------------------------------------
# Per-guild allowed_channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_allowed_channels_allows(adapter, monkeypatch):
    """Guild A has its own allowed_channels whitelist."""
    monkeypatch.delenv("DISCORD_ALLOWED_CHANNELS", raising=False)
    adapter.config.extra.pop("allowed_channels", None)
    adapter.config.extra["guilds"] = {
        "100": {"allowed_channels": [1]},
    }

    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=100),
        content="in allowed channel",
    )
    # Need to also pass mention check — set require_mention to False
    adapter.config.extra["require_mention"] = False
    await adapter._handle_message(message)
    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_per_guild_allowed_channels_blocks(adapter, monkeypatch):
    """Guild A's allowed_channels blocks a channel not in the list."""
    monkeypatch.delenv("DISCORD_ALLOWED_CHANNELS", raising=False)
    adapter.config.extra.pop("allowed_channels", None)
    adapter.config.extra["guilds"] = {
        "100": {"allowed_channels": [1]},
    }
    adapter.config.extra["require_mention"] = False

    message = make_message(
        channel=FakeTextChannel(channel_id=99, guild_id=100),
        content="in blocked channel",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Per-guild ignored_channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_ignored_channels(adapter, monkeypatch):
    """Guild A has its own ignored_channels list."""
    monkeypatch.delenv("DISCORD_IGNORED_CHANNELS", raising=False)
    adapter.config.extra.pop("ignored_channels", None)
    adapter.config.extra["guilds"] = {
        "100": {"ignored_channels": [666]},
    }
    adapter.config.extra["require_mention"] = False

    message = make_message(
        channel=FakeTextChannel(channel_id=666, guild_id=100),
        content="in ignored channel",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Per-guild auto_thread
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_auto_thread_disabled(adapter, monkeypatch):
    """Guild A has auto_thread: false → no thread creation."""
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    adapter.config.extra.pop("auto_thread", None)
    adapter.config.extra["require_mention"] = False
    adapter.config.extra["guilds"] = {
        "100": {"auto_thread": False},
    }
    adapter._auto_create_thread = AsyncMock()

    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=100),
        content="no auto thread here",
    )
    await adapter._handle_message(message)
    adapter._auto_create_thread.assert_not_awaited()
    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_per_guild_auto_thread_enabled(adapter, monkeypatch):
    """Guild A has auto_thread: true → thread is created."""
    monkeypatch.delenv("DISCORD_AUTO_THREAD", raising=False)
    adapter.config.extra.pop("auto_thread", None)
    adapter.config.extra["require_mention"] = False
    adapter.config.extra["guilds"] = {
        "100": {"auto_thread": True},
    }
    fake_thread = FakeThread(channel_id=777, guild_id=100)
    adapter._auto_create_thread = AsyncMock(return_value=fake_thread)

    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=100),
        content="create thread please",
    )
    await adapter._handle_message(message)
    adapter._auto_create_thread.assert_awaited_once()


# ---------------------------------------------------------------------------
# Per-guild no_thread_channels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_guild_no_thread_channels(adapter, monkeypatch):
    """Guild A has its own no_thread_channels list."""
    monkeypatch.delenv("DISCORD_NO_THREAD_CHANNELS", raising=False)
    adapter.config.extra.pop("no_thread_channels", None)
    adapter.config.extra["require_mention"] = False
    adapter.config.extra["guilds"] = {
        "100": {"no_thread_channels": [42]},
    }
    adapter._auto_create_thread = AsyncMock()

    message = make_message(
        channel=FakeTextChannel(channel_id=42, guild_id=100),
        content="no thread here",
    )
    await adapter._handle_message(message)
    adapter._auto_create_thread.assert_not_awaited()


# ---------------------------------------------------------------------------
# Cross-guild isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_guild_isolation(adapter, monkeypatch):
    """Guild A has free_response, Guild B does not — settings don't leak."""
    monkeypatch.delenv("DISCORD_FREE_RESPONSE_CHANNELS", raising=False)
    monkeypatch.delenv("DISCORD_REQUIRE_MENTION", raising=False)
    adapter.config.extra["require_mention"] = True  # global: require mention
    adapter.config.extra["guilds"] = {
        "100": {"free_response_channels": [1]},  # channel 1 is free in Guild 100
    }

    # Same channel id, but different guild — Guild 200 has no free_response override
    message = make_message(
        channel=FakeTextChannel(channel_id=1, guild_id=200),
        content="not free in guild 200",
    )
    await adapter._handle_message(message)
    adapter.handle_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# _coerce_channel_set helper
# ---------------------------------------------------------------------------

def test_coerce_channel_set_from_list(adapter):
    assert adapter._coerce_channel_set([1, 2, 3]) == {"1", "2", "3"}


def test_coerce_channel_set_from_str(adapter):
    assert adapter._coerce_channel_set("1, 2, 3") == {"1", "2", "3"}


def test_coerce_channel_set_from_set(adapter):
    assert adapter._coerce_channel_set({"a", "b"}) == {"a", "b"}


def test_coerce_channel_set_from_none(adapter):
    assert adapter._coerce_channel_set(None) == set()
