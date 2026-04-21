"""Test for Telegram file attachment fix (issue #13356)."""

import asyncio
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTelegramSendDocumentFix:
    """Regression tests for issue #13356:
    Telegram text delivery works, file attachments report success but never arrive.
    """

    def test_send_document_returns_error_on_api_failure(self):
        """If Telegram API raises on send_document, adapter must return error,
        not fall back to super().send_document() which sends text."""
        from gateway.platforms.telegram import TelegramAdapter
        from gateway.platforms.base import SendResult

        adapter = MagicMock(spec=TelegramAdapter)
        adapter._bot = MagicMock()
        adapter.name = "telegram"
        adapter._metadata_thread_id = lambda m: None
        adapter._message_thread_id_for_send = lambda t: None
        adapter._missing_media_path_error = TelegramAdapter._missing_media_path_error

        # Simulate API failure
        adapter._bot.send_document = AsyncMock(side_effect=Exception("Network timeout"))

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            # Run the real send_document logic by binding the method
            result = asyncio.run(
                TelegramAdapter.send_document(
                    adapter, "12345", tmp_path, caption="test"
                )
            )
            assert result.success is False
            assert "Network timeout" in result.error
        finally:
            os.unlink(tmp_path)

    def test_send_document_returns_error_on_invalid_response(self):
        """If Telegram API returns None or invalid message, adapter must return error."""
        from gateway.platforms.telegram import TelegramAdapter
        from gateway.platforms.base import SendResult

        adapter = MagicMock(spec=TelegramAdapter)
        adapter._bot = MagicMock()
        adapter.name = "telegram"
        adapter._metadata_thread_id = lambda m: None
        adapter._message_thread_id_for_send = lambda t: None
        adapter._missing_media_path_error = TelegramAdapter._missing_media_path_error

        # Simulate invalid response (None message_id)
        adapter._bot.send_document = AsyncMock(
            return_value=SimpleNamespace(message_id=None)
        )

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            result = asyncio.run(
                TelegramAdapter.send_document(
                    adapter, "12345", tmp_path, caption="test"
                )
            )
            assert result.success is False
            assert "invalid response" in result.error.lower()
        finally:
            os.unlink(tmp_path)

    def test_send_document_success_on_valid_response(self):
        """Normal successful send_document should return success=True with message_id."""
        from gateway.platforms.telegram import TelegramAdapter
        from gateway.platforms.base import SendResult

        adapter = MagicMock(spec=TelegramAdapter)
        adapter._bot = MagicMock()
        adapter.name = "telegram"
        adapter._metadata_thread_id = lambda m: None
        adapter._message_thread_id_for_send = lambda t: None
        adapter._missing_media_path_error = TelegramAdapter._missing_media_path_error

        adapter._bot.send_document = AsyncMock(
            return_value=SimpleNamespace(message_id=42)
        )

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            result = asyncio.run(
                TelegramAdapter.send_document(
                    adapter, "12345", tmp_path, caption="test"
                )
            )
            assert result.success is True
            assert result.message_id == "42"
        finally:
            os.unlink(tmp_path)


class TestSendTelegramToolFix:
    """Regression tests for _send_telegram media delivery fix."""

    def test_media_failure_returns_error_even_if_text_succeeded(self, monkeypatch):
        """If text was sent but file fails, should return error not success."""
        from tools import send_message_tool

        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
        bot.send_document = AsyncMock(side_effect=Exception("Upload failed"))

        # Mock Bot constructor
        monkeypatch.setattr(send_message_tool, "Bot", lambda token: bot)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            result = asyncio.run(
                send_message_tool._send_telegram(
                    "token", "12345", "Hello text", media_files=[(tmp_path, False)]
                )
            )
            assert "error" in result
            assert "Upload failed" in result["error"]
        finally:
            os.unlink(tmp_path)

    def test_media_invalid_response_returns_error(self, monkeypatch):
        """If send_document returns invalid response, should return error."""
        from tools import send_message_tool

        bot = MagicMock()
        bot.send_document = AsyncMock(return_value=SimpleNamespace(message_id=None))

        monkeypatch.setattr(send_message_tool, "Bot", lambda token: bot)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            result = asyncio.run(
                send_message_tool._send_telegram(
                    "token", "12345", "", media_files=[(tmp_path, False)]
                )
            )
            assert "error" in result
            assert "invalid response" in result["error"].lower()
        finally:
            os.unlink(tmp_path)
