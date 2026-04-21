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
def adapter(monkeypatch, tmp_path):
    monkeypatch.setattr(discord_platform.discord, "DMChannel", FakeDMChannel, raising=False)
    monkeypatch.setattr(discord_platform.discord, "Thread", FakeThread, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("DISCORD_ALLOWED_CHANNELS", raising=False)

    config = PlatformConfig(enabled=True, token="fake-token")
    adapter = DiscordAdapter(config)
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=999))
    adapter._text_batch_delay_seconds = 0  # disable batching for tests
    adapter.handle_message = AsyncMock()
    return adapter


def make_message(*, channel, content: str, mentions=None, author_bot: bool = False, reference=None, webhook_id=None):
    author = SimpleNamespace(id=42, display_name="TestUser", name="TestUser", bot=author_bot)
    return SimpleNamespace(
        id=123,
        content=content,
        mentions=list(mentions or []),
        attachments=[],
        reference=reference,
        created_at=datetime.now(timezone.utc),
        channel=channel,
        author=author,
        webhook_id=webhook_id,
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


@pytest.mark.asyncio
async def test_bot_ack_only_message_is_suppressed(adapter, monkeypatch, caplog):
    """Short bot/app acknowledgements should be dropped to prevent ping-pong loops."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_ALLOW_BOTS", "mentions")
    bot_user = adapter._client.user
    message = make_message(
        channel=FakeTextChannel(channel_id=500),
        content=f"<@{bot_user.id}> 확인했습니다.",
        mentions=[bot_user],
        author_bot=True,
    )

    with caplog.at_level("INFO"):
        await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()
    assert "suppressed_bot_ack_loop reason=ack_only" in caplog.text


@pytest.mark.asyncio
async def test_bot_thread_followup_requires_explicit_target(adapter, monkeypatch, caplog):
    """Bot authors no longer get free unmentioned follow-ups just because the bot joined the thread."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_ALLOW_BOTS", "all")
    parent = FakeTextChannel(channel_id=500, name="briefing")
    thread = FakeThread(channel_id=501, name="thread", parent=parent)
    adapter._threads.mark(str(thread.id))
    message = make_message(
        channel=thread,
        content="구현 초안 올렸습니다. 검토 부탁드립니다.",
        author_bot=True,
    )

    with caplog.at_level("INFO"):
        await adapter._handle_message(message)

    adapter.handle_message.assert_not_awaited()
    assert "suppressed_bot_ack_loop reason=thread_followup_requires_explicit_target" in caplog.text


@pytest.mark.asyncio
async def test_human_thread_followup_still_allowed(adapter, monkeypatch):
    """Human follow-ups in an active thread should still work without repeated mentions."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    parent = FakeTextChannel(channel_id=500, name="briefing")
    thread = FakeThread(channel_id=501, name="thread", parent=parent)
    adapter._threads.mark(str(thread.id))
    message = make_message(
        channel=thread,
        content="추가 로그 붙였습니다.",
        author_bot=False,
    )

    await adapter._handle_message(message)

    adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_bot_reply_to_self_still_allowed(adapter, monkeypatch):
    """Explicit replies to this bot remain valid even inside active threads."""
    monkeypatch.setenv("DISCORD_REQUIRE_MENTION", "true")
    monkeypatch.setenv("DISCORD_ALLOW_BOTS", "all")
    parent = FakeTextChannel(channel_id=500, name="briefing")
    thread = FakeThread(channel_id=501, name="thread", parent=parent)
    adapter._threads.mark(str(thread.id))
    resolved = SimpleNamespace(author=adapter._client.user, content="이 경로로 답장해 주세요")
    reference = SimpleNamespace(message_id=321, resolved=resolved)
    message = make_message(
        channel=thread,
        content="구체 패치 순서 정리했습니다.",
        author_bot=True,
        reference=reference,
    )

    await adapter._handle_message(message)

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


def test_config_bridges_allowed_users(monkeypatch, tmp_path):
    """gateway/config.py bridges discord.allowed_users to DISCORD_ALLOWED_USERS."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "allowed_users": ["111", "222"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_ALLOWED_USERS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("DISCORD_ALLOWED_USERS") == "111,222"



def test_config_bridges_allow_from_to_allowed_users(monkeypatch, tmp_path):
    """gateway/config.py also accepts discord.allow_from for Discord allowlists."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "allow_from": ["333"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_ALLOWED_USERS", "")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    assert os.getenv("DISCORD_ALLOWED_USERS") == "333"



def test_config_env_var_takes_precedence(monkeypatch, tmp_path):
    """Env vars should take precedence over config.yaml values."""
    import yaml
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "discord": {
            "ignored_channels": ["111"],
            "allowed_users": ["222"],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_IGNORED_CHANNELS", "999")
    monkeypatch.setenv("DISCORD_ALLOWED_USERS", "888")

    from gateway.config import load_gateway_config
    load_gateway_config()

    import os
    # Env vars should NOT be overwritten
    assert os.getenv("DISCORD_IGNORED_CHANNELS") == "999"
    assert os.getenv("DISCORD_ALLOWED_USERS") == "888"
