"""Tests for Telegram bot-to-bot message filtering.

Verifies that:
- Bot messages without an explicit @mention of this bot are dropped
- Bot messages with a markdown @mention (renders as text_link entity) are accepted
- Bot messages with a standard mention entity are accepted
- Self-messages (bot's own echo) are dropped
- Normal user messages with mention are unaffected
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from gateway.config import Platform, PlatformConfig


def _make_adapter(require_mention=True):
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.config = PlatformConfig(enabled=True, token="***", extra={"require_mention": require_mention})
    adapter._bot = SimpleNamespace(id=999, username="hermes_bot")
    adapter._message_handler = AsyncMock()
    adapter._pending_text_batches = {}
    adapter._pending_text_batch_tasks = {}
    adapter._text_batch_delay_seconds = 0.01
    adapter._mention_patterns = adapter._compile_mention_patterns()
    return adapter


def _group_message(
    text="hello",
    *,
    chat_id=-100,
    thread_id=None,
    from_user_id=111,
    from_user_is_bot=False,
    entities=None,
    caption=None,
    caption_entities=None,
):
    from_user = SimpleNamespace(id=from_user_id, is_bot=from_user_is_bot)
    return SimpleNamespace(
        text=text,
        caption=caption,
        entities=entities or [],
        caption_entities=caption_entities or [],
        message_thread_id=thread_id,
        chat=SimpleNamespace(id=chat_id, type="group"),
        from_user=from_user,
    )


def _mention_entity(text, mention="@hermes_bot"):
    offset = text.index(mention)
    return SimpleNamespace(type="mention", offset=offset, length=len(mention))


def _text_link_entity(text, mention="@hermes_bot"):
    """Simulates a text_link entity produced by a markdown @mention.

    When a bot sends a message with markdown syntax [@username](https://t.me/username),
    Telegram parses it as a text_link entity whose URL contains the t.me profile link.
    """
    offset = text.index(mention)
    return SimpleNamespace(
        type="text_link",
        offset=offset,
        length=len(mention),
        url=f"https://t.me/{mention.lstrip('@')}",
    )


def _text_mention_entity(text, mention="@hermes_bot"):
    """Simulates a text_mention entity."""
    offset = text.index(mention)
    return SimpleNamespace(
        type="text_mention",
        offset=offset,
        length=len(mention),
        user=SimpleNamespace(id=999),
    )


# ---------------------------------------------------------------------------
# Bot-to-bot filtering
# ---------------------------------------------------------------------------

class TestBotMentionDetection:
    """_bot_mentioned_in_entities must detect all valid Telegram mention formats."""

    def test_text_link_entity_from_markdown_mention_is_detected(self):
        adapter = _make_adapter(require_mention=True)
        # [@hermes_bot](https://t.me/hermes_bot) — markdown @mention renders as text_link
        msg = _group_message(
            "hi [@hermes_bot](https://t.me/hermes_bot)",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_text_link_entity("hi [@hermes_bot](https://t.me/hermes_bot)")],
        )
        # Without the fix, this would be dropped because text_link was not checked
        assert adapter._bot_mentioned_in_entities(msg, "hermes_bot", 999) is True

    def test_standard_mention_entity_is_detected(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "hi @hermes_bot",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_mention_entity("hi @hermes_bot")],
        )
        assert adapter._bot_mentioned_in_entities(msg, "hermes_bot", 999) is True

    def test_text_mention_entity_is_detected(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "hi @hermes_bot",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_text_mention_entity("hi @hermes_bot")],
        )
        assert adapter._bot_mentioned_in_entities(msg, "hermes_bot", 999) is True

    def test_no_mention_returns_false(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message("hello world", from_user_id=888, from_user_is_bot=True, entities=[])
        assert adapter._bot_mentioned_in_entities(msg, "hermes_bot", 999) is False

    def test_mention_of_different_bot_returns_false(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "hi @other_bot",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_text_link_entity("hi @other_bot", "@other_bot")],
        )
        assert adapter._bot_mentioned_in_entities(msg, "hermes_bot", 999) is False


class TestBotMessageFiltering:
    """_should_process_message drops bot messages without an explicit @mention of this bot."""

    def test_bot_message_without_mention_is_dropped(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message("hello from another bot", from_user_id=888, from_user_is_bot=True, entities=[])
        assert adapter._should_process_message(msg) is False

    def test_bot_message_with_markdown_mention_is_accepted(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "[@hermes_bot](https://t.me/hermes_bot) hi",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_text_link_entity("[@hermes_bot](https://t.me/hermes_bot) hi")],
        )
        assert adapter._should_process_message(msg) is True

    def test_bot_message_with_standard_mention_is_accepted(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "@hermes_bot hello",
            from_user_id=888,
            from_user_is_bot=True,
            entities=[_mention_entity("@hermes_bot hello")],
        )
        assert adapter._should_process_message(msg) is True

    def test_user_message_with_mention_is_accepted(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "hi @hermes_bot",
            from_user_id=111,
            from_user_is_bot=False,
            entities=[_mention_entity("hi @hermes_bot")],
        )
        assert adapter._should_process_message(msg) is True

    def test_user_message_without_mention_is_dropped(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message("hello everyone", from_user_id=111, from_user_is_bot=False, entities=[])
        assert adapter._should_process_message(msg) is False

    def test_require_mention_disabled_all_messages_pass(self):
        adapter = _make_adapter(require_mention=False)
        msg = _group_message("hello everyone", from_user_id=888, from_user_is_bot=True, entities=[])
        assert adapter._should_process_message(msg) is True


class TestSelfMessageFiltering:
    """Bot's own messages (echo) must always be dropped."""

    def test_self_message_is_dropped(self):
        adapter = _make_adapter(require_mention=True)
        # Message from the bot itself (echo of its own sent message)
        msg = _group_message("my own text", from_user_id=999, from_user_is_bot=True, entities=[])
        assert adapter._should_process_message(msg) is False

    def test_self_message_with_mention_is_still_dropped(self):
        adapter = _make_adapter(require_mention=True)
        msg = _group_message(
            "@hermes_bot my own text",
            from_user_id=999,
            from_user_is_bot=True,
            entities=[_mention_entity("@hermes_bot my own text")],
        )
        # Even with a mention, self-messages must be dropped to prevent loops
        assert adapter._should_process_message(msg) is False
