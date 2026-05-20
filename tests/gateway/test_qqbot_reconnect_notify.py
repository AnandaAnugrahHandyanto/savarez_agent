"""Regression tests for issue #29005.

QQBot adapter must notify the gateway via the fatal-error handler when its
reconnect budget is exhausted; otherwise the gateway process stays alive but
the platform is permanently dead, with no restart.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.qqbot import QQAdapter, QQCloseError
from gateway.platforms.qqbot import adapter as qq_adapter_mod


def _make_adapter() -> QQAdapter:
    return QQAdapter(PlatformConfig(enabled=True, extra={"app_id": "a", "client_secret": "b"}))


@pytest.mark.asyncio
async def test_listen_loop_notifies_fatal_on_generic_exception_exhaustion(monkeypatch):
    """Exception branch: exhausting MAX_RECONNECT_ATTEMPTS must set fatal + notify."""
    monkeypatch.setattr(qq_adapter_mod, "MAX_RECONNECT_ATTEMPTS", 1)

    adapter = _make_adapter()
    adapter._running = True

    fatal_handler = AsyncMock()
    adapter.set_fatal_error_handler(fatal_handler)

    async def fail(*_a, **_kw):
        raise RuntimeError("boom")

    adapter._read_events = fail  # type: ignore[assignment]
    adapter._reconnect = AsyncMock(return_value=False)  # type: ignore[assignment]
    adapter._mark_transport_disconnected = MagicMock()
    adapter._fail_pending = MagicMock()

    await asyncio.wait_for(adapter._listen_loop(), timeout=2.0)

    assert adapter.has_fatal_error
    assert adapter.fatal_error_code == "qq_reconnect_exhausted"
    fatal_handler.assert_called_once_with(adapter)


@pytest.mark.asyncio
async def test_listen_loop_notifies_fatal_on_qqcloseerror_exhaustion(monkeypatch):
    """QQCloseError branch: same expectation."""
    monkeypatch.setattr(qq_adapter_mod, "MAX_RECONNECT_ATTEMPTS", 1)

    adapter = _make_adapter()
    adapter._running = True

    fatal_handler = AsyncMock()
    adapter.set_fatal_error_handler(fatal_handler)

    async def fail(*_a, **_kw):
        # Use a non-special code so flow falls through to the generic reconnect.
        raise QQCloseError(4000, "transient")

    adapter._read_events = fail  # type: ignore[assignment]
    adapter._reconnect = AsyncMock(return_value=False)  # type: ignore[assignment]
    adapter._mark_transport_disconnected = MagicMock()
    adapter._fail_pending = MagicMock()

    await asyncio.wait_for(adapter._listen_loop(), timeout=2.0)

    assert adapter.has_fatal_error
    assert adapter.fatal_error_code == "qq_reconnect_exhausted"
    fatal_handler.assert_called_once_with(adapter)
