"""Tests for _send_wecom media support (regression test for #27947)."""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


class TestSendWecomMedia:
    """_send_wecom routes media files through adapter._send_media_source."""

    def _make_adapter(self, send_result=None, media_result=None):
        """Build a mock WeComAdapter with configurable results."""
        adapter = MagicMock()
        adapter.connect = AsyncMock(return_value=True)
        adapter.disconnect = AsyncMock(return_value=None)
        adapter.fatal_error_message = None

        if send_result is None:
            send_result = SimpleNamespace(success=True, message_id="msg-123")
        adapter.send = AsyncMock(return_value=send_result)

        if media_result is None:
            media_result = SimpleNamespace(success=True)
        adapter._send_media_source = AsyncMock(return_value=media_result)
        return adapter

    def _run(self, *args, **kwargs):
        from tools.send_message_tool import _send_wecom
        return asyncio.run(_send_wecom(*args, **kwargs))

    def test_text_only_sends_via_adapter_send(self):
        adapter = self._make_adapter()
        with patch("gateway.platforms.wecom.WeComAdapter", return_value=adapter), \
             patch("gateway.platforms.wecom.check_wecom_requirements", return_value=True), \
             patch.dict(os.environ, {"WECOM_BOT_ID": "bot1", "WECOM_BOT_SECRET": "sec1"}):
            result = self._run({"url": "https://wecom.example"}, "chat1", "hello")
        assert result["success"] is True
        assert result["platform"] == "wecom"
        adapter.send.assert_called_once_with("chat1", "hello")
        adapter._send_media_source.assert_not_called()

    def test_media_files_use_send_media_source(self):
        adapter = self._make_adapter()
        with patch("gateway.platforms.wecom.WeComAdapter", return_value=adapter), \
             patch("gateway.platforms.wecom.check_wecom_requirements", return_value=True), \
             patch.dict(os.environ, {"WECOM_BOT_ID": "bot1", "WECOM_BOT_SECRET": "sec1"}):
            result = self._run(
                {"url": "https://wecom.example"},
                "chat1",
                "Here is the file",
                media_files=["/tmp/test.pdf"],
            )
        assert result["success"] is True
        adapter._send_media_source.assert_called_once_with("chat1", "/tmp/test.pdf")
        adapter.send.assert_called_once_with("chat1", "Here is the file")

    def test_media_files_only_no_text(self):
        adapter = self._make_adapter()
        with patch("gateway.platforms.wecom.WeComAdapter", return_value=adapter), \
             patch("gateway.platforms.wecom.check_wecom_requirements", return_value=True), \
             patch.dict(os.environ, {"WECOM_BOT_ID": "bot1", "WECOM_BOT_SECRET": "sec1"}):
            result = self._run(
                {"url": "https://wecom.example"},
                "chat1",
                "   ",
                media_files=["/tmp/doc.pdf"],
            )
        assert result["success"] is True
        adapter._send_media_source.assert_called_once_with("chat1", "/tmp/doc.pdf")
        adapter.send.assert_not_called()

    def test_media_failure_returns_error(self):
        media_fail = SimpleNamespace(success=False, error="upload timeout")
        adapter = self._make_adapter(media_result=media_fail)
        with patch("gateway.platforms.wecom.WeComAdapter", return_value=adapter), \
             patch("gateway.platforms.wecom.check_wecom_requirements", return_value=True), \
             patch.dict(os.environ, {"WECOM_BOT_ID": "bot1", "WECOM_BOT_SECRET": "sec1"}):
            result = self._run(
                {"url": "https://wecom.example"},
                "chat1",
                "text",
                media_files=["/tmp/fail.pdf"],
            )
        assert "error" in result
        assert "upload timeout" in result["error"]

    def test_multiple_media_files_all_sent(self):
        adapter = self._make_adapter()
        with patch("gateway.platforms.wecom.WeComAdapter", return_value=adapter), \
             patch("gateway.platforms.wecom.check_wecom_requirements", return_value=True), \
             patch.dict(os.environ, {"WECOM_BOT_ID": "bot1", "WECOM_BOT_SECRET": "sec1"}):
            result = self._run(
                {"url": "https://wecom.example"},
                "chat1",
                "multiple files",
                media_files=["/tmp/a.pdf", "/tmp/b.png"],
            )
        assert result["success"] is True
        assert adapter._send_media_source.call_count == 2
