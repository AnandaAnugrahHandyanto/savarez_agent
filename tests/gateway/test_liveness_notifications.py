from unittest.mock import AsyncMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import SendResult
from gateway.run import GatewayRunner


def _runner_with_discord_adapter():
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="***")}
    )
    adapter = AsyncMock()
    adapter.send = AsyncMock(return_value=SendResult(success=True, message_id="msg-1"))
    runner.adapters = {Platform.DISCORD: adapter}
    return runner, adapter


@pytest.mark.asyncio
async def test_liveness_notification_sends_to_configured_thread(monkeypatch):
    import gateway.run as gateway_run

    runner, adapter = _runner_with_discord_adapter()
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_config",
        lambda: {
            "gateway": {
                "liveness_notifications": {
                    "enabled": True,
                    "target": "discord:12345:67890",
                    "send_timeout_seconds": 1,
                }
            }
        },
    )

    await runner._send_liveness_notification("start")

    adapter.send.assert_awaited_once()
    chat_id, message = adapter.send.await_args.args[:2]
    assert chat_id == "12345"
    assert "Hermes gateway started" in message
    assert adapter.send.await_args.kwargs["metadata"] == {"thread_id": "67890"}


@pytest.mark.asyncio
async def test_liveness_notification_is_silent_when_disabled(monkeypatch):
    import gateway.run as gateway_run

    runner, adapter = _runner_with_discord_adapter()
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_config",
        lambda: {"gateway": {"liveness_notifications": {"enabled": False}}},
    )

    await runner._send_liveness_notification("start")

    adapter.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_liveness_notification_respects_per_event_toggle(monkeypatch):
    import gateway.run as gateway_run

    runner, adapter = _runner_with_discord_adapter()
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_config",
        lambda: {
            "gateway": {
                "liveness_notifications": {
                    "enabled": True,
                    "notify_on_start": False,
                    "target": "discord:12345",
                }
            }
        },
    )

    await runner._send_liveness_notification("start")

    adapter.send.assert_not_awaited()
