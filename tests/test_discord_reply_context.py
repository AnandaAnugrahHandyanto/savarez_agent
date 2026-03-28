"""Tests for custom fork features — bilibili casting, smart home tools,
Discord enhancements, memory limits, file attachments, slash commands, etc.

All tests mock external hardware/APIs so nothing real is contacted.
"""

import json
import os
import socket
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import (
    MagicMock,
    Mock,
    patch,
)

import pytest


# =========================================================================
# 6. Discord Reply Context Extraction
# =========================================================================


class TestDiscordReplyContext:
    """Test that reply_to_id and reply_to_text are extracted from message.reference."""

    def test_reply_context_extraction_logic(self):
        """Simulate the reply extraction logic from discord.py _handle_message."""
        ref_msg = Mock()
        ref_msg.content = "Original message text"

        reference = Mock()
        reference.message_id = 123456789
        reference.resolved = ref_msg

        message = Mock()
        message.reference = reference

        reply_to_id = None
        reply_to_text = None
        if message.reference and message.reference.message_id:
            reply_to_id = str(message.reference.message_id)
            ref = message.reference.resolved
            if ref and ref.content:
                reply_to_text = ref.content

        assert reply_to_id == "123456789"
        assert reply_to_text == "Original message text"

    def test_reply_context_no_reference(self):
        message = Mock()
        message.reference = None

        reply_to_id = None
        reply_to_text = None
        if message.reference and message.reference.message_id:
            reply_to_id = str(message.reference.message_id)

        assert reply_to_id is None
        assert reply_to_text is None

    def test_reply_context_unresolved(self):
        """When resolved is None, reply_to_text should remain None."""
        reference = Mock()
        reference.message_id = 999
        reference.resolved = None

        message = Mock()
        message.reference = reference

        reply_to_id = None
        reply_to_text = None
        if message.reference and message.reference.message_id:
            reply_to_id = str(message.reference.message_id)
            ref = message.reference.resolved
            if ref and ref.content:
                reply_to_text = ref.content

        assert reply_to_id == "999"
        assert reply_to_text is None

    def test_message_event_has_reply_fields(self):
        """MessageEvent dataclass should have reply_to_message_id and reply_to_text."""
        from gateway.platforms.base import MessageEvent

        event = MessageEvent(text="test")
        assert hasattr(event, "reply_to_message_id")
        assert hasattr(event, "reply_to_text")
        assert event.reply_to_message_id is None
        assert event.reply_to_text is None

    def test_message_event_with_reply(self):
        from gateway.platforms.base import MessageEvent

        event = MessageEvent(
            text="reply text",
            reply_to_message_id="123",
            reply_to_text="original text",
        )
        assert event.reply_to_message_id == "123"
        assert event.reply_to_text == "original text"


# =========================================================================
# 7. /history Slash Command Registration
# =========================================================================


