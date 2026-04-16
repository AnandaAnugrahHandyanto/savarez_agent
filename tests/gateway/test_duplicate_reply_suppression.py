"""Tests for duplicate reply suppression across the gateway stack.

Covers three fix paths:
  1. base.py: stale response suppressed when interrupt_event is set and a
     pending message exists (#8221 / #2483)
  2. run.py return path: only explicit final previews / final_response_sent
     suppress base delivery; already_sent alone means interim output was
     visible, not that the final reply was delivered
  3. run.py queued-message path: first response is considered already-streamed
     only when it was explicitly previewed or final_response_sent is True
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    ProcessingOutcome,
    SendResult,
)
from gateway.session import SessionSource, build_session_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class StubAdapter(BasePlatformAdapter):
    """Minimal concrete adapter for testing."""

    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake"), Platform.DISCORD)
        self.sent = []

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append({"chat_id": chat_id, "content": content})
        return SendResult(success=True, message_id="msg1")

    async def send_typing(self, chat_id, metadata=None):
        pass

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}


def _make_event(text="hello", chat_id="c1", user_id="u1"):
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.DISCORD,
            chat_id=chat_id,
            chat_type="dm",
            user_id=user_id,
        ),
        message_id="m1",
    )


# ===================================================================
# Test 1: base.py — stale response suppressed on interrupt (#8221)
# ===================================================================

class TestBaseInterruptSuppression:
    @pytest.mark.asyncio
    async def test_stale_response_suppressed_when_interrupted(self):
        """When interrupt_event is set AND a pending message exists,
        base.py should suppress the stale response instead of sending it."""
        adapter = StubAdapter()

        stale_response = "This is the stale answer to the first question."
        pending_response = "This is the answer to the second question."
        call_count = 0

        async def fake_handler(event):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stale_response
            return pending_response

        adapter.set_message_handler(fake_handler)

        event_a = _make_event(text="first question")
        session_key = build_session_key(event_a.source)

        # Simulate: message A is being processed, message B arrives
        # The interrupt event is set and B is in pending_messages
        interrupt_event = asyncio.Event()
        interrupt_event.set()
        adapter._active_sessions[session_key] = interrupt_event

        event_b = _make_event(text="second question")
        adapter._pending_messages[session_key] = event_b

        await adapter._process_message_background(event_a, session_key)

        # The stale response should NOT have been sent.
        stale_sends = [s for s in adapter.sent if s["content"] == stale_response]
        assert len(stale_sends) == 0, (
            f"Stale response was sent {len(stale_sends)} time(s) — should be suppressed"
        )
        # The pending message's response SHOULD have been sent.
        pending_sends = [s for s in adapter.sent if s["content"] == pending_response]
        assert len(pending_sends) == 1, "Pending message response should be sent"

    @pytest.mark.asyncio
    async def test_response_not_suppressed_without_interrupt(self):
        """Normal case: no interrupt, response should be sent."""
        adapter = StubAdapter()

        async def fake_handler(event):
            return "Normal response"

        adapter.set_message_handler(fake_handler)
        event = _make_event()
        session_key = build_session_key(event.source)

        await adapter._process_message_background(event, session_key)

        assert any(s["content"] == "Normal response" for s in adapter.sent)

    @pytest.mark.asyncio
    async def test_response_not_suppressed_with_interrupt_but_no_pending(self):
        """Interrupt event set but no pending message (race already resolved) —
        response should still be sent."""
        adapter = StubAdapter()

        async def fake_handler(event):
            return "Valid response"

        adapter.set_message_handler(fake_handler)
        event = _make_event()
        session_key = build_session_key(event.source)

        # Set interrupt but no pending message
        interrupt_event = asyncio.Event()
        interrupt_event.set()
        adapter._active_sessions[session_key] = interrupt_event

        await adapter._process_message_background(event, session_key)

        assert any(s["content"] == "Valid response" for s in adapter.sent)


# ===================================================================
# Test 2: run.py — already_sent alone must not suppress final delivery
# ===================================================================

class TestFinalResponseSuppression:
    """Only explicit final previews / final_response_sent suppress base send.

    already_sent=True is broader: it also covers interim commentary or partial
    stream output. Those cases must still fall through to the normal final
    delivery path when final_response_sent=False.
    """

    def _make_mock_stream_consumer(self, already_sent=False, final_response_sent=False):
        sc = SimpleNamespace(
            already_sent=already_sent,
            final_response_sent=final_response_sent,
        )
        return sc

    def _apply_suppression_logic(self, response, sc):
        if isinstance(response, dict) and not response.get("failed"):
            _final = response.get("final_response") or ""
            _is_empty_sentinel = not _final or _final == "(empty)"
            _final_already_delivered = bool(response.get("response_previewed"))
            if sc and getattr(sc, "final_response_sent", False):
                _final_already_delivered = True
            if not _is_empty_sentinel and _final_already_delivered:
                response["already_sent"] = True

    def test_already_sent_without_final_response_sent_does_not_suppress(self):
        """Interim output alone must not suppress the final reply."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=False)
        response = {"final_response": "text", "response_previewed": False}

        self._apply_suppression_logic(response, sc)

        assert "already_sent" not in response

    def test_nothing_sent_does_not_suppress(self):
        """When stream consumer hasn't sent anything, suppression stays off."""
        sc = self._make_mock_stream_consumer(already_sent=False, final_response_sent=False)
        response = {"final_response": "text", "response_previewed": False}

        self._apply_suppression_logic(response, sc)

        assert "already_sent" not in response

    def test_final_response_sent_still_suppresses(self):
        """final_response_sent=True should still work as before."""
        sc = self._make_mock_stream_consumer(already_sent=False, final_response_sent=True)
        response = {"final_response": "text"}

        self._apply_suppression_logic(response, sc)

        assert response.get("already_sent") is True

    def test_response_previewed_still_suppresses(self):
        """Explicit final previews should still suppress the base send."""
        response = {"final_response": "text", "response_previewed": True}

        self._apply_suppression_logic(response, sc=None)

        assert response.get("already_sent") is True

    def test_failed_response_is_never_suppressed(self):
        """Failed responses should never be suppressed — user needs to see
        the error message even if streaming sent earlier partial output."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=False)
        response = {"final_response": "Error: something broke", "failed": True}

        self._apply_suppression_logic(response, sc)

        assert "already_sent" not in response


# ===================================================================
# Test 2b: run.py — empty response never suppressed (#10xxx)
# ===================================================================

class TestEmptyResponseNotSuppressed:
    """When the model returns '(empty)' after tool calls (e.g. mimo-v2-pro
    going silent after web_search), the gateway must NOT suppress delivery
    even if the stream consumer sent intermediate text earlier.

    Without this fix, the user sees partial streaming text ('Let me search
    for that') and then silence — the '(empty)' sentinel is swallowed by
    already_sent=True."""

    def _make_mock_stream_consumer(self, already_sent=False, final_response_sent=False):
        return SimpleNamespace(
            already_sent=already_sent,
            final_response_sent=final_response_sent,
        )

    def _apply_suppression_logic(self, response, sc):
        """Reproduce the fixed logic from gateway/run.py return path."""
        if isinstance(response, dict) and not response.get("failed"):
            _final = response.get("final_response") or ""
            _is_empty_sentinel = not _final or _final == "(empty)"
            _final_already_delivered = bool(response.get("response_previewed"))
            if sc and getattr(sc, "final_response_sent", False):
                _final_already_delivered = True
            if not _is_empty_sentinel and _final_already_delivered:
                response["already_sent"] = True

    def test_empty_sentinel_not_suppressed_with_already_sent(self):
        """'(empty)' final_response should NOT be suppressed even when
        streaming sent intermediate content."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=True)
        response = {"final_response": "(empty)"}
        self._apply_suppression_logic(response, sc)
        assert "already_sent" not in response

    def test_empty_string_not_suppressed_with_already_sent(self):
        """Empty string final_response should NOT be suppressed."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=True)
        response = {"final_response": ""}
        self._apply_suppression_logic(response, sc)
        assert "already_sent" not in response

    def test_none_response_not_suppressed_with_already_sent(self):
        """None final_response should NOT be suppressed."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=True)
        response = {"final_response": None}
        self._apply_suppression_logic(response, sc)
        assert "already_sent" not in response

    def test_real_response_still_suppressed_when_final_response_was_streamed(self):
        """Normal non-empty response should still be suppressed when the
        consumer confirms the final reply was delivered."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=True)
        response = {"final_response": "Here are the search results..."}
        self._apply_suppression_logic(response, sc)
        assert response.get("already_sent") is True

    def test_failed_empty_response_never_suppressed(self):
        """Failed responses are never suppressed regardless of content."""
        sc = self._make_mock_stream_consumer(already_sent=True, final_response_sent=True)
        response = {"final_response": "(empty)", "failed": True}
        self._apply_suppression_logic(response, sc)
        assert "already_sent" not in response

class TestQueuedMessageAlreadyStreamed:
    """Queued-message suppression should key off final delivery only."""

    def _make_mock_sc(self, already_sent=False, final_response_sent=False):
        return SimpleNamespace(
            already_sent=already_sent,
            final_response_sent=final_response_sent,
        )

    def _apply_queued_logic(self, sc, *, response_previewed=False):
        return bool(
            response_previewed or (sc and getattr(sc, "final_response_sent", False))
        )

    def test_already_sent_without_final_response_sent_is_not_already_streamed(self):
        """Interim streaming must not suppress the queued-path base send."""
        _sc = self._make_mock_sc(already_sent=True)

        _already_streamed = self._apply_queued_logic(_sc)

        assert _already_streamed is False

    def test_queued_path_detects_final_response_already_streamed(self):
        """Only final_response_sent=True should skip re-sending."""
        _sc = self._make_mock_sc(already_sent=False, final_response_sent=True)

        _already_streamed = self._apply_queued_logic(_sc)

        assert _already_streamed is True

    def test_queued_path_detects_previewed_response(self):
        """Explicitly previewed finals should skip re-sending too."""
        _already_streamed = self._apply_queued_logic(None, response_previewed=True)

        assert _already_streamed is True

    def test_queued_path_sends_when_not_streamed(self):
        """Nothing was streamed — first response should be sent before
        processing the queued message."""
        _sc = self._make_mock_sc(already_sent=False)

        _already_streamed = self._apply_queued_logic(_sc)

        assert _already_streamed is False

    def test_queued_path_with_no_stream_consumer(self):
        """No stream consumer at all (streaming disabled) — not streamed."""
        _sc = None

        _already_streamed = self._apply_queued_logic(_sc)

        assert _already_streamed is False
