"""Tests for Telegram _edit_overflow_split format-before-chunk fix.

Issue: #43441 — When content exceeds 4096 UTF-16 units, _edit_overflow_split
was chunking the raw text first, then formatting each chunk with MarkdownV2.
The formatting inflates escaping by 4-8 %, pushing each chunk past the limit.
Telegram rejects the oversized formatted chunk and falls back to plain text,
causing raw Markdown markers (**, `, ```) to appear in the user's chat.

The fix mirrors send(): format the entire content first, then chunk the
already-formatted text so every chunk is within the 4096 limit.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.platforms.base import SendResult, utf16_len


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create a minimal TelegramAdapter for testing overflow split."""
    from gateway.config import Platform
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter.MAX_MESSAGE_LENGTH = 4096
    adapter._bot = MagicMock()
    adapter._metadata_thread_id = MagicMock(return_value=None)
    adapter._thread_kwargs_for_send = MagicMock(return_value={})
    adapter._link_preview_kwargs = MagicMock(return_value={})
    adapter._notification_kwargs = MagicMock(return_value={})
    return adapter


class TestEditOverflowSplitFormatBeforeChunk:
    """_edit_overflow_split must format-then-chunk when finalize=True."""

    @pytest.mark.asyncio
    async def test_finalize_formats_entire_content_before_chunking(self):
        """format_message must be called once on the full content, not per-chunk."""
        adapter = _make_adapter()

        # Content that is under 4096 raw but will exceed 4096 after MarkdownV2
        # escaping.  Use **bold** markers that get escaped to \*\*bold\*\*.
        raw_word = "**bold_text_here** "  # 20 chars raw → ~28 chars MarkdownV2
        content = raw_word * 200  # 4000 raw chars, ~5600 formatted

        # Mock format_message to simulate MarkdownV2 inflation
        def fake_format(text):
            # Simulate escaping: ** → \*\*, etc.  ~40% inflation
            return text.replace("**", "\\*\\*").replace("_", "\\_")

        adapter.format_message = fake_format
        adapter.truncate_message = MagicMock(
            side_effect=lambda text, limit, len_fn=None: (
                [text] if (len_fn or len)(text) <= limit
                else [text[:limit], text[limit:]]
            )
        )
        adapter._bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=200))
        adapter._bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=300))

        result = await adapter._edit_overflow_split(
            "12345", 100, content, finalize=True,
        )

        assert result.success
        # truncate_message must have been called with ALREADY-FORMATTED content
        call_args = adapter.truncate_message.call_args
        passed_text = call_args[0][0]
        # The passed text should contain MarkdownV2 escapes
        assert "\\*\\*" in passed_text, (
            "truncate_message received raw content instead of formatted content"
        )

    @pytest.mark.asyncio
    async def test_finalize_chunks_stay_within_limit(self):
        """When finalize=True, each chunk sent to Telegram must be ≤ 4096 UTF-16."""
        adapter = _make_adapter()

        # Build content that exceeds 4096 after formatting
        raw_word = "**code** " * 10 + "\n"  # ~100 raw chars per line
        content = raw_word * 50  # ~5000 raw chars

        def fake_format(text):
            return text.replace("**", "\\*\\*")

        adapter.format_message = fake_format

        # Use the real truncate_message (it's a staticmethod on the base class)
        from gateway.platforms.base import BasePlatformAdapter
        adapter.truncate_message = staticmethod(BasePlatformAdapter.truncate_message)

        sent_texts = []
        async def capture_edit(**kwargs):
            sent_texts.append(kwargs.get("text", ""))
            return SimpleNamespace(message_id=200)

        async def capture_send(**kwargs):
            sent_texts.append(kwargs.get("text", ""))
            return SimpleNamespace(message_id=300)

        adapter._bot.edit_message_text = AsyncMock(side_effect=capture_edit)
        adapter._bot.send_message = AsyncMock(side_effect=capture_send)

        result = await adapter._edit_overflow_split(
            "12345", 100, content, finalize=True,
        )

        assert result.success
        # Every text sent to Telegram must be within the UTF-16 limit
        for i, text in enumerate(sent_texts):
            assert utf16_len(text) <= 4096, (
                f"Chunk {i} exceeds 4096 UTF-16 units: {utf16_len(text)}"
            )

    @pytest.mark.asyncio
    async def test_finalize_false_chunks_raw_content(self):
        """When finalize=False, content is chunked raw (no formatting)."""
        adapter = _make_adapter()

        content = "x" * 5000  # Exceeds 4096

        format_called = MagicMock()
        adapter.format_message = lambda text: (format_called(), text)[1]
        adapter.truncate_message = MagicMock(
            side_effect=lambda text, limit, len_fn=None: (
                [text] if (len_fn or len)(text) <= limit
                else [text[:limit], text[limit:]]
            )
        )
        adapter._bot.edit_message_text = AsyncMock(return_value=SimpleNamespace(message_id=200))
        adapter._bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=300))

        result = await adapter._edit_overflow_split(
            "12345", 100, content, finalize=False,
        )

        assert result.success
        # format_message must NOT have been called for finalize=False
        assert format_called.call_count == 0, (
            "format_message was called even though finalize=False"
        )

    @pytest.mark.asyncio
    async def test_finalize_first_chunk_fallback_strips_mdv2(self):
        """When MarkdownV2 edit fails on first chunk, fallback uses _strip_mdv2."""
        adapter = _make_adapter()

        content = "**bold** " * 300  # ~2700 raw, exceeds after formatting

        def fake_format(text):
            return text.replace("**", "\\*\\*")

        adapter.format_message = fake_format
        adapter.truncate_message = MagicMock(
            side_effect=lambda text, limit, len_fn=None: (
                [text] if (len_fn or len)(text) <= limit
                else [text[:limit], text[limit:]]
            )
        )

        # First call (MarkdownV2) fails, second call (plain) succeeds
        call_count = 0
        async def edit_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("parse_mode"):
                raise Exception("can't parse entities")
            return SimpleNamespace(message_id=200)

        adapter._bot.edit_message_text = AsyncMock(side_effect=edit_side_effect)
        adapter._bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=300))

        result = await adapter._edit_overflow_split(
            "12345", 100, content, finalize=True,
        )

        assert result.success
        # The fallback call must NOT contain MarkdownV2 escapes
        fallback_text = adapter._bot.edit_message_text.call_args_list[-1][1].get("text", "")
        assert "\\*\\*" not in fallback_text, (
            "Fallback should use _strip_mdv2 to remove MarkdownV2 escaping"
        )
