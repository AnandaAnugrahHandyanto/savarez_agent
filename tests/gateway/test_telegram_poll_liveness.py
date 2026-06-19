"""
Tests for the Telegram polling-liveness watchdog.

The watchdog detects the "process alive, poller dead" failure mode:
the Updater reports running=True but the getUpdates loop silently stopped
delivering updates (observed on 2026-06-16 after transient network errors).

When the liveness timestamp hasn't been refreshed for longer than the
configured timeout AND updater.running is True, the watchdog fires
_handle_polling_network_error — a full teardown + reconnect, NOT a soft
resume.

Tests also cover:
- _refresh_poll_liveness updates the timestamp
- watchdog exits cleanly when disabled (timeout=0)
- watchdog does NOT fire when adapter is shutting down (has_fatal_error)
- watchdog does NOT fire in webhook mode
- watchdog does NOT fire when updater isn't running (reconnect already in flight)
- misleading "polling resumed" log message is replaced (verifies new wording)
"""
from __future__ import annotations

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    telegram_mod = MagicMock()
    telegram_mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    telegram_mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    telegram_mod.constants.ChatType.GROUP = "group"
    telegram_mod.constants.ChatType.SUPERGROUP = "supergroup"
    telegram_mod.constants.ChatType.CHANNEL = "channel"
    telegram_mod.constants.ChatType.PRIVATE = "private"

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, telegram_mod)


_ensure_telegram_mock()

from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


@pytest.fixture(autouse=True)
def _no_auto_discovery(monkeypatch):
    """Disable DoH auto-discovery so connect() uses the plain builder chain."""
    async def _noop():
        return []
    monkeypatch.setattr("gateway.platforms.telegram.discover_fallback_ips", _noop)


def _make_adapter() -> TelegramAdapter:
    return TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))


def _make_running_app():
    mock_updater = MagicMock()
    mock_updater.running = True
    mock_updater.stop = AsyncMock()
    mock_updater.start_polling = AsyncMock()

    mock_app = MagicMock()
    mock_app.updater = mock_updater
    return mock_app


# ── _refresh_poll_liveness ─────────────────────────────────────────────────

def test_refresh_poll_liveness_updates_timestamp():
    """_refresh_poll_liveness should set _last_successful_poll_at to now."""
    adapter = _make_adapter()
    before = time.monotonic()
    adapter._refresh_poll_liveness()
    after = time.monotonic()

    assert adapter._last_successful_poll_at is not None
    assert before <= adapter._last_successful_poll_at <= after


def test_refresh_poll_liveness_idempotent():
    """Multiple calls to _refresh_poll_liveness always advance the timestamp."""
    adapter = _make_adapter()
    adapter._refresh_poll_liveness()
    t1 = adapter._last_successful_poll_at
    # Tiny sleep so monotonic clock can advance
    time.sleep(0.01)
    adapter._refresh_poll_liveness()
    t2 = adapter._last_successful_poll_at

    assert t2 is not None and t1 is not None
    assert t2 >= t1


# ── Watchdog disabled ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_watchdog_disabled_when_timeout_zero(monkeypatch):
    """Watchdog returns immediately without any sleeps when timeout=0."""
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "0")
    adapter = _make_adapter()

    sleep_calls = []
    async def _fake_sleep(t):
        sleep_calls.append(t)

    with patch("asyncio.sleep", side_effect=_fake_sleep):
        await adapter._start_poll_liveness_watchdog()

    assert sleep_calls == [], "Watchdog must not sleep when disabled"


# ── Watchdog fires on timeout ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_watchdog_fires_reconnect_on_liveness_timeout(monkeypatch):
    """
    When the liveness timestamp is older than the timeout AND the updater is
    running, the watchdog must call _handle_polling_network_error (full
    teardown+reconnect path).

    The watchdog seeds self._last_successful_poll_at at startup via
    time.monotonic(), so we mock time.monotonic to return T0 for the seed
    and T0 + 200 for the age check (200s >> 60s timeout).
    """
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "60")
    adapter = _make_adapter()
    adapter._app = _make_running_app()
    adapter._webhook_mode = False

    # Mock time.monotonic so the watchdog sees an expired timestamp:
    # call 1 = seed (T0), all subsequent = T0 + 200 (well past 60s timeout).
    T0 = 1_000_000.0
    call_count = 0

    def _mock_monotonic() -> float:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return T0  # watchdog seeds _last_successful_poll_at = T0
        return T0 + 200.0  # age = 200s > 60s timeout

    reconnect_calls: list = []

    async def _fake_reconnect(err):
        reconnect_calls.append(err)

    adapter._handle_polling_network_error = _fake_reconnect  # type: ignore[method-assign]

    # Let the watchdog run one full check cycle then stop
    sleep_count = 0

    async def _controlled_sleep(t):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise StopAsyncIteration("stop after one cycle")

    with patch("gateway.platforms.telegram.time.monotonic", side_effect=_mock_monotonic):
        with patch("asyncio.sleep", side_effect=_controlled_sleep):
            with pytest.raises(StopAsyncIteration):
                await adapter._start_poll_liveness_watchdog()

    assert len(reconnect_calls) == 1, (
        f"Expected exactly 1 reconnect call, got {len(reconnect_calls)}"
    )
    err_msg = str(reconnect_calls[0])
    assert "liveness timeout" in err_msg.lower() or "Poll liveness" in err_msg


@pytest.mark.asyncio
async def test_watchdog_does_not_fire_when_liveness_fresh(monkeypatch):
    """
    When the liveness timestamp is recent (within the timeout window), the
    watchdog must NOT fire a reconnect.
    """
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "300")
    adapter = _make_adapter()
    adapter._app = _make_running_app()
    adapter._webhook_mode = False

    # Fresh timestamp — should not trigger
    adapter._last_successful_poll_at = time.monotonic()

    reconnect_calls: list = []

    async def _fake_reconnect(err):
        reconnect_calls.append(err)

    adapter._handle_polling_network_error = _fake_reconnect  # type: ignore[method-assign]

    sleep_count = 0

    async def _controlled_sleep(t):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise StopAsyncIteration("stop after one cycle")

    with patch("asyncio.sleep", side_effect=_controlled_sleep):
        with pytest.raises(StopAsyncIteration):
            await adapter._start_poll_liveness_watchdog()

    assert reconnect_calls == [], "Watchdog must not fire when liveness is fresh"


# ── Guard conditions ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_watchdog_exits_on_fatal_error(monkeypatch):
    """
    When has_fatal_error is True (adapter shutting down), the watchdog must
    return without triggering a reconnect.

    The watchdog returns after the first sleep when fatal_error is set — so
    we let it run to natural completion (no StopAsyncIteration needed).
    """
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "60")
    adapter = _make_adapter()
    adapter._app = _make_running_app()
    adapter._webhook_mode = False

    # Simulate fatal error already set
    adapter._set_fatal_error("test", "simulated fatal", retryable=False)

    reconnect_calls: list = []

    async def _fake_reconnect(err):
        reconnect_calls.append(err)

    adapter._handle_polling_network_error = _fake_reconnect  # type: ignore[method-assign]

    # Watchdog sleeps once then returns when it sees has_fatal_error=True.
    # We allow that one sleep so the function completes naturally.
    async def _noop_sleep(t):
        pass

    with patch("asyncio.sleep", side_effect=_noop_sleep):
        await adapter._start_poll_liveness_watchdog()

    assert reconnect_calls == [], (
        "Watchdog must not fire reconnect when adapter has a fatal error"
    )


@pytest.mark.asyncio
async def test_watchdog_skips_in_webhook_mode(monkeypatch):
    """
    Webhook mode doesn't use getUpdates — watchdog must return without
    triggering a reconnect.

    The watchdog returns after the first sleep when _webhook_mode is True.
    """
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "60")
    adapter = _make_adapter()
    adapter._app = _make_running_app()
    adapter._webhook_mode = True

    reconnect_calls: list = []

    async def _fake_reconnect(err):
        reconnect_calls.append(err)

    adapter._handle_polling_network_error = _fake_reconnect  # type: ignore[method-assign]

    # Watchdog sleeps once then returns when it sees _webhook_mode=True.
    async def _noop_sleep(t):
        pass

    with patch("asyncio.sleep", side_effect=_noop_sleep):
        await adapter._start_poll_liveness_watchdog()

    assert reconnect_calls == [], (
        "Watchdog must not fire reconnect in webhook mode"
    )


@pytest.mark.asyncio
async def test_watchdog_skips_when_updater_not_running(monkeypatch):
    """
    When updater.running is False, a reconnect is already in flight via the
    error callback path — watchdog must not double-trigger.
    """
    monkeypatch.setenv("HERMES_POLL_LIVENESS_TIMEOUT", "60")
    adapter = _make_adapter()

    mock_updater = MagicMock()
    mock_updater.running = False  # updater is stopped / reconnect in flight
    mock_app = MagicMock()
    mock_app.updater = mock_updater
    adapter._app = mock_app
    adapter._webhook_mode = False
    adapter._last_successful_poll_at = time.monotonic() - 120  # expired

    reconnect_calls: list = []

    async def _fake_reconnect(err):
        reconnect_calls.append(err)

    adapter._handle_polling_network_error = _fake_reconnect  # type: ignore[method-assign]

    sleep_count = 0

    async def _controlled_sleep(t):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise StopAsyncIteration("stop")

    with patch("asyncio.sleep", side_effect=_controlled_sleep):
        with pytest.raises(StopAsyncIteration):
            await adapter._start_poll_liveness_watchdog()

    assert reconnect_calls == [], (
        "Watchdog must not fire when updater.running is False (reconnect already in flight)"
    )


# ── Log message accuracy ───────────────────────────────────────────────────

def test_reconnect_log_message_wording():
    """
    The 'polling resumed' log message must be replaced with 'reconnect
    initiated — awaiting first getUpdates cycle to confirm liveness' so that
    the message accurately reflects what has (and hasn't) happened.

    Regression guard: the OLD wording said 'Telegram polling resumed after
    network error' which was misleading — start_polling() returning doesn't
    mean the long-poll loop is actually alive.
    """
    import inspect
    import gateway.platforms.telegram as tg_module

    source = inspect.getsource(tg_module)

    old_misleading_phrase = "polling resumed after network error"
    assert old_misleading_phrase not in source, (
        f"Misleading log phrase '{old_misleading_phrase}' still present in telegram.py — "
        "it should be replaced with wording that reflects the reconnect is only initiated, "
        "not confirmed"
    )

    new_accurate_phrase = "reconnect initiated"
    assert new_accurate_phrase in source, (
        f"Expected accurate log phrase '{new_accurate_phrase}' in telegram.py"
    )
