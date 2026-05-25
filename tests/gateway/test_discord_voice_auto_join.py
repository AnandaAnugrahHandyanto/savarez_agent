"""Tests for Discord voice auto-join and listen-only defaults."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, SessionSource
from plugins.platforms.discord.adapter import DiscordAdapter, _apply_yaml_config


class _FakeTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _FakeReceiver:
    def __init__(self, completed):
        self._running = True
        self._completed = list(completed)

    def check_silence(self):
        self._running = False
        completed, self._completed = self._completed, []
        return completed


class _FakeGuild:
    def __init__(self, guild_id=111):
        self.id = guild_id
        self.voice_channels = []

    def get_member(self, user_id):
        return None


class _FakeMember:
    def __init__(self, user_id=333, *, bot=False, guild=None, display_name="Edward"):
        self.id = user_id
        self.bot = bot
        self.guild = guild or _FakeGuild()
        self.display_name = display_name
        self.roles = []


class _FakeVoiceChannel:
    def __init__(self, channel_id=222, name="General", guild=None, members=None):
        self.id = channel_id
        self.name = name
        self.guild = guild or _FakeGuild()
        self.members = list(members or [])


class _FakeVoiceClient:
    def __init__(self, channel):
        self.channel = channel
        self.disconnected = False

    def is_connected(self):
        return not self.disconnected

    async def disconnect(self):
        self.disconnected = True


def _make_adapter(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN", "true")
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_CHANNEL_NAME", "General")
    monkeypatch.setenv("DISCORD_VOICE_TEXT_CHANNEL_ID", "444")
    monkeypatch.delenv("DISCORD_VOICE_AUTO_JOIN_CHANNEL_ID", raising=False)
    monkeypatch.delenv("DISCORD_VOICE_AUTO_JOIN_USER_IDS", raising=False)
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="x"))
    adapter.gateway_runner = SimpleNamespace(_handle_discord_voice_auto_join=AsyncMock())
    return adapter


@pytest.mark.asyncio
async def test_auto_join_invokes_runner_for_configured_channel(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    member = _FakeMember(guild=_FakeGuild(111))
    channel = _FakeVoiceChannel(guild=member.guild)

    await adapter._maybe_auto_join_voice_channel(member, channel)

    adapter.gateway_runner._handle_discord_voice_auto_join.assert_awaited_once_with(
        adapter,
        member,
        channel,
        "444",
    )


@pytest.mark.asyncio
async def test_auto_join_ignores_unconfigured_channel(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_CHANNEL_NAME", "Not General")

    await adapter._maybe_auto_join_voice_channel(_FakeMember(), _FakeVoiceChannel())

    adapter.gateway_runner._handle_discord_voice_auto_join.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_reconciliation_auto_joins_when_user_already_in_target_channel(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_CHANNEL_ID", "222")
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_USER_IDS", "333")
    guild = _FakeGuild(111)
    member = _FakeMember(333, guild=guild)
    channel = _FakeVoiceChannel(222, "General", guild=guild, members=[member])
    guild.voice_channels = [channel]
    adapter._client = SimpleNamespace(guilds=[guild], user=SimpleNamespace(id=999))

    await adapter._reconcile_voice_auto_join()

    adapter.gateway_runner._handle_discord_voice_auto_join.assert_awaited_once_with(
        adapter,
        member,
        channel,
        "444",
    )


@pytest.mark.asyncio
async def test_disconnect_cancels_startup_reconciliation(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    never = asyncio.Event()

    async def wait_forever():
        await never.wait()

    task = asyncio.create_task(wait_forever())
    adapter._voice_auto_join_reconcile_task = task

    await adapter.disconnect()

    assert task.cancelled() is True
    assert adapter._voice_auto_join_reconcile_task is None


@pytest.mark.asyncio
async def test_trigger_user_leave_disconnects_immediately(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_USER_IDS", "333")
    guild = _FakeGuild(111)
    member = _FakeMember(333, guild=guild)
    channel = _FakeVoiceChannel(222, "General", guild=guild)
    vc = _FakeVoiceClient(channel)
    text_channel = SimpleNamespace(send=AsyncMock())
    adapter._client = SimpleNamespace(get_channel=MagicMock(return_value=text_channel), user=SimpleNamespace(id=999))
    adapter._voice_clients[111] = vc
    adapter._voice_text_channels[111] = 444
    adapter._on_voice_disconnect = MagicMock()

    left = await adapter._maybe_auto_leave_voice_channel_for_trigger(member, channel, None)

    assert left is True
    assert vc.disconnected is True
    assert 111 not in adapter._voice_clients
    adapter._on_voice_disconnect.assert_called_once_with("444")
    text_channel.send.assert_awaited_once_with("Left voice channel (trigger user left).")


@pytest.mark.asyncio
async def test_non_trigger_user_leave_keeps_voice_connected(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    monkeypatch.setenv("DISCORD_VOICE_AUTO_JOIN_USER_IDS", "333")
    guild = _FakeGuild(111)
    member = _FakeMember(444, guild=guild)
    channel = _FakeVoiceChannel(222, "General", guild=guild)
    vc = _FakeVoiceClient(channel)
    adapter._voice_clients[111] = vc

    left = await adapter._maybe_auto_leave_voice_channel_for_trigger(member, channel, None)

    assert left is False
    assert vc.disconnected is False
    assert adapter._voice_clients[111] is vc


def test_idle_timeout_zero_disables_timeout_task(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_VOICE_IDLE_TIMEOUT_SECONDS", "0")
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="x"))

    adapter._reset_voice_timeout(111)

    assert adapter._voice_timeout_tasks == {}


def test_empty_channel_timeout_schedules_when_no_humans(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_VOICE_EMPTY_TIMEOUT_SECONDS", "60")
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="x"))
    channel = _FakeVoiceChannel(members=[SimpleNamespace(id=999, bot=True)])
    adapter._voice_clients[111] = _FakeVoiceClient(channel)
    scheduled_task = _FakeTask()

    def fake_ensure_future(coro):
        coro.close()
        return scheduled_task

    monkeypatch.setattr("plugins.platforms.discord.adapter.asyncio.ensure_future", fake_ensure_future)

    adapter._reset_empty_voice_timeout(111)

    assert adapter._voice_empty_timeout_tasks[111] is scheduled_task


def test_empty_channel_timeout_cancelled_when_human_present(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("DISCORD_VOICE_EMPTY_TIMEOUT_SECONDS", "60")
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="x"))
    channel = _FakeVoiceChannel(members=[SimpleNamespace(id=333, bot=False)])
    adapter._voice_clients[111] = _FakeVoiceClient(channel)
    task = _FakeTask()
    adapter._voice_empty_timeout_tasks[111] = task

    adapter._reset_empty_voice_timeout(111)

    assert task.cancelled is True
    assert adapter._voice_empty_timeout_tasks == {}


@pytest.mark.asyncio
async def test_voice_input_resets_idle_timeout(monkeypatch, tmp_path):
    adapter = _make_adapter(monkeypatch, tmp_path)
    adapter._allowed_user_ids = {"333"}
    adapter._voice_receivers[111] = _FakeReceiver([(333, b"pcm")])  # type: ignore[assignment]
    adapter._client = SimpleNamespace(get_guild=MagicMock(return_value=_FakeGuild(111)))
    adapter._reset_voice_timeout = MagicMock()
    adapter._process_voice_input = AsyncMock()

    await adapter._voice_listen_loop(111)

    adapter._reset_voice_timeout.assert_called_once_with(111)
    adapter._process_voice_input.assert_awaited_once_with(111, 333, b"pcm")


def test_yaml_config_bridge_exports_discord_voice_env(monkeypatch):
    for key in (
        "DISCORD_VOICE_AUTO_JOIN",
        "DISCORD_VOICE_AUTO_JOIN_CHANNEL_ID",
        "DISCORD_VOICE_AUTO_JOIN_CHANNEL_NAME",
        "DISCORD_VOICE_TEXT_CHANNEL_ID",
        "DISCORD_VOICE_AUTO_JOIN_USER_IDS",
        "DISCORD_VOICE_IDLE_TIMEOUT_SECONDS",
        "DISCORD_VOICE_EMPTY_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    _apply_yaml_config({}, {
        "voice": {
            "auto_join": {
                "enabled": True,
                "channel_id": "222",
                "channel_name": "General",
                "text_channel_id": "444",
                "user_ids": ["333"],
            },
            "idle_timeout_seconds": 0,
            "empty_timeout_seconds": 120,
        }
    })

    assert os.environ["DISCORD_VOICE_AUTO_JOIN"] == "true"
    assert os.environ["DISCORD_VOICE_AUTO_JOIN_CHANNEL_ID"] == "222"
    assert os.environ["DISCORD_VOICE_AUTO_JOIN_CHANNEL_NAME"] == "General"
    assert os.environ["DISCORD_VOICE_TEXT_CHANNEL_ID"] == "444"
    assert os.environ["DISCORD_VOICE_AUTO_JOIN_USER_IDS"] == "333"
    assert os.environ["DISCORD_VOICE_IDLE_TIMEOUT_SECONDS"] == "0"
    assert os.environ["DISCORD_VOICE_EMPTY_TIMEOUT_SECONDS"] == "120"


def test_gateway_schedules_startup_reconcile_after_voice_auto_tts_sync(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"voice": {"auto_tts": True}},
    )
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._voice_mode = {}
    observed = []
    adapter = SimpleNamespace(
        platform=Platform.DISCORD,
        _auto_tts_default=False,
        _auto_tts_enabled_chats=set(),
        _auto_tts_disabled_chats=set(),
    )

    def schedule_reconcile():
        observed.append(adapter._auto_tts_default)

    adapter.schedule_voice_auto_join_reconcile = schedule_reconcile

    runner._sync_voice_mode_state_to_adapter(adapter)
    runner._run_adapter_post_sync_startup(adapter)

    assert observed == [True]


@pytest.mark.asyncio
async def test_runner_auto_join_wires_text_only_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.join_voice_channel = AsyncMock(return_value=True)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._auto_tts_default = False
    adapter._auto_tts_enabled_chats = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._client = SimpleNamespace(
        get_channel=MagicMock(return_value=SimpleNamespace(name="general", guild=_FakeGuild(111)))
    )
    member = _FakeMember(333, guild=_FakeGuild(111))
    channel = _FakeVoiceChannel(guild=member.guild)

    await runner._handle_discord_voice_auto_join(adapter, member, channel, "444")

    assert adapter._voice_text_channels[111] == 444
    assert runner._voice_mode["discord:444"] == "off"
    assert "444" not in adapter._auto_tts_enabled_chats
    assert "444" in adapter._auto_tts_disabled_chats
    adapter.join_voice_channel.assert_awaited_once_with(channel)


@pytest.mark.asyncio
async def test_runner_auto_join_wires_tts_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.join_voice_channel = AsyncMock(return_value=True)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._auto_tts_default = True
    adapter._auto_tts_enabled_chats = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._client = SimpleNamespace(
        get_channel=MagicMock(return_value=SimpleNamespace(name="general", guild=_FakeGuild(111)))
    )
    member = _FakeMember(333, guild=_FakeGuild(111))
    channel = _FakeVoiceChannel(guild=member.guild)

    await runner._handle_discord_voice_auto_join(adapter, member, channel, "444")

    assert adapter._voice_text_channels[111] == 444
    assert runner._voice_mode["discord:444"] == "all"
    assert "444" in adapter._auto_tts_enabled_chats
    assert "444" not in adapter._auto_tts_disabled_chats
    adapter.join_voice_channel.assert_awaited_once_with(channel)


@pytest.mark.asyncio
async def test_runner_auto_join_failure_clears_callbacks(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.join_voice_channel = AsyncMock(return_value=False)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._voice_input_callback = MagicMock()
    adapter._on_voice_disconnect = MagicMock()
    adapter._client = SimpleNamespace(
        get_channel=MagicMock(return_value=SimpleNamespace(name="general", guild=_FakeGuild(111)))
    )
    member = _FakeMember(333, guild=_FakeGuild(111))
    channel = _FakeVoiceChannel(guild=member.guild)

    await runner._handle_discord_voice_auto_join(adapter, member, channel, "444")

    assert adapter._voice_input_callback is None
    assert adapter._on_voice_disconnect is None
    assert adapter._voice_text_channels == {}


@pytest.mark.asyncio
async def test_runner_auto_join_rejects_bad_text_channel_before_join(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.join_voice_channel = AsyncMock(return_value=True)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._client = SimpleNamespace(get_channel=MagicMock())
    member = _FakeMember(333, guild=_FakeGuild(111))
    channel = _FakeVoiceChannel(guild=member.guild)

    await runner._handle_discord_voice_auto_join(adapter, member, channel, "not-a-number")

    adapter.join_voice_channel.assert_not_awaited()
    assert adapter._voice_text_channels == {}


@pytest.mark.asyncio
async def test_manual_voice_join_honors_voice_auto_tts_false(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.get_user_voice_channel = AsyncMock()
    adapter.join_voice_channel = AsyncMock(return_value=True)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._auto_tts_default = False
    adapter._auto_tts_enabled_chats = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._voice_input_callback = None
    adapter._on_voice_disconnect = None
    guild = _FakeGuild(111)
    channel = _FakeVoiceChannel(guild=guild)
    adapter.get_user_voice_channel.return_value = channel
    runner.adapters = {Platform.DISCORD: adapter}

    source = SessionSource(platform=Platform.DISCORD, chat_id="444", user_id="333")
    event = MessageEvent(text="/voice join", message_type=MessageType.TEXT, source=source)
    event.raw_message = SimpleNamespace(guild_id=111)

    result = await runner._handle_voice_channel_join(event)

    assert adapter._voice_text_channels[111] == 444
    assert runner._voice_mode["discord:444"] == "off"
    assert "444" not in adapter._auto_tts_enabled_chats
    assert "444" in adapter._auto_tts_disabled_chats
    assert "text" in result.lower()


@pytest.mark.asyncio
async def test_manual_voice_join_honors_voice_auto_tts_true(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._voice_mode = {}
    runner._VOICE_MODE_PATH = tmp_path / "gateway_voice_mode.json"
    runner.session_store = MagicMock()
    runner._session_db = None

    adapter = MagicMock()
    adapter.get_user_voice_channel = AsyncMock()
    adapter.join_voice_channel = AsyncMock(return_value=True)
    adapter._voice_text_channels = {}
    adapter._voice_sources = {}
    adapter._auto_tts_default = True
    adapter._auto_tts_enabled_chats = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._voice_input_callback = None
    adapter._on_voice_disconnect = None
    guild = _FakeGuild(111)
    channel = _FakeVoiceChannel(guild=guild)
    adapter.get_user_voice_channel.return_value = channel
    runner.adapters = {Platform.DISCORD: adapter}

    source = SessionSource(platform=Platform.DISCORD, chat_id="444", user_id="333")
    event = MessageEvent(text="/voice join", message_type=MessageType.TEXT, source=source)
    event.raw_message = SimpleNamespace(guild_id=111)

    result = await runner._handle_voice_channel_join(event)

    assert adapter._voice_text_channels[111] == 444
    assert runner._voice_mode["discord:444"] == "all"
    assert "444" in adapter._auto_tts_enabled_chats
    assert "444" not in adapter._auto_tts_disabled_chats
    assert "speak" in result.lower()
