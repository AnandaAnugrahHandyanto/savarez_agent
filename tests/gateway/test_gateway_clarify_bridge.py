"""Tests for the GatewayRunner clarify callback bridge."""

import asyncio
import concurrent.futures
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner
from gateway.session import SessionSource


class _FakeAdapter:
    async def send_clarify_prompt(self, **kwargs):
        fut = kwargs["response_future"]
        fut.set_result("按钮选择")
        return MagicMock(success=True)


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.adapters = {Platform.TELEGRAM: _FakeAdapter()}
    return runner


@pytest.mark.asyncio
async def test_build_clarify_callback_sends_prompt_and_waits_for_result():
    runner = _make_runner()
    adapter = runner.adapters[Platform.TELEGRAM]
    adapter.send_clarify_prompt = AsyncMock(side_effect=adapter.send_clarify_prompt)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="group",
        user_id="u1",
        thread_id="159975",
    )

    callback = runner._build_clarify_callback(
        adapter=adapter,
        source=source,
        session_key="agent:main:telegram:group:12345:159975",
        loop=asyncio.get_running_loop(),
        metadata={"thread_id": "159975"},
    )

    result = await asyncio.to_thread(callback, "下一步？", ["修复", "跳过"])

    assert result == "按钮选择"
    adapter.send_clarify_prompt.assert_awaited_once()
    kwargs = adapter.send_clarify_prompt.call_args.kwargs
    assert kwargs["question"] == "下一步？"
    assert kwargs["choices"] == ["修复", "跳过"]
    assert isinstance(kwargs["response_future"], concurrent.futures.Future)
