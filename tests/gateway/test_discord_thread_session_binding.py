from types import SimpleNamespace

from gateway.config import PlatformConfig
from gateway.session import build_session_key
from plugins.platforms.discord.adapter import DiscordAdapter


class _FakeParent:
    id = 111
    name = "github-dev"


class _FakeThread:
    id = 222
    parent_id = 111
    parent = _FakeParent()
    name = "workstream"
    guild = SimpleNamespace(id=333, name="Hermes and Jonas")


class _FakeUser:
    id = 444
    display_name = "Jonas"


class _FakeInteraction:
    channel_id = 222
    channel = _FakeThread()
    user = _FakeUser()
    guild = _FakeThread.guild


def _patch_discord_classes(monkeypatch):
    import plugins.platforms.discord.adapter as adapter_mod

    monkeypatch.setattr(adapter_mod.discord, "Thread", _FakeThread)
    monkeypatch.setattr(adapter_mod.discord, "DMChannel", type("DMChannel", (), {}))


def test_discord_slash_events_bind_thread_sessions_to_parent_channel(monkeypatch):
    _patch_discord_classes(monkeypatch)

    adapter = DiscordAdapter(config=PlatformConfig(enabled=True, token="test-token"))
    event = adapter._build_slash_event(_FakeInteraction(), "/status")

    assert event.source.chat_type == "thread"
    assert event.source.chat_id == "111"
    assert event.source.parent_chat_id == "111"
    assert event.source.thread_id == "222"
    assert event.source.guild_id == "333"
    assert build_session_key(event.source) == "agent:main:discord:thread:111:222"


def test_discord_thread_starter_events_use_same_parent_thread_session(monkeypatch):
    _patch_discord_classes(monkeypatch)

    adapter = DiscordAdapter(config=PlatformConfig(enabled=True, token="test-token"))
    captured = {}

    async def fake_handle_message(event):
        captured["event"] = event

    adapter.handle_message = fake_handle_message

    import asyncio

    asyncio.run(
        adapter._dispatch_thread_session(
            _FakeInteraction(),
            thread_id="222",
            thread_name="workstream",
            text="starter",
        )
    )

    source = captured["event"].source
    assert source.chat_type == "thread"
    assert source.chat_id == "111"
    assert source.parent_chat_id == "111"
    assert source.thread_id == "222"
    assert source.guild_id == "333"
    assert build_session_key(source) == "agent:main:discord:thread:111:222"
