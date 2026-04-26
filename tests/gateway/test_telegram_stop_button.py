"""Tests for the Telegram ⏳ Stop button (on_processing_start / _handle_callback_query)."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal Telegram mock (same pattern as test_telegram_approval_buttons.py)
# ---------------------------------------------------------------------------
def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    mod = MagicMock()
    mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    mod.constants.ParseMode.MARKDOWN = "Markdown"
    mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.constants.ParseMode.HTML = "HTML"
    mod.constants.ChatType.PRIVATE = "private"
    mod.constants.ChatType.GROUP = "group"
    mod.constants.ChatType.SUPERGROUP = "supergroup"
    mod.constants.ChatType.CHANNEL = "channel"
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

from gateway.platforms.telegram import TelegramAdapter
from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, ProcessingOutcome


def _make_adapter(extra=None):
    config = PlatformConfig(enabled=True, token="test-token", extra=extra or {})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


def _make_event(chat_id="12345", message_id="99", thread_id=None):
    """Build a minimal MessageEvent with a SessionSource stub."""
    source = MagicMock()
    source.chat_id = chat_id
    source.thread_id = thread_id
    event = MagicMock(spec=MessageEvent)
    event.source = source
    event.message_id = message_id
    return event


# ===========================================================================
# on_processing_start — stop stub
# ===========================================================================

class TestSendStopStub:
    """_send_stop_stub sends the ⏳ Working… message with a [🛑 Stop] button."""

    @pytest.mark.asyncio
    async def test_sends_stop_stub_when_enabled(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 77
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-test"):
                event = _make_event()
                await adapter._send_stop_stub(event)

        adapter._bot.send_message.assert_called_once()
        kwargs = adapter._bot.send_message.call_args[1]
        assert kwargs["chat_id"] == 12345
        assert "Working" in kwargs["text"]
        assert kwargs["reply_markup"] is not None
        # Stored in _stop_stubs
        assert adapter._stop_stubs.get("sk-test") == ("12345", "77")

    @pytest.mark.asyncio
    async def test_no_stub_when_not_connected(self):
        adapter = _make_adapter()
        adapter._bot = None

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-test"):
                await adapter._send_stop_stub(_make_event())

        assert "sk-test" not in adapter._stop_stubs

    @pytest.mark.asyncio
    async def test_no_stub_when_no_chat_id(self):
        adapter = _make_adapter()
        adapter._bot.send_message = AsyncMock()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-test"):
                event = _make_event(chat_id=None)
                event.source.chat_id = None
                await adapter._send_stop_stub(event)

        adapter._bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_in_thread(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 77
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-thread"):
                event = _make_event(thread_id="555")
                await adapter._send_stop_stub(event)

        kwargs = adapter._bot.send_message.call_args[1]
        assert kwargs.get("message_thread_id") == 555

    @pytest.mark.asyncio
    async def test_on_processing_start_calls_stub_when_enabled(self):
        adapter = _make_adapter()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true", "TELEGRAM_REACTIONS": "false"}):
            with patch.object(adapter, "_send_stop_stub", new_callable=AsyncMock) as mock_stub:
                await adapter.on_processing_start(_make_event())

        mock_stub.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_processing_start_skips_stub_when_disabled(self):
        adapter = _make_adapter()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "false", "TELEGRAM_REACTIONS": "false"}):
            with patch.object(adapter, "_send_stop_stub", new_callable=AsyncMock) as mock_stub:
                await adapter.on_processing_start(_make_event())

        mock_stub.assert_not_called()


# ===========================================================================
# on_processing_complete — stub cleanup
# ===========================================================================

class TestDeleteStopStub:
    """_delete_stop_stub deletes the stub message on normal completion."""

    @pytest.mark.asyncio
    async def test_deletes_stub_on_complete(self):
        adapter = _make_adapter()
        adapter._stop_stubs["sk-done"] = ("12345", "77")
        adapter._bot.delete_message = AsyncMock()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-done"):
                await adapter._delete_stop_stub(_make_event())

        adapter._bot.delete_message.assert_called_once_with(12345, 77)
        assert "sk-done" not in adapter._stop_stubs

    @pytest.mark.asyncio
    async def test_no_crash_when_stub_missing(self):
        adapter = _make_adapter()
        adapter._bot.delete_message = AsyncMock()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true"}):
            with patch.object(adapter, "_session_key_for_event", return_value="sk-gone"):
                await adapter._delete_stop_stub(_make_event())

        adapter._bot.delete_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_processing_complete_calls_delete_when_enabled(self):
        adapter = _make_adapter()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "true", "TELEGRAM_REACTIONS": "false"}):
            with patch.object(adapter, "_delete_stop_stub", new_callable=AsyncMock) as mock_del:
                await adapter.on_processing_complete(_make_event(), ProcessingOutcome.SUCCESS)

        mock_del.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_processing_complete_skips_delete_when_disabled(self):
        adapter = _make_adapter()

        with patch.dict(os.environ, {"TELEGRAM_STOP_BUTTON": "false", "TELEGRAM_REACTIONS": "false"}):
            with patch.object(adapter, "_delete_stop_stub", new_callable=AsyncMock) as mock_del:
                await adapter.on_processing_complete(_make_event(), ProcessingOutcome.SUCCESS)

        mock_del.assert_not_called()


# ===========================================================================
# _handle_callback_query — st: stop button click
# ===========================================================================

class TestStopButtonCallback:
    """Stop button click handler in _handle_callback_query."""

    def _make_query(self, data: str, user_id: int = 123, chat_id: int = 12345):
        query = AsyncMock()
        query.data = data
        query.message = MagicMock()
        query.message.chat_id = chat_id
        query.from_user = MagicMock()
        query.from_user.id = user_id
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        return query

    @pytest.mark.asyncio
    async def test_stop_click_interrupts_session(self):
        adapter = _make_adapter()
        adapter._stop_stubs["my-session"] = ("12345", "77")

        query = self._make_query("st:my-session")
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": ""}):
            with patch.object(adapter, "interrupt_session_activity", new_callable=AsyncMock) as mock_interrupt:
                await adapter._handle_callback_query(update, context)

        mock_interrupt.assert_called_once_with("my-session", "12345")
        query.answer.assert_called_once()
        assert "Stopping" in query.answer.call_args[1]["text"]
        query.edit_message_text.assert_called_once()
        assert "Stopped" in query.edit_message_text.call_args[1]["text"]
        assert "my-session" not in adapter._stop_stubs

    @pytest.mark.asyncio
    async def test_stop_already_finished(self):
        """Clicking Stop after processing already ended answers gracefully."""
        adapter = _make_adapter()
        # No stub in _stop_stubs — processing already completed

        query = self._make_query("st:expired-session")
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": ""}):
            with patch.object(adapter, "interrupt_session_activity", new_callable=AsyncMock) as mock_interrupt:
                await adapter._handle_callback_query(update, context)

        mock_interrupt.assert_not_called()
        query.answer.assert_called_once()
        assert "already" in query.answer.call_args[1]["text"].lower()

    @pytest.mark.asyncio
    async def test_stop_rejects_unauthorized_user(self):
        adapter = _make_adapter()
        adapter._stop_stubs["sk"] = ("12345", "77")

        query = self._make_query("st:sk", user_id=999)
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": "111"}):
            with patch.object(adapter, "interrupt_session_activity", new_callable=AsyncMock) as mock_interrupt:
                await adapter._handle_callback_query(update, context)

        mock_interrupt.assert_not_called()
        query.answer.assert_called_once()
        assert "not authorized" in query.answer.call_args[1]["text"].lower()
        # Stub should NOT be consumed by unauthorized click
        assert "sk" in adapter._stop_stubs

    @pytest.mark.asyncio
    async def test_stop_allows_authorized_user(self):
        adapter = _make_adapter()
        adapter._stop_stubs["sk"] = ("12345", "77")

        query = self._make_query("st:sk", user_id=111)
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": "111"}):
            with patch.object(adapter, "interrupt_session_activity", new_callable=AsyncMock) as mock_interrupt:
                await adapter._handle_callback_query(update, context)

        mock_interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_approval_callback_not_affected(self):
        """Existing ea: callbacks still work after adding st: handler."""
        adapter = _make_adapter()
        adapter._approval_state[1] = "some-session"

        query = self._make_query("ea:once:1")
        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch.dict(os.environ, {"TELEGRAM_ALLOWED_USERS": ""}):
            with patch("tools.approval.resolve_gateway_approval", return_value=1) as mock_resolve:
                await adapter._handle_callback_query(update, context)

        mock_resolve.assert_called_once_with("some-session", "once")
