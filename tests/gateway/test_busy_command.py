"""Tests for gateway /busy command extras (dedupe toggle)."""

import time
from unittest.mock import MagicMock

import pytest

# Minimal telegram stubs for gateway imports
import sys, types

_tg = types.ModuleType("telegram")
_tg.constants = types.ModuleType("telegram.constants")
_ct = MagicMock()
_ct.SUPERGROUP = "supergroup"
_ct.GROUP = "group"
_ct.PRIVATE = "private"
_tg.constants.ChatType = _ct
sys.modules.setdefault("telegram", _tg)
sys.modules.setdefault("telegram.constants", _tg.constants)
sys.modules.setdefault("telegram.ext", types.ModuleType("telegram.ext"))

from gateway.platforms.base import MessageEvent, MessageType, SessionSource


def _make_event(text="/busy status", chat_id="123", platform_val="telegram"):
    source = SessionSource(
        platform=MagicMock(value=platform_val),
        chat_id=chat_id,
        chat_type="private",
        user_id="user1",
    )
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=source,
        message_id="msg1",
    )


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._busy_input_mode = "interrupt"
    runner._busy_retry_after_ts = {}
    runner._busy_queue_config = {
        "enabled": True,
        "dedupe_exact": True,
        "default_priority": "P1",
    }
    runner._queued_events = {}
    runner.adapters = {}
    return runner


@pytest.mark.asyncio
async def test_busy_status_includes_dedupe_line():
    runner = _make_runner()
    event = _make_event("/busy status")

    msg = await runner._handle_busy_command(event)

    assert "Queue dedupe" in msg
    assert "`on`" in msg


@pytest.mark.asyncio
async def test_busy_dedupe_off_updates_runtime_and_persists(tmp_path, monkeypatch):
    import gateway.run as _gr

    monkeypatch.setattr(_gr, "_hermes_home", tmp_path)

    runner = _make_runner()
    event = _make_event("/busy dedupe off")

    msg = await runner._handle_busy_command(event)

    assert "dedupe set to `off`" in msg
    assert runner._busy_queue_config.get("dedupe_exact") is False


@pytest.mark.asyncio
async def test_busy_dedupe_invalid_usage():
    runner = _make_runner()
    event = _make_event("/busy dedupe maybe")

    msg = await runner._handle_busy_command(event)

    assert "Usage: `/busy dedupe on|off`" in msg
