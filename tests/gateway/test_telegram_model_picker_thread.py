"""Regression test for #12839 — send_model_picker must route thread_id
through _message_thread_id_for_send so the General-topic sentinel "1"
is converted to None before reaching Telegram's Bot.send_message.

Without this, forum-group General topic messages get
message_thread_id=1 and Telegram returns "Message thread not found",
making /model fall back to text output instead of showing the
interactive inline-keyboard picker.
"""

import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def _install_telegram_mock():
    """Install a minimal telegram mock mirroring the shape used elsewhere."""
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    t = types.ModuleType("telegram")
    t.Update = object
    t.Bot = object
    t.Message = object

    class _FakeButton:
        def __init__(self, label, callback_data=None):
            self.label = label
            self.callback_data = callback_data

    class _FakeMarkup:
        def __init__(self, rows):
            self.rows = rows

    t.InlineKeyboardButton = _FakeButton
    t.InlineKeyboardMarkup = _FakeMarkup
    sys.modules["telegram"] = t

    err = types.ModuleType("telegram.error")

    class _FakeNetworkError(Exception):
        pass
    err.NetworkError = _FakeNetworkError
    err.BadRequest = type("BadRequest", (_FakeNetworkError,), {})
    err.TimedOut = type("TimedOut", (_FakeNetworkError,), {})
    err.RetryAfter = type("RetryAfter", (Exception,), {})
    t.error = err
    sys.modules["telegram.error"] = err

    consts = types.ModuleType("telegram.constants")
    consts.ParseMode = SimpleNamespace(MARKDOWN="Markdown", MARKDOWN_V2="MarkdownV2")
    consts.ChatType = SimpleNamespace(
        GROUP="group", SUPERGROUP="supergroup", CHANNEL="channel", PRIVATE="private"
    )
    t.constants = consts
    sys.modules["telegram.constants"] = consts

    ext = types.ModuleType("telegram.ext")
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=type(None))
    ext.Application = object
    ext.CommandHandler = object
    ext.MessageHandler = object
    ext.CallbackQueryHandler = object
    ext.filters = SimpleNamespace()
    t.ext = ext
    sys.modules["telegram.ext"] = ext

    req = types.ModuleType("telegram.request")
    req.HTTPXRequest = object
    t.request = req
    sys.modules["telegram.request"] = req


_install_telegram_mock()


from gateway.config import PlatformConfig  # noqa: E402
from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


def _make_adapter() -> TelegramAdapter:
    cfg = PlatformConfig(enabled=True, token="fake-token")
    adapter = TelegramAdapter(cfg)
    sent_bot = MagicMock()
    sent_bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=999))
    adapter._bot = sent_bot
    # _link_preview_kwargs is called in send_model_picker; stub with empty dict
    adapter._link_preview_kwargs = lambda: {}
    return adapter


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.new_event_loop().run_until_complete(coro)


def test_send_model_picker_normalizes_general_topic_sentinel_to_none():
    """When thread_id is "1" (General-topic sentinel), send_model_picker
    must pass message_thread_id=None to the bot, not 1 — otherwise
    Telegram rejects with "Message thread not found"."""
    adapter = _make_adapter()

    _run(adapter.send_model_picker(
        chat_id="123456",
        providers=[{"name": "P1", "slug": "p1", "total_models": 1, "models": ["m1"], "is_current": True}],
        current_model="m1",
        current_provider="p1",
        session_key="s1",
        on_model_selected=lambda *_, **__: None,
        metadata={"thread_id": "1"},
    ))

    call = adapter._bot.send_message.call_args
    assert call is not None
    assert call.kwargs.get("message_thread_id") is None, (
        "General-topic sentinel '1' must be normalized to None (#12839)"
    )


def test_send_model_picker_passes_real_thread_id_through():
    """A real numeric topic id must be preserved (not normalized to None)."""
    adapter = _make_adapter()

    _run(adapter.send_model_picker(
        chat_id="123456",
        providers=[{"name": "P1", "slug": "p1", "total_models": 1, "models": ["m1"], "is_current": True}],
        current_model="m1",
        current_provider="p1",
        session_key="s1",
        on_model_selected=lambda *_, **__: None,
        metadata={"thread_id": "42"},
    ))

    call = adapter._bot.send_message.call_args
    assert call is not None
    assert call.kwargs.get("message_thread_id") == 42
