"""Tests for Signal gateway approval routing fix (#46866).

When an agent is busy waiting for a dangerous-command approval, user replies
arriving via Signal were previously misrouted as OOB steers, causing approvals
to always time out. This suite verifies the fix: approval replies are
intercepted in _handle_active_session_busy_message before steer/queue logic.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal runner shim that exposes _handle_active_session_busy_message
# ---------------------------------------------------------------------------

def _make_runner():
    """Import and partially init GatewayRunner with the minimal attrs needed."""
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._draining = False
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_ack_ts = {}
    runner._busy_input_mode = "steer"
    runner._busy_text_mode = "steer"
    runner._BUSY_QUEUE_MAX_PENDING = 5
    runner._pending_messages = {}
    runner._is_user_authorized = lambda source: True
    return runner


def _make_event(text: str, chat_id: str = "signal:+15550001234:+15550001234"):
    """Build a minimal MessageEvent-like object."""
    from gateway.config import Platform

    source = SimpleNamespace(
        platform=Platform.SIGNAL,
        chat_id=chat_id,
        user_id="+15550001234",
        user_name="TestUser",
        chat_type="dm",
        thread_id=None,
    )

    def get_command():
        # Mirror gateway.platforms.base.MessageEvent.get_command: only
        # slash-prefixed text is a command; plain text returns None.
        t = (text or "")
        if not t.startswith("/"):
            return None
        parts = t.split(maxsplit=1)
        raw = parts[0][1:].lower() if parts else None
        if raw and "/" in raw:
            return None
        return raw

    event = SimpleNamespace(
        source=source,
        text=text,
        message_id="msg-1",
        message_type=MagicMock(),
        get_command=get_command,
        media_urls=None,
    )
    return event


# ---------------------------------------------------------------------------
# Core routing tests
# ---------------------------------------------------------------------------

class TestApprovalInterceptInBusyHandler:
    """_handle_active_session_busy_message must route approval replies to
    resolve_gateway_approval instead of the steer/queue path (#46866)."""

    SESSION_KEY = "signal:+15550001234:+15550001234"

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @pytest.mark.parametrize("text,expected_choice", [
        ("yes", "once"),
        ("approve", "once"),
        ("/approve", "once"),
        ("ok", "once"),
        ("y", "once"),
        ("always", "always"),
        ("always approve", "always"),
        ("no", "deny"),
        ("deny", "deny"),
        ("/deny", "deny"),
        ("n", "deny"),
        ("cancel", "deny"),
    ])
    def test_approval_reply_intercepted(self, text, expected_choice):
        """Approval keyword replies must call resolve_gateway_approval and
        return True (handled) without falling through to steer/queue."""
        runner = _make_runner()
        event = _make_event(text, self.SESSION_KEY)

        mock_adapter = MagicMock()
        mock_adapter._send_with_retry = AsyncMock()
        runner.adapters = {event.source.platform: mock_adapter}

        with patch("tools.approval.has_blocking_approval", return_value=True) as mock_has, \
             patch("tools.approval.resolve_gateway_approval", return_value=1) as mock_resolve:
            result = self._run(
                runner._handle_active_session_busy_message(event, self.SESSION_KEY)
            )

        assert result is True, f"Expected handled=True for text={text!r}"
        mock_has.assert_called_once_with(self.SESSION_KEY)
        mock_resolve.assert_called_once_with(self.SESSION_KEY, expected_choice)

    def test_no_approval_pending_falls_through(self):
        """When no approval is pending the busy handler must NOT call
        resolve_gateway_approval and must fall through to normal steer/queue."""
        runner = _make_runner()
        event = _make_event("yes", self.SESSION_KEY)

        mock_adapter = MagicMock()
        mock_adapter._send_with_retry = AsyncMock()
        mock_adapter._pending_messages = {}
        runner.adapters = {event.source.platform: mock_adapter}
        runner._running_agents = {self.SESSION_KEY: MagicMock()}
        runner._running_agents_ts = {self.SESSION_KEY: 0}
        runner._busy_ack_ts = {}

        with patch("tools.approval.has_blocking_approval", return_value=False) as mock_has, \
             patch("tools.approval.resolve_gateway_approval") as mock_resolve:
            # May raise (missing attrs) — we only care that resolve wasn't called
            try:
                self._run(
                    runner._handle_active_session_busy_message(event, self.SESSION_KEY)
                )
            except Exception:
                pass

        mock_resolve.assert_not_called()

    def test_unrecognized_text_does_not_resolve(self):
        """Arbitrary text while approval is pending must NOT resolve it —
        only recognized keywords should unblock the agent."""
        runner = _make_runner()
        event = _make_event("what is the weather today?", self.SESSION_KEY)

        mock_adapter = MagicMock()
        mock_adapter._send_with_retry = AsyncMock()
        mock_adapter._pending_messages = {}
        runner.adapters = {event.source.platform: mock_adapter}
        runner._running_agents = {self.SESSION_KEY: MagicMock()}
        runner._running_agents_ts = {self.SESSION_KEY: 0}
        runner._busy_ack_ts = {}

        with patch("tools.approval.has_blocking_approval", return_value=True), \
             patch("tools.approval.resolve_gateway_approval") as mock_resolve:
            try:
                self._run(
                    runner._handle_active_session_busy_message(event, self.SESSION_KEY)
                )
            except Exception:
                pass

        mock_resolve.assert_not_called()

    def test_ack_sent_after_approval_resolved(self):
        """A confirmation message (✅/❌) must be sent back to the user after
        the approval is resolved so they know it was received."""
        runner = _make_runner()
        event = _make_event("approve", self.SESSION_KEY)

        mock_adapter = MagicMock()
        mock_adapter._send_with_retry = AsyncMock()
        runner.adapters = {event.source.platform: mock_adapter}

        with patch("tools.approval.has_blocking_approval", return_value=True), \
             patch("tools.approval.resolve_gateway_approval", return_value=1):
            self._run(
                runner._handle_active_session_busy_message(event, self.SESSION_KEY)
            )

        mock_adapter._send_with_retry.assert_awaited_once()
        call_kwargs = mock_adapter._send_with_retry.call_args
        content = call_kwargs.kwargs.get("content") or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else "")
        assert "✅" in content or "approved" in content.lower(), (
            f"Expected approval ack in response, got: {content!r}"
        )

    def test_unauthorized_user_blocked_before_approval_check(self):
        """The authorization gate must still fire before the approval intercept —
        an unauthorized user must not be able to approve commands."""
        runner = _make_runner()
        runner._is_user_authorized = lambda source: False
        event = _make_event("approve", self.SESSION_KEY)

        with patch("tools.approval.has_blocking_approval") as mock_has, \
             patch("tools.approval.resolve_gateway_approval") as mock_resolve:
            result = self._run(
                runner._handle_active_session_busy_message(event, self.SESSION_KEY)
            )

        assert result is True  # silently dropped
        mock_has.assert_not_called()
        mock_resolve.assert_not_called()
