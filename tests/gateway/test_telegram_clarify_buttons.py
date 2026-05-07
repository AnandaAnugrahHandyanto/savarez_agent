"""Tests for Telegram clarify-tool inline keyboard wiring.

Covers issue #21032 — the messaging gateway never wired ``clarify_callback``
into the AIAgent, so the clarify tool always returned
``"Clarify tool is not available in this execution context."`` for users on
Telegram. These tests exercise the adapter primitives that the wiring relies
on; the wiring itself is exercised in
``tests/gateway/test_runner_clarify_callback.py``.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


def _ensure_telegram_mock():
    """Wire up the minimal mocks required to import TelegramAdapter."""
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
from gateway.config import PlatformConfig


def _make_adapter():
    config = PlatformConfig(enabled=True, token="test-token", extra={})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


# ===========================================================================
# send_clarify_prompt — inline keyboard buttons
# ===========================================================================

class TestTelegramClarifyPrompt:
    @pytest.mark.asyncio
    async def test_sends_inline_keyboard_with_choices(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 77
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        result = await adapter.send_clarify_prompt(
            chat_id="12345",
            question="Pick a colour:",
            choices=["red", "green", "blue"],
            clarify_id="abcd1234",
        )

        assert result.success is True
        assert result.message_id == "77"

        adapter._bot.send_message.assert_called_once()
        kwargs = adapter._bot.send_message.call_args[1]
        assert kwargs["chat_id"] == 12345
        assert kwargs["text"] == "Pick a colour:"
        assert kwargs["reply_markup"] is not None  # InlineKeyboardMarkup

    @pytest.mark.asyncio
    async def test_sends_skip_button_for_open_ended(self):
        """Open-ended questions still get a Skip button so the user can dismiss."""
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 1
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        await adapter.send_clarify_prompt(
            chat_id="12345",
            question="Anything else?",
            choices=[],
            clarify_id="open1",
        )

        kwargs = adapter._bot.send_message.call_args[1]
        # Skip button is always appended
        assert kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_sends_in_thread(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 1
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)

        await adapter.send_clarify_prompt(
            chat_id="12345",
            question="Q?",
            choices=["a"],
            clarify_id="t1",
            metadata={"thread_id": "5550"},
        )

        kwargs = adapter._bot.send_message.call_args[1]
        assert kwargs.get("message_thread_id") == 5550

    @pytest.mark.asyncio
    async def test_not_connected(self):
        adapter = _make_adapter()
        adapter._bot = None
        result = await adapter.send_clarify_prompt(
            chat_id="12345", question="Q?", choices=["a"], clarify_id="x",
        )
        assert result.success is False


# ===========================================================================
# _handle_callback_query — clarify button clicks
# ===========================================================================

class TestTelegramClarifyCallback:
    @pytest.mark.asyncio
    async def test_choice_resolves_event_and_writes_choice(self):
        adapter = _make_adapter()
        import threading
        ev = threading.Event()
        adapter._clarify_state["xyz"] = {
            "event": ev, "choice": None,
            "choices": ["red", "green", "blue"],
            "question": "Pick a colour:",
        }

        query = AsyncMock()
        query.data = "clarify:xyz:1"  # green
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.from_user.first_name = "Norbert"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await adapter._handle_callback_query(update, context)

        assert ev.is_set()
        assert adapter._clarify_state["xyz"]["choice"] == "green"
        query.answer.assert_called_once()
        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_resolve_choice(self):
        adapter = _make_adapter()
        adapter._is_callback_user_authorized = MagicMock(return_value=False)
        import threading
        ev = threading.Event()
        adapter._clarify_state["locked"] = {
            "event": ev, "choice": None,
            "choices": ["red", "green"],
            "question": "Pick a colour:",
        }

        query = AsyncMock()
        query.data = "clarify:locked:1"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.message.message_thread_id = 777
        query.message.chat = MagicMock()
        query.message.chat.type = "supergroup"
        query.from_user = MagicMock()
        query.from_user.id = 999
        query.from_user.first_name = "Mallory"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await adapter._handle_callback_query(update, context)

        adapter._is_callback_user_authorized.assert_called_once_with(
            "999",
            chat_id=12345,
            chat_type="supergroup",
            thread_id="777",
            user_name="Mallory",
        )
        assert not ev.is_set()
        assert adapter._clarify_state["locked"]["choice"] is None
        query.answer.assert_called_once()
        assert "not authorized" in query.answer.call_args[1]["text"].lower()
        query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_resolves_with_empty_string(self):
        adapter = _make_adapter()
        import threading
        ev = threading.Event()
        adapter._clarify_state["zzz"] = {
            "event": ev, "choice": None,
            "choices": ["a", "b"], "question": "Pick:",
        }

        query = AsyncMock()
        query.data = "clarify:zzz:skip"
        query.message = MagicMock()
        query.from_user = MagicMock()
        query.from_user.first_name = "Alice"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await adapter._handle_callback_query(update, context)

        assert ev.is_set()
        assert adapter._clarify_state["zzz"]["choice"] == ""

    @pytest.mark.asyncio
    async def test_unknown_clarify_id_acks_gracefully(self):
        adapter = _make_adapter()
        # No state for "missing" — already resolved or expired

        query = AsyncMock()
        query.data = "clarify:missing:0"
        query.from_user = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        ack_text = query.answer.call_args[1]["text"]
        assert "no longer active" in ack_text.lower()
        query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_index_rejected(self):
        adapter = _make_adapter()
        import threading
        ev = threading.Event()
        adapter._clarify_state["foo"] = {
            "event": ev, "choice": None,
            "choices": ["only"], "question": "Q?",
        }

        query = AsyncMock()
        query.data = "clarify:foo:99"  # out of range
        query.from_user = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        await adapter._handle_callback_query(update, context)

        # State must NOT be resolved on a bad index
        assert not ev.is_set()
        assert adapter._clarify_state["foo"]["choice"] is None
        query.answer.assert_called_once()
        assert "invalid" in query.answer.call_args[1]["text"].lower()

    @pytest.mark.asyncio
    async def test_does_not_clobber_existing_callbacks(self):
        """clarify: prefix must not match the ea:/sc:/update_prompt: branches."""
        adapter = _make_adapter()
        adapter._approval_state[1] = "session-x"

        query = AsyncMock()
        query.data = "ea:once:1"  # exec-approval, NOT clarify
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.from_user.first_name = "Alice"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        with patch("tools.approval.resolve_gateway_approval", return_value=1) as m:
            await adapter._handle_callback_query(update, context)

        m.assert_called_once()  # ea: still routes to approval
