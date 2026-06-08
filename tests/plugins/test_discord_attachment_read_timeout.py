"""Tests for _read_attachment_bytes timeout behavior.

Regression test for https://github.com/NousResearch/hermes-agent/issues/33400:
When Discord's CDN is slow or unreachable, att.read() can hang indefinitely.
The fix wraps the call in asyncio.wait_for with a 15-second timeout so the
fallback URL download path runs while the signed CDN URL is still valid.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def adapter():
    """Create a minimal DiscordAdapter instance for testing."""
    import importlib
    mod = importlib.import_module("plugins.platforms.discord.adapter")
    # Use __new__ to bypass __init__ which requires complex setup
    obj = mod.DiscordAdapter.__new__(mod.DiscordAdapter)
    return obj


class TestReadAttachmentBytesTimeout:
    """_read_attachment_bytes must time out on slow CDN reads."""

    @pytest.mark.asyncio
    async def test_normal_read_succeeds(self, adapter):
        """Normal case: att.read() returns bytes quickly."""
        att = MagicMock()
        expected = b"fake-audio-data"
        att.read = AsyncMock(return_value=expected)
        att.filename = "voice.ogg"

        result = await adapter._read_attachment_bytes(att)
        assert result == expected

    @pytest.mark.asyncio
    async def test_read_timeout_returns_none(self, adapter):
        """When att.read() hangs past 15s, should return None (triggering fallback)."""
        async def _slow_read():
            await asyncio.sleep(999)  # Simulate indefinite hang
            return b"never-reached"

        att = MagicMock()
        att.read = _slow_read
        att.filename = "voice.ogg"

        # Patch asyncio.wait_for to use a very short timeout for testing
        original_wait_for = asyncio.wait_for

        async def _fast_wait_for(coro, timeout=None):
            return await original_wait_for(coro, timeout=0.05)  # 50ms for test speed

        with patch("asyncio.wait_for", side_effect=_fast_wait_for):
            result = await adapter._read_attachment_bytes(att)

        assert result is None

    @pytest.mark.asyncio
    async def test_read_exception_returns_none(self, adapter):
        """When att.read() raises an exception, should return None."""
        att = MagicMock()
        att.read = AsyncMock(side_effect=ConnectionError("CDN unreachable"))
        att.filename = "voice.ogg"

        result = await adapter._read_attachment_bytes(att)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_read_method_returns_none(self, adapter):
        """When att has no read() method, should return None."""
        att = MagicMock(spec=[])  # No read attribute
        att.filename = "voice.ogg"

        result = await adapter._read_attachment_bytes(att)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_not_callable_returns_none(self, adapter):
        """When att.read exists but is not callable, should return None."""
        att = MagicMock()
        att.read = "not-a-function"
        att.filename = "voice.ogg"

        result = await adapter._read_attachment_bytes(att)
        assert result is None
