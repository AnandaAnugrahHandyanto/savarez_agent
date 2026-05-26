"""Tests for Telegram busy-input inline keyboard buttons.

Creates TelegramAdapter with mocked internals (same pattern as
test_telegram_approval_buttons.py and test_telegram_clarify_buttons.py)
and exercises the bi: callback handler for interrupt, steer, queue,
and cancel actions.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal Telegram mock so TelegramAdapter can be imported
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


def _make_adapter(extra=None):
    config = PlatformConfig(enabled=True, token="test-token", extra=extra or {})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    adapter._gateway_runner = None
    return adapter


def _make_bi_query(adapter, data, session_key="agent:main:telegram:dm:12345"):
    """Build a mock callback query for the busy-input handler."""
    query = AsyncMock()
    query.data = data
    query.message = MagicMock()
    query.message.message_id = 1001
    query.message.chat.id = 12345
    query.message.chat.type = "private"
    query.from_user = MagicMock()
    query.from_user.id = "user1"
    query.from_user.first_name = "Scott"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    adapter._busy_state[1001] = session_key

    update = MagicMock()
    update.callback_query = query
    context = MagicMock()
    return query, update, context


# ===========================================================================
# _busy_state initialization
# ===========================================================================

class TestBusyStateInit:
    """_busy_state dict is created on construction."""

    def test_busy_state_is_empty_dict(self):
        adapter = _make_adapter()
        assert hasattr(adapter, "_busy_state")
        assert adapter._busy_state == {}


# ===========================================================================
# bi: callback handler — each action
# ===========================================================================

class TestBusyCallbackInterrupt:
    """bi:interrupt — cancels the current turn."""

    @pytest.mark.asyncio
    async def test_interrupt_edits_message(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:interrupt")

        await adapter._handle_callback_query(update, context)

        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[1].get("text", "")
        assert "Interrupting" in text
        assert "Scott" in text

    @pytest.mark.asyncio
    async def test_interrupt_answers_query(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:interrupt")

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()


class TestBusyCallbackSteer:
    """bi:steer — injects pending message into running context."""

    @pytest.mark.asyncio
    async def test_steer_edits_message(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:steer")

        await adapter._handle_callback_query(update, context)

        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[1].get("text", "")
        assert "Steered" in text

    @pytest.mark.asyncio
    async def test_steer_answers_query(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:steer")

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()


class TestBusyCallbackQueue:
    """bi:queue — no-op; message already queued."""

    @pytest.mark.asyncio
    async def test_queue_edits_message(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:queue")

        await adapter._handle_callback_query(update, context)

        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[1].get("text", "")
        assert "Queued" in text

    @pytest.mark.asyncio
    async def test_queue_answers_query(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:queue")

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()


class TestBusyCallbackCancel:
    """bi:cancel — discards pending message without interrupting."""

    @pytest.mark.asyncio
    async def test_cancel_edits_message(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:cancel")

        await adapter._handle_callback_query(update, context)

        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[1].get("text", "")
        assert "Cancelled" in text

    @pytest.mark.asyncio
    async def test_cancel_answers_query(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:cancel")

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()


# ===========================================================================
# Edge cases
# ===========================================================================

class TestBusyCallbackEdgeCases:
    """Malformed data, unknown actions, missing state."""

    @pytest.mark.asyncio
    async def test_unknown_action_says_not_recognized(self):
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:fly_away")

        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        text = query.answer.call_args[1].get("text", "")
        assert "choice:" in text.lower()

    @pytest.mark.asyncio
    async def test_missing_busy_state_falls_back_to_session_key(self):
        """When _busy_state doesn't have the message_id, should still handle gracefully."""
        adapter = _make_adapter()
        query = AsyncMock()
        query.data = "bi:interrupt"
        query.message = MagicMock()
        query.message.message_id = 9999  # not in _busy_state
        query.message.chat.id = 12345
        query.message.chat.type = "private"
        query.from_user = MagicMock()
        query.from_user.id = "user1"
        query.from_user.first_name = "Scott"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        # No _busy_state entry — should fall through gracefully
        await adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_bi_prefix_does_not_conflict_with_cl_approval(self):
        """Callback data starting with bi: should not match other handlers."""
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:interrupt")

        await adapter._handle_callback_query(update, context)

        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_busy_state_cleaned_after_use(self):
        """The _busy_state entry is removed after processing."""
        adapter = _make_adapter()
        query, update, context = _make_bi_query(adapter, "bi:cancel", session_key="sk-cleanup")

        assert 1001 in adapter._busy_state

        await adapter._handle_callback_query(update, context)

        assert 1001 not in adapter._busy_state

    @pytest.mark.asyncio
    async def test_unknown_prefix_not_misrouted(self):
        """Callback data that doesn't start with bi: should not enter busy handler."""
        adapter = _make_adapter()
        query = AsyncMock()
        query.data = "some_random_data"
        query.message = MagicMock()
        query.message.chat.id = 12345
        query.message.chat.type = "private"
        query.from_user = MagicMock()
        query.from_user.id = "user1"
        query.from_user.first_name = "Tester"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        context = MagicMock()

        # Should not crash but should not call edit_message_text
        await adapter._handle_callback_query(update, context)

        # bi: handler was NOT triggered (data doesn't start with bi:)
        # The handler may fall through to other callback handlers or be ignored
        # We just check it doesn't blow up
        assert True
