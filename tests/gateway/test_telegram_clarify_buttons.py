"""Tests for Telegram clarify prompts and callback handling."""

import concurrent.futures
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


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

from gateway.config import PlatformConfig
from gateway.platforms.telegram import TelegramAdapter


def _make_adapter():
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


class TestTelegramClarifyPrompt:
    @pytest.mark.asyncio
    async def test_sends_inline_keyboard_and_stores_state(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 77
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)
        response_future = concurrent.futures.Future()

        result = await adapter.send_clarify_prompt(
            chat_id="12345",
            question="下一步做什么？",
            choices=["修复", "跳过"],
            session_key="agent:main:telegram:group:12345:159975",
            response_future=response_future,
            metadata={"thread_id": "159975"},
        )

        assert result.success is True
        kwargs = adapter._bot.send_message.call_args[1]
        assert kwargs["chat_id"] == 12345
        assert kwargs["message_thread_id"] == 159975
        assert kwargs["reply_markup"] is not None
        assert len(adapter._clarify_state) == 1
        clarify_id = list(adapter._clarify_state.keys())[0]
        state = adapter._clarify_state[clarify_id]
        assert state["session_key"] == "agent:main:telegram:group:12345:159975"
        assert state["response_future"] is response_future
        assert state["choices"] == ["修复", "跳过"]

    @pytest.mark.asyncio
    async def test_open_ended_prompt_tracks_awaiting_text(self):
        adapter = _make_adapter()
        mock_msg = MagicMock()
        mock_msg.message_id = 88
        adapter._bot.send_message = AsyncMock(return_value=mock_msg)
        response_future = concurrent.futures.Future()

        await adapter.send_clarify_prompt(
            chat_id="12345",
            question="请补充说明",
            choices=None,
            session_key="s1",
            response_future=response_future,
        )

        state = adapter._clarify_state[list(adapter._clarify_state.keys())[0]]
        assert state["awaiting_text"] is True
        assert state["response_future"] is response_future


class TestTelegramClarifyCallbacks:
    @pytest.mark.asyncio
    async def test_button_click_resolves_future(self):
        adapter = _make_adapter()
        response_future = concurrent.futures.Future()
        adapter._clarify_state[1] = {
            "session_key": "s1",
            "question": "下一步？",
            "choices": ["修复", "跳过"],
            "response_future": response_future,
            "awaiting_text": False,
            "chat_id": "12345",
            "thread_id": "159975",
        }

        query = AsyncMock()
        query.data = "cq:1:0"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.from_user.first_name = "Gimi"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        await adapter._handle_callback_query(update, MagicMock())

        assert response_future.result(timeout=0.1) == "修复"
        assert 1 not in adapter._clarify_state
        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_other_button_switches_to_text_mode(self):
        adapter = _make_adapter()
        response_future = concurrent.futures.Future()
        adapter._clarify_state[2] = {
            "session_key": "s2",
            "question": "下一步？",
            "choices": ["修复", "跳过"],
            "response_future": response_future,
            "awaiting_text": False,
            "chat_id": "12345",
            "thread_id": "159975",
        }

        query = AsyncMock()
        query.data = "cq:2:other"
        query.message = MagicMock()
        query.message.chat_id = 12345
        query.from_user = MagicMock()
        query.from_user.first_name = "Gimi"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        await adapter._handle_callback_query(update, MagicMock())

        assert adapter._clarify_state[2]["awaiting_text"] is True
        assert response_future.done() is False
        query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_reply_resolves_open_clarify_without_forwarding(self):
        adapter = _make_adapter()
        adapter.handle_message = AsyncMock()
        response_future = concurrent.futures.Future()
        adapter._clarify_state[3] = {
            "session_key": "agent:main:telegram:group:12345:159975",
            "question": "请补充说明",
            "choices": None,
            "response_future": response_future,
            "awaiting_text": True,
            "chat_id": "12345",
            "thread_id": "159975",
        }

        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "我选自定义方案"
        update.message.chat_id = 12345
        update.message.message_thread_id = 159975
        update.message.chat = MagicMock()
        update.message.chat.type = "supergroup"
        update.message.from_user = MagicMock()
        update.message.from_user.id = 1
        update.message.from_user.username = "gimi"
        update.message.from_user.full_name = "Gimi"
        update.message.reply_to_message = None
        update.message.message_id = 999

        await adapter._handle_text_message(update, MagicMock())

        assert response_future.result(timeout=0.1) == "我选自定义方案"
        assert 3 not in adapter._clarify_state
        adapter.handle_message.assert_not_called()
