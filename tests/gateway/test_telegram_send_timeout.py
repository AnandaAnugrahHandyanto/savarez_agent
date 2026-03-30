"""Tests for duplicate-message prevention on Telegram send timeouts.

Root cause (issue #3906): PR #3288 added _send_with_retry() in base which
retries on transient errors.  TelegramAdapter.send() already has an internal
3-attempt retry loop.  When a sendMessage call times out, Telegram may have
already delivered the message even though the HTTP client timed out.  The
stacked retry layers could re-send the same content 2-3 times.

Fix:
- SendResult.delivery_uncertain=True signals that retries would risk duplicates.
- TelegramAdapter._looks_like_send_timeout() detects TimedOut / ReadTimeout.
- send() sets delivery_uncertain=True when the final exception is a timeout.
- _send_with_retry() returns immediately when delivery_uncertain is set.
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import PlatformConfig, Platform
from gateway.platforms.base import SendResult


# ── Fake telegram.error hierarchy ──────────────────────────────────────


class FakeNetworkError(Exception):
    pass


class FakeTimedOut(FakeNetworkError):
    pass


class FakeBadRequest(FakeNetworkError):
    pass


_fake_telegram = types.ModuleType("telegram")
_fake_telegram_error = types.ModuleType("telegram.error")
_fake_telegram_error.NetworkError = FakeNetworkError
_fake_telegram_error.TimedOut = FakeTimedOut
_fake_telegram_error.BadRequest = FakeBadRequest
_fake_telegram.error = _fake_telegram_error
_fake_telegram_constants = types.ModuleType("telegram.constants")
_fake_telegram_constants.ParseMode = SimpleNamespace(MARKDOWN_V2="MarkdownV2")
_fake_telegram.constants = _fake_telegram_constants


@pytest.fixture(autouse=True)
def _inject_fake_telegram(monkeypatch):
    monkeypatch.setitem(sys.modules, "telegram", _fake_telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", _fake_telegram_error)
    monkeypatch.setitem(sys.modules, "telegram.constants", _fake_telegram_constants)


def _make_adapter():
    from gateway.platforms.telegram import TelegramAdapter

    config = PlatformConfig(enabled=True, token="fake-token")
    adapter = object.__new__(TelegramAdapter)
    adapter._config = config
    adapter._platform = Platform.TELEGRAM
    adapter._connected = True
    adapter._dm_topics = {}
    adapter._dm_topics_config = []
    adapter._reply_to_mode = "first"
    adapter._fallback_ips = []
    adapter._polling_conflict_count = 0
    adapter._polling_network_error_count = 0
    adapter._polling_error_callback_ref = None
    adapter.platform = Platform.TELEGRAM
    return adapter


# ── _looks_like_send_timeout ────────────────────────────────────────────


def test_looks_like_send_timeout_timedout_instance():
    """FakeTimedOut (mapped to telegram.error.TimedOut) is detected."""
    from gateway.platforms.telegram import TelegramAdapter
    assert TelegramAdapter._looks_like_send_timeout(FakeTimedOut("timed out")) is True


def test_looks_like_send_timeout_by_class_name():
    """Exception class names containing 'timeout' are detected without import."""
    from gateway.platforms.telegram import TelegramAdapter

    class ReadTimeout(Exception):
        pass

    assert TelegramAdapter._looks_like_send_timeout(ReadTimeout("read timeout")) is True


def test_looks_like_send_timeout_by_class_name_import_free():
    from gateway.platforms.telegram import TelegramAdapter

    class WriteTimeout(Exception):
        pass

    assert TelegramAdapter._looks_like_send_timeout(WriteTimeout()) is True


def test_looks_like_send_timeout_network_error_not_timeout():
    """Generic NetworkError (non-timeout) should NOT be flagged."""
    from gateway.platforms.telegram import TelegramAdapter
    assert TelegramAdapter._looks_like_send_timeout(FakeNetworkError("connection reset")) is False


# ── send() sets delivery_uncertain on timeout ───────────────────────────


@pytest.mark.asyncio
async def test_send_returns_delivery_uncertain_on_timedout():
    """When all send attempts raise TimedOut, delivery_uncertain must be True."""
    adapter = _make_adapter()

    async def always_timeout(**kwargs):
        raise FakeTimedOut("Operation timed out")

    adapter._bot = SimpleNamespace(send_message=always_timeout)

    result = await adapter.send(chat_id="123", content="hello")

    assert result.success is False
    assert result.delivery_uncertain is True


@pytest.mark.asyncio
async def test_send_delivery_uncertain_false_on_non_timeout_error():
    """A non-timeout send failure must NOT set delivery_uncertain."""
    adapter = _make_adapter()

    async def always_fail(**kwargs):
        raise FakeBadRequest("Chat not found")

    adapter._bot = SimpleNamespace(send_message=always_fail)

    result = await adapter.send(chat_id="123", content="hello")

    assert result.success is False
    assert result.delivery_uncertain is False


# ── _send_with_retry suppresses retries on delivery_uncertain ───────────


@pytest.mark.asyncio
async def test_send_with_retry_no_retry_on_delivery_uncertain():
    """_send_with_retry must call send() exactly once when delivery_uncertain=True."""
    adapter = _make_adapter()

    call_count = 0

    async def _mock_send(**kwargs):
        nonlocal call_count
        call_count += 1
        return SendResult(success=False, error="TimedOut", delivery_uncertain=True)

    adapter.send = _mock_send  # type: ignore[method-assign]

    result = await adapter._send_with_retry(chat_id="123", content="hello")

    assert call_count == 1, "send() should not be called more than once when delivery_uncertain=True"
    assert result.delivery_uncertain is True
    assert result.success is False


@pytest.mark.asyncio
async def test_send_with_retry_still_retries_on_normal_network_error():
    """Regular transient errors (not delivery_uncertain) should still be retried."""
    adapter = _make_adapter()

    attempt = [0]

    async def _mock_send(**kwargs):
        attempt[0] += 1
        if attempt[0] == 1:
            return SendResult(success=False, error="connection reset", retryable=True)
        return SendResult(success=True, message_id="42")

    adapter.send = _mock_send  # type: ignore[method-assign]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await adapter._send_with_retry(chat_id="123", content="hello")

    assert result.success is True
    assert attempt[0] == 2
