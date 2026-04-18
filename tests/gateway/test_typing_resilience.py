"""Tests for gateway/platforms/base.py — _keep_typing resilience."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_adapter():
    """Create a minimal mock adapter with _keep_typing and send_typing."""
    adapter = MagicMock()
    adapter.name = "test"
    adapter._typing_paused = set()
    adapter.stop_typing = AsyncMock()
    return adapter


class TestKeepTypingResilience:
    @pytest.mark.asyncio
    async def test_survives_transient_error(self, mock_adapter):
        """Typing loop continues after a transient send_typing failure."""
        from gateway.platforms.base import BasePlatformAdapter

        call_count = 0

        async def flaky_send_typing(chat_id, metadata=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("simulated network blip")

        mock_adapter.send_typing = flaky_send_typing
        loop_task = asyncio.create_task(
            BasePlatformAdapter._keep_typing(mock_adapter, "123", interval=0.01)
        )
        await asyncio.sleep(0.05)
        loop_task.cancel()
        try:
            await asyncio.wait_for(loop_task, timeout=1.0)
        except asyncio.CancelledError:
            pass

        # Should have called send_typing at least 3 times (survived the error)
        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_stops_after_consecutive_failures(self, mock_adapter):
        """Loop stops after 5 consecutive send_typing failures."""
        from gateway.platforms.base import BasePlatformAdapter

        call_count = 0

        async def always_fail(chat_id, metadata=None):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        mock_adapter.send_typing = always_fail
        loop_task = asyncio.create_task(
            BasePlatformAdapter._keep_typing(mock_adapter, "123", interval=0.01)
        )
        await asyncio.wait_for(loop_task, timeout=1.0)

        # Should have tried exactly 5 times then returned
        assert call_count == 5
        mock_adapter.stop_typing.assert_called_once()

    @pytest.mark.asyncio
    async def test_resets_counter_on_success(self, mock_adapter):
        """Consecutive error counter resets after a successful send_typing."""
        from gateway.platforms.base import BasePlatformAdapter

        call_count = 0

        async def fail_twice_then_succeed(chat_id, metadata=None):
            nonlocal call_count
            call_count += 1
            if call_count in (2, 3):
                raise ConnectionError("blip")

        mock_adapter.send_typing = fail_twice_then_succeed
        loop_task = asyncio.create_task(
            BasePlatformAdapter._keep_typing(mock_adapter, "123", interval=0.01)
        )
        await asyncio.sleep(0.06)
        loop_task.cancel()
        try:
            await asyncio.wait_for(loop_task, timeout=1.0)
        except asyncio.CancelledError:
            pass

        # Should have run many iterations (errors were non-consecutive, counter reset)
        assert call_count > 5
