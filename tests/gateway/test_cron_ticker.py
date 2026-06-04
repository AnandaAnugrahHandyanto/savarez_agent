"""Regression tests for the gateway cron ticker thread."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import patch

import gateway.run as gateway_run


def test_cron_ticker_survives_cancelled_error(caplog):
    """A BaseException from cron_tick must not kill the ticker thread."""
    stop_event = threading.Event()
    tick_calls: list[str] = []

    def fake_tick(*, verbose=False, adapters=None, loop=None):
        tick_calls.append("tick")
        if len(tick_calls) == 1:
            raise asyncio.CancelledError()
        stop_event.set()

    with caplog.at_level("ERROR"), patch("cron.scheduler.tick", side_effect=fake_tick):
        gateway_run._start_cron_ticker(stop_event, interval=0)

    assert tick_calls == ["tick", "tick"]
    assert "Cron tick error" in caplog.text

