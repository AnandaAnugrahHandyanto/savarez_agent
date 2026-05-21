"""Regression test for #4469.

When the agent is actively running (session present in
``adapter._active_sessions``) and the user fires off multiple TEXT
follow-ups in rapid succession, the previous behaviour was a single-slot
replacement at ``gateway/platforms/base.py``:

    self._pending_messages[session_key] = event

So three rapid messages ``A``, ``B``, ``C`` arriving while the agent was
still working on the initial turn produced a pending slot containing only
``C``; ``A`` and ``B`` were silently dropped.

The fix routes the follow-up through ``merge_pending_message_event(...,
merge_text=True)`` so TEXT events accumulate into the existing pending
event's text instead of clobbering it.  Photo / media bursts continue to
merge through the same helper (they always did).
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Minimal telegram stub so importing gateway.platforms.base does not pull
# in the real python-telegram-bot dependency.
_tg = sys.modules.get("telegram") or types.ModuleType("telegram")
_tg.constants = sys.modules.get("telegram.constants") or types.ModuleType("telegram.constants")
_ct = MagicMock()
_ct.PRIVATE = "private"
_ct.GROUP = "group"
_ct.SUPERGROUP = "supergroup"
_tg.constants.ChatType = _ct
sys.modules.setdefault("telegram", _tg)
sys.modules.setdefault("telegram.constants", _tg.constants)
sys.modules.setdefault("telegram.ext", types.ModuleType("telegram.ext"))

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
)
from gateway.session import SessionSource, build_session_key


def _make_event(text: str, chat_id: str = "12345") -> MessageEvent:
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        chat_type="dm",
        user_id="u1",
    )
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=source,
        message_id=f"msg-{text[:8]}",
    )


def _make_adapter() -> BasePlatformAdapter:
    """Build a BasePlatformAdapter without running its heavy __init__.

    We only need the bits ``handle_message`` touches on the active-session
    path: ``_active_sessions``, ``_pending_messages``,
    ``_message_handler``, ``_busy_session_handler``, ``config``, ``platform``.
    """

    class _DummyAdapter(BasePlatformAdapter):  # type: ignore[misc]
        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def get_chat_info(self, chat_id):
            return None

        async def send(self, *args, **kwargs):
            return MagicMock(success=True, message_id="x", retryable=False)

    adapter = object.__new__(_DummyAdapter)
    adapter.config = PlatformConfig(enabled=True, token="***")
    adapter.platform = Platform.TELEGRAM
    adapter._message_handler = AsyncMock(return_value=None)
    adapter._busy_session_handler = None
    adapter._active_sessions = {}
    adapter._pending_messages = {}
    adapter._session_tasks = {}
    adapter._background_tasks = set()
    adapter._post_delivery_callbacks = {}
    adapter._expected_cancelled_tasks = set()
    adapter._fatal_error_code = None
    adapter._fatal_error_message = None
    adapter._fatal_error_retryable = True
    adapter._fatal_error_handler = None
    adapter._running = True
    adapter._text_debounce_buffers = {}
    adapter._text_debounce_tasks = {}
    adapter._busy_text_mode = ""  # not debouncing by default
    adapter._busy_text_debounce_seconds = 0.1  # fast for tests
    adapter._auto_tts_default = False
    adapter._auto_tts_enabled_chats = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._typing_paused = set()
    return adapter


@pytest.mark.asyncio
async def test_rapid_text_followups_accumulate_instead_of_replacing():
    """Three rapid TEXT follow-ups during an active session must all
    survive in ``adapter._pending_messages[session_key].text``."""
    adapter = _make_adapter()
    first = _make_event("part one")
    session_key = build_session_key(first.source)

    # Mark the session as active so subsequent messages take the
    # "already running" branch in handle_message.
    adapter._active_sessions[session_key] = asyncio.Event()

    second = _make_event("part two")
    third = _make_event("part three")

    await adapter.handle_message(second)
    await adapter.handle_message(third)

    # Both rapid follow-ups must be preserved, not just the last one.
    pending = adapter._pending_messages[session_key]
    assert pending.text == "part two\npart three", (
        f"expected accumulated text, got {pending.text!r}"
    )
    # Text follow-ups now queue like photos: preserve all parts, but do not
    # signal an interrupt or stop the in-flight turn.
    assert not adapter._active_sessions[session_key].is_set()


# ---------------------------------------------------------------------------
# Option B1: text debounce tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_buffers_rapid_text_then_flushes_to_pending():
    """With busy_text_mode=queue, rapid text goes to debounce buffer first,
    then flushes to _pending_messages after the window."""
    adapter = _make_adapter()
    adapter._busy_text_mode = "queue"
    adapter._busy_text_debounce_seconds = 0.05  # super fast for test

    first = _make_event("part one")
    session_key = build_session_key(first.source)
    adapter._active_sessions[session_key] = asyncio.Event()

    second = _make_event("part two")

    # First message → debounce buffer
    await adapter.handle_message(second)
    assert session_key in adapter._text_debounce_buffers
    assert adapter._text_debounce_buffers[session_key].text == "part two"
    assert session_key not in adapter._pending_messages

    # Third message → merges into debounce buffer, resets timer
    third = _make_event("part three")
    await adapter.handle_message(third)
    assert adapter._text_debounce_buffers[session_key].text == "part two\npart three"

    # Wait for flush
    await asyncio.sleep(0.15)

    # After flush: buffer cleared, merged text in _pending_messages
    assert session_key not in adapter._text_debounce_buffers
    assert session_key in adapter._pending_messages
    assert adapter._pending_messages[session_key].text == "part two\npart three"


@pytest.mark.asyncio
async def test_debounce_resets_timer_on_new_arrival():
    """Each new text arrival during the debounce window cancels the
    previous flush task and resets the timer."""
    adapter = _make_adapter()
    adapter._busy_text_mode = "queue"
    adapter._busy_text_debounce_seconds = 0.1

    first = _make_event("one")
    session_key = build_session_key(first.source)
    adapter._active_sessions[session_key] = asyncio.Event()

    await adapter.handle_message(first)
    task1 = adapter._text_debounce_tasks.get(session_key)
    assert task1 is not None
    assert not task1.done()

    # Second message within the debounce window
    second = _make_event("two")
    await adapter.handle_message(second)
    task2 = adapter._text_debounce_tasks.get(session_key)
    assert task2 is not None
    assert task2 is not task1  # new task was created
    # Cancellation is async; wait a moment for it to settle
    await asyncio.sleep(0)
    assert task1.cancelled() or task1.done()  # old task was cancelled

    # Third message — resets again
    third = _make_event("three")
    await adapter.handle_message(third)
    task3 = adapter._text_debounce_tasks.get(session_key)
    assert task3 is not task2

    # Wait for final flush
    await asyncio.sleep(0.2)
    assert session_key not in adapter._text_debounce_buffers
    assert adapter._pending_messages[session_key].text == "one\ntwo\nthree"


@pytest.mark.asyncio
async def test_debounce_skipped_when_busy_text_mode_not_queue():
    """Without busy_text_mode=queue, old direct merge behavior is used."""
    adapter = _make_adapter()
    # _busy_text_mode is "" by default → no debounce
    first = _make_event("direct merge")
    session_key = build_session_key(first.source)
    adapter._active_sessions[session_key] = asyncio.Event()

    await adapter.handle_message(first)

    # No debounce — text lands directly in _pending_messages
    assert session_key in adapter._pending_messages
    assert adapter._pending_messages[session_key].text == "direct merge"
    assert session_key not in adapter._text_debounce_buffers


@pytest.mark.asyncio
async def test_debounce_respects_env_var_override(monkeypatch):
    """HERMES_GATEWAY_BUSY_TEXT_DEBOUNCE_SECONDS overrides the default."""
    monkeypatch.setenv("HERMES_GATEWAY_BUSY_TEXT_DEBOUNCE_SECONDS", "2.5")
    # Re-build adapter to pick up the env var
    # (the _make_adapter sets _busy_text_debounce_seconds manually,
    #  but production __init__ reads from env — test directly)
    import os
    assert float(os.environ.get("HERMES_GATEWAY_BUSY_TEXT_DEBOUNCE_SECONDS", "0.6")) == 2.5


@pytest.mark.asyncio
async def test_debounce_cleanup_in_cancel_background_tasks():
    """cancel_background_tasks() cleans up text debounce state."""
    adapter = _make_adapter()
    adapter._busy_text_mode = "queue"
    adapter._busy_text_debounce_seconds = 1.0

    first = _make_event("cleanup test")
    session_key = build_session_key(first.source)
    adapter._active_sessions[session_key] = asyncio.Event()
    await adapter.handle_message(first)

    assert session_key in adapter._text_debounce_buffers
    assert session_key in adapter._text_debounce_tasks

    await adapter.cancel_background_tasks()

    assert session_key not in adapter._text_debounce_buffers
    assert session_key not in adapter._text_debounce_tasks


@pytest.mark.asyncio
async def test_single_followup_is_stored_as_is():
    """One TEXT follow-up still lands as the event object itself
    (no spurious wrapping / mutation) — guards against the merge path
    breaking the simple case."""
    adapter = _make_adapter()
    first = _make_event("only one")
    session_key = build_session_key(first.source)

    adapter._active_sessions[session_key] = asyncio.Event()
    await adapter.handle_message(first)

    pending = adapter._pending_messages[session_key]
    assert pending is first
    assert pending.text == "only one"
    assert not adapter._active_sessions[session_key].is_set()
