"""Discord approval prompts ping configured approvers."""

from types import SimpleNamespace

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.discord import (
    DISCORD_AVAILABLE,
    DiscordAdapter,
    _format_discord_user_mentions,
)


class _FakeChannel:
    def __init__(self):
        self.sent = None

    async def send(self, **kwargs):
        self.sent = kwargs
        return SimpleNamespace(id=12345)


class _FakeClient:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, channel_id):
        return self.channel


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("540316979035242547", "<@540316979035242547>"),
        ("<@540316979035242547>, user:123", "<@540316979035242547> <@123>"),
        (["540316979035242547", "not-a-user", "540316979035242547"], "<@540316979035242547>"),
    ],
)
def test_format_discord_user_mentions_accepts_only_numeric_user_ids(raw, expected):
    assert _format_discord_user_mentions(raw) == expected


@pytest.mark.skipif(not DISCORD_AVAILABLE, reason="discord.py unavailable")
@pytest.mark.asyncio
async def test_send_exec_approval_mentions_configured_approver():
    channel = _FakeChannel()
    adapter = DiscordAdapter(
        PlatformConfig(
            enabled=True,
            token="test-token",
            extra={"approval_mentions": "540316979035242547"},
        )
    )
    adapter._client = _FakeClient(channel)

    result = await adapter.send_exec_approval(
        chat_id="1503609107482148995",
        command="rm -rf /tmp/example",
        session_key="session-1",
        description="destructive command",
    )

    assert result.success is True
    assert channel.sent["content"] == "<@540316979035242547>"
    assert channel.sent["embed"].title == "⚠️ Command Approval Required"
    assert channel.sent["view"] is not None


@pytest.mark.skipif(not DISCORD_AVAILABLE, reason="discord.py unavailable")
@pytest.mark.asyncio
async def test_send_exec_approval_falls_back_to_allowed_users_for_mentions():
    channel = _FakeChannel()
    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._client = _FakeClient(channel)
    adapter._allowed_user_ids = {"540316979035242547"}

    result = await adapter.send_exec_approval(
        chat_id="1503609107482148995",
        command="rm -rf /tmp/example",
        session_key="session-1",
        description="destructive command",
    )

    assert result.success is True
    assert channel.sent["content"] == "<@540316979035242547>"
