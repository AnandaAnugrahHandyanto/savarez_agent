"""Regression test: send_message routes MEDIA attachments to email targets.

Verifies that ``_send_to_platform`` dispatches to ``_send_email_with_media``
when the platform is EMAIL and ``media_files`` is non-empty, and that the
resulting SMTP call sends a multipart message with the expected attachments.

Fixes: https://github.com/NousResearch/hermes-agent/issues/38708
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def _email_env(monkeypatch):
    """Provide minimal email credentials via env vars."""
    monkeypatch.setenv("EMAIL_ADDRESS", "test@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_SMTP_PORT", "587")


@pytest.fixture()
def _sample_attachment(tmp_path):
    """Create a small temp file to use as a media attachment."""
    p = tmp_path / "report.pdf"
    p.write_bytes(b"%PDF-1.4 fake pdf content")
    return str(p)


class TestSendEmailWithMedia:
    """Unit tests for ``_send_email_with_media``."""

    @pytest.mark.usefixtures("_email_env")
    def test_single_attachment(self, _sample_attachment):
        from tools.send_message_tool import _send_email_with_media

        captured = {}

        with patch("tools.send_message_tool.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            async def _run():
                return await _send_email_with_media(
                    extra={},
                    chat_id="user@example.com",
                    message="See attached report.",
                    media_files=[(_sample_attachment, False)],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["success"] is True
        assert result["attachments"] == 1
        assert result["platform"] == "email"

        # Verify send_message was called with a multipart message
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg.is_multipart()
        parts = list(msg.walk())
        # multipart/alternative + text/plain + application/octet-stream
        assert len(parts) >= 3
        # The last part should be the attachment
        attachment_part = parts[-1]
        assert "attachment" in attachment_part.get("Content-Disposition", "")
        assert "report.pdf" in attachment_part.get("Content-Disposition", "")

    @pytest.mark.usefixtures("_email_env")
    def test_multiple_attachments(self, tmp_path):
        from tools.send_message_tool import _send_email_with_media

        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")
        f2 = tmp_path / "doc2.csv"
        f2.write_text("a,b,c")

        with patch("tools.send_message_tool.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            async def _run():
                return await _send_email_with_media(
                    extra={},
                    chat_id="user@example.com",
                    message="Two files attached.",
                    media_files=[(str(f1), False), (str(f2), False)],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["success"] is True
        assert result["attachments"] == 2

        msg = mock_server.send_message.call_args[0][0]
        parts = list(msg.walk())
        # text/plain + 2 attachments = at least 4 parts (outer multipart + text + 2 attachments)
        attachment_parts = [
            p for p in parts
            if "attachment" in p.get("Content-Disposition", "")
        ]
        assert len(attachment_parts) == 2

    @pytest.mark.usefixtures("_email_env")
    def test_missing_file_skipped_with_warning(self, monkeypatch, caplog):
        from tools.send_message_tool import _send_email_with_media

        with patch("tools.send_message_tool.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            async def _run():
                return await _send_email_with_media(
                    extra={},
                    chat_id="user@example.com",
                    message="Trying to attach missing file.",
                    media_files=[("/nonexistent/path/file.pdf", False)],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["success"] is True
        assert result["attachments"] == 0  # no valid files
        # Should still send the text body (no crash)
        mock_server.send_message.assert_called_once()

    @pytest.mark.usefixtures("_email_env")
    def test_empty_media_files_sends_text_only(self):
        from tools.send_message_tool import _send_email_with_media

        with patch("tools.send_message_tool.smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            async def _run():
                return await _send_email_with_media(
                    extra={},
                    chat_id="user@example.com",
                    message="Just text, no attachments.",
                    media_files=[],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["success"] is True
        assert result["attachments"] == 0


class TestSendToPlatformEmailMediaRouting:
    """Integration-level test: _send_to_platform dispatches email+media correctly."""

    @pytest.mark.usefixtures("_email_env")
    def test_email_with_media_calls_send_email_with_media(self, _sample_attachment):
        from tools.send_message_tool import _send_to_platform

        with patch(
            "tools.send_message_tool._send_email_with_media",
            new_callable=AsyncMock,
            return_value={"success": True, "platform": "email", "chat_id": "u@e.com", "attachments": 1},
        ) as mock_send, patch(
            "tools.send_message_tool._send_email",
            new_callable=AsyncMock,
        ) as mock_plain:
            from gateway.config import Platform

            pconfig = MagicMock()
            pconfig.extra = {}

            async def _run():
                return await _send_to_platform(
                    Platform.EMAIL, pconfig, "u@e.com",
                    "See attached.", media_files=[(_sample_attachment, False)],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        # Must route to the media-aware function, not the plain one
        mock_send.assert_called_once()
        mock_plain.assert_not_called()
        assert result["success"] is True

    @pytest.mark.usefixtures("_email_env")
    def test_email_without_media_calls_plain_send(self):
        from tools.send_message_tool import _send_to_platform

        with patch(
            "tools.send_message_tool._send_email_with_media",
            new_callable=AsyncMock,
        ) as mock_media, patch(
            "tools.send_message_tool._send_email",
            new_callable=AsyncMock,
            return_value={"success": True, "platform": "email", "chat_id": "u@e.com"},
        ) as mock_plain:
            from gateway.config import Platform

            pconfig = MagicMock()
            pconfig.extra = {}

            async def _run():
                return await _send_to_platform(
                    Platform.EMAIL, pconfig, "u@e.com",
                    "Just text.", media_files=[],
                )

            result = asyncio.get_event_loop().run_until_complete(_run())

        # Without media, should use the plain send
        mock_plain.assert_called_once()
        mock_media.assert_not_called()
        assert result["success"] is True
