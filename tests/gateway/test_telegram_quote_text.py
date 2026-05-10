"""Tests for Telegram partial-quote handling in _build_message_event.

When a user selects a text fragment in Telegram (partial quote), the cited
fragment is available in message.quote.text. _build_message_event must prefer
that over the full reply_to_message.text / caption.
"""
import sys
from unittest.mock import MagicMock

import pytest

from gateway.config import PlatformConfig
from gateway.platforms.base import MessageType


def _ensure_telegram_mock() -> None:
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    mod = MagicMock()
    mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.constants.ParseMode.MARKDOWN = "Markdown"
    mod.constants.ParseMode.HTML = "HTML"
    mod.constants.ChatType.GROUP = "group"
    mod.constants.ChatType.SUPERGROUP = "supergroup"
    mod.constants.ChatType.CHANNEL = "channel"
    mod.constants.ChatType.PRIVATE = "private"
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules[name] = mod


_ensure_telegram_mock()

from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


@pytest.fixture()
def adapter():
    config = PlatformConfig(enabled=True, token="test-token")
    return TelegramAdapter(config)


def _make_message(
    *,
    reply_text: str | None = "full reply text",
    reply_caption: str | None = None,
    quote_text: str | None = None,
) -> MagicMock:
    """Build a minimal private-chat message mock with a reply and optional partial quote."""
    msg = MagicMock()
    msg.message_id = 1
    msg.text = "user message"
    msg.caption = None
    msg.message_thread_id = None  # must be explicit — MagicMock() is truthy
    msg.date = None

    msg.chat.type = "private"
    msg.chat.id = 100
    msg.chat.title = None

    msg.from_user.id = 42
    msg.from_user.full_name = "Test User"

    reply = MagicMock()
    reply.message_id = 99
    reply.text = reply_text
    reply.caption = reply_caption
    msg.reply_to_message = reply

    if quote_text is not None:
        msg.quote.text = quote_text
    else:
        msg.quote = None

    return msg


class TestQuoteText:
    def test_partial_quote_preferred_over_full_reply(self, adapter):
        msg = _make_message(reply_text="This is the full original message", quote_text="full original")
        event = adapter._build_message_event(msg, MessageType.TEXT)
        assert event.reply_to_text == "full original"

    def test_no_quote_falls_back_to_reply_text(self, adapter):
        msg = _make_message(reply_text="Full reply text", quote_text=None)
        event = adapter._build_message_event(msg, MessageType.TEXT)
        assert event.reply_to_text == "Full reply text"

    def test_no_quote_falls_back_to_reply_caption(self, adapter):
        msg = _make_message(reply_text=None, reply_caption="Photo caption", quote_text=None)
        event = adapter._build_message_event(msg, MessageType.TEXT)
        assert event.reply_to_text == "Photo caption"

    def test_empty_quote_text_falls_back_to_reply_text(self, adapter):
        # quote.text == "" is falsy — must not override full text
        msg = _make_message(reply_text="Full reply text", quote_text="")
        event = adapter._build_message_event(msg, MessageType.TEXT)
        assert event.reply_to_text == "Full reply text"

    def test_no_reply_message_means_no_reply_context(self, adapter):
        msg = _make_message()
        msg.reply_to_message = None
        msg.quote = None
        event = adapter._build_message_event(msg, MessageType.TEXT)
        assert event.reply_to_text is None
        assert event.reply_to_message_id is None
