"""Regression tests for #33708: _send_fallback_final must set _final_content_delivered=True.

The gateway's queued-follow-up path in run.py checks:
    _already_streamed = final_response_sent OR response_previewed OR final_content_delivered

Before the fix, _send_fallback_final set _final_response_sent=True but never set
_final_content_delivered=True.  In some Telegram runs final_response_sent stayed
False (e.g. when the fallback delivered via a fresh message rather than an edit)
while _final_content_delivered also stayed False, causing the gateway to log:

  "Queued follow-up ... final stream delivery not confirmed; sending first response
   before continuing."

and then emit a tiny duplicate message to the user.

Three exit paths of _send_fallback_final are covered:
  1. Empty continuation (content already visible) — early return after cursor strip.
  2. Partial delivery failure — some chunks sent, rest failed, early return.
  3. Full successful delivery — all chunks sent.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.stream_consumer import GatewayStreamConsumer, StreamConsumerConfig


# ── helpers ──────────────────────────────────────────────────────────────


def _make_adapter(*, send_succeeds: bool = True, edit_succeeds: bool = True):
    adapter = MagicMock()
    adapter.MAX_MESSAGE_LENGTH = 4096
    adapter.send = AsyncMock(
        return_value=SimpleNamespace(
            success=send_succeeds,
            message_id="msg_fallback_1",
            error="simulated failure" if not send_succeeds else None,
        )
    )
    adapter.edit_message = AsyncMock(
        return_value=SimpleNamespace(success=edit_succeeds)
    )
    # Platform capability flags
    adapter.SUPPORTS_EDIT = True
    # No utf16 override — use plain len
    del adapter.message_len_fn
    return adapter


def _make_consumer(adapter, *, cursor: str = " ▉") -> GatewayStreamConsumer:
    cfg = StreamConsumerConfig(edit_interval=0.0, buffer_threshold=1, cursor=cursor)
    return GatewayStreamConsumer(adapter, chat_id="chat_test", config=cfg)


# ── path 1: empty continuation (content already shown) ───────────────────


class TestFallbackFinalEmptyContinuation:
    """_send_fallback_final when continuation.strip() == '' sets final_content_delivered."""

    @pytest.mark.asyncio
    async def test_empty_continuation_sets_final_content_delivered(self):
        """When content was already streamed and fallback has nothing new to send,
        final_content_delivered must be True so the gateway does not resend."""
        adapter = _make_adapter()
        consumer = _make_consumer(adapter, cursor="")

        # Simulate: consumer already streamed "Hello world" and the fallback
        # is entered with the same text — continuation will be empty.
        consumer._last_sent_text = "Hello world"
        consumer._fallback_prefix = "Hello world"
        consumer._fallback_final_send = True  # entry flag

        await consumer._send_fallback_final("Hello world")

        assert consumer._final_response_sent, (
            "_final_response_sent should be True after empty-continuation fallback"
        )
        assert consumer._final_content_delivered, (  # ← this was the bug
            "_final_content_delivered must be True after empty-continuation fallback "
            "so the gateway queued-follow-up suppression fires correctly (#33708)"
        )


# ── path 2: partial delivery failure ─────────────────────────────────────


class TestFallbackFinalPartialFailure:
    """_send_fallback_final when some chunks land but the last one fails."""

    @pytest.mark.asyncio
    async def test_partial_chunks_sets_final_content_delivered(self):
        """When at least one chunk reaches the user before a send failure,
        final_content_delivered must be True."""
        adapter = _make_adapter()
        send_call_count = 0

        async def _patchy_send(chat_id, content, **kw):
            nonlocal send_call_count
            send_call_count += 1
            if send_call_count == 1:
                return SimpleNamespace(success=True, message_id="msg_1", error=None)
            # Second chunk fails
            return SimpleNamespace(success=False, message_id=None, error="network error")

        adapter.send = _patchy_send
        consumer = _make_consumer(adapter, cursor="")
        consumer._fallback_final_send = True
        consumer._message_id = None
        consumer._last_sent_text = ""
        consumer._fallback_prefix = ""

        # Build a long text that will be split into ≥2 chunks
        long_text = "A" * 3000 + "\n" + "B" * 3000

        await consumer._send_fallback_final(long_text)

        assert consumer._final_response_sent, (
            "_final_response_sent should be True when some chunks reached user"
        )
        assert consumer._final_content_delivered, (  # ← this was the bug
            "_final_content_delivered must be True when partial chunks reached user (#33708)"
        )


# ── path 3: full successful delivery ─────────────────────────────────────


class TestFallbackFinalFullSuccess:
    """_send_fallback_final when all chunks succeed."""

    @pytest.mark.asyncio
    async def test_full_success_sets_final_content_delivered(self):
        """Normal happy-path fallback must set final_content_delivered=True."""
        adapter = _make_adapter(send_succeeds=True)
        consumer = _make_consumer(adapter, cursor="")
        consumer._fallback_final_send = True
        consumer._message_id = None
        consumer._last_sent_text = ""
        consumer._fallback_prefix = ""

        await consumer._send_fallback_final("The quick brown fox jumps over the lazy dog.")

        assert consumer._final_response_sent, (
            "_final_response_sent should be True after successful fallback send"
        )
        assert consumer._final_content_delivered, (  # ← this was the bug
            "_final_content_delivered must be True after successful fallback send (#33708)"
        )

    @pytest.mark.asyncio
    async def test_gateway_suppression_flag_is_consistent(self):
        """Simulate the run.py _already_streamed check:
           final_response_sent OR final_content_delivered must be True
           after any successful fallback delivery path."""
        adapter = _make_adapter(send_succeeds=True)
        consumer = _make_consumer(adapter, cursor="")
        consumer._fallback_final_send = True
        consumer._message_id = None
        consumer._last_sent_text = ""
        consumer._fallback_prefix = ""

        await consumer._send_fallback_final("Response text.")

        # Mimic run.py line ~17927:
        _already_streamed = (
            consumer.final_response_sent
            or consumer.final_content_delivered
        )
        assert _already_streamed, (
            "run.py suppression flag (_already_streamed) must be truthy after fallback; "
            "got final_response_sent=%s, final_content_delivered=%s" % (
                consumer.final_response_sent, consumer.final_content_delivered
            )
        )
