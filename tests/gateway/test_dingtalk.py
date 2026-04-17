"""Tests for DingTalk platform adapter."""
import asyncio
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from gateway.config import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Requirements check
# ---------------------------------------------------------------------------


class TestDingTalkRequirements:

    def test_returns_false_when_sdk_missing(self, monkeypatch):
        with patch.dict("sys.modules", {"dingtalk_stream": None}):
            monkeypatch.setattr(
                "gateway.platforms.dingtalk.DINGTALK_STREAM_AVAILABLE", False
            )
            from gateway.platforms.dingtalk import check_dingtalk_requirements
            assert check_dingtalk_requirements() is False

    def test_returns_false_when_env_vars_missing(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.platforms.dingtalk.DINGTALK_STREAM_AVAILABLE", True
        )
        monkeypatch.setattr("gateway.platforms.dingtalk.HTTPX_AVAILABLE", True)
        monkeypatch.delenv("DINGTALK_CLIENT_ID", raising=False)
        monkeypatch.delenv("DINGTALK_CLIENT_SECRET", raising=False)
        from gateway.platforms.dingtalk import check_dingtalk_requirements
        assert check_dingtalk_requirements() is False

    def test_returns_true_when_all_available(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.platforms.dingtalk.DINGTALK_STREAM_AVAILABLE", True
        )
        monkeypatch.setattr("gateway.platforms.dingtalk.HTTPX_AVAILABLE", True)
        monkeypatch.setenv("DINGTALK_CLIENT_ID", "test-id")
        monkeypatch.setenv("DINGTALK_CLIENT_SECRET", "test-secret")
        from gateway.platforms.dingtalk import check_dingtalk_requirements
        assert check_dingtalk_requirements() is True


# ---------------------------------------------------------------------------
# Adapter construction
# ---------------------------------------------------------------------------


class TestDingTalkAdapterInit:

    def test_reads_config_from_extra(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        config = PlatformConfig(
            enabled=True,
            extra={"client_id": "cfg-id", "client_secret": "cfg-secret"},
        )
        adapter = DingTalkAdapter(config)
        assert adapter._client_id == "cfg-id"
        assert adapter._client_secret == "cfg-secret"
        assert adapter.name == "Dingtalk"  # base class uses .title()

    def test_falls_back_to_env_vars(self, monkeypatch):
        monkeypatch.setenv("DINGTALK_CLIENT_ID", "env-id")
        monkeypatch.setenv("DINGTALK_CLIENT_SECRET", "env-secret")
        from gateway.platforms.dingtalk import DingTalkAdapter
        config = PlatformConfig(enabled=True)
        adapter = DingTalkAdapter(config)
        assert adapter._client_id == "env-id"
        assert adapter._client_secret == "env-secret"


# ---------------------------------------------------------------------------
# Message text extraction
# ---------------------------------------------------------------------------


class TestExtractText:

    def test_extracts_dict_text(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        msg = MagicMock()
        msg.text = {"content": "  hello world  "}
        msg.rich_text = None
        assert DingTalkAdapter._extract_text(msg) == "hello world"

    def test_extracts_string_text(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        msg = MagicMock()
        msg.text = "plain text"
        msg.rich_text = None
        assert DingTalkAdapter._extract_text(msg) == "plain text"

    def test_falls_back_to_rich_text(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        msg = MagicMock()
        msg.text = ""
        msg.rich_text = [{"text": "part1"}, {"text": "part2"}, {"image": "url"}]
        assert DingTalkAdapter._extract_text(msg) == "part1 part2"

    def test_returns_empty_for_no_content(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        msg = MagicMock()
        msg.text = ""
        msg.rich_text = None
        assert DingTalkAdapter._extract_text(msg) == ""


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:

    def test_first_message_not_duplicate(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        assert adapter._dedup.is_duplicate("msg-1") is False

    def test_second_same_message_is_duplicate(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._dedup.is_duplicate("msg-1")
        assert adapter._dedup.is_duplicate("msg-1") is True

    def test_different_messages_not_duplicate(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._dedup.is_duplicate("msg-1")
        assert adapter._dedup.is_duplicate("msg-2") is False

    def test_cache_cleanup_on_overflow(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        max_size = adapter._dedup._max_size
        # Fill beyond max
        for i in range(max_size + 10):
            adapter._dedup.is_duplicate(f"msg-{i}")
        # Cache should have been pruned
        assert len(adapter._dedup._seen) <= max_size + 10


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


class TestSend:

    @pytest.mark.asyncio
    async def test_send_posts_to_webhook(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._http_client = mock_client

        result = await adapter.send(
            "chat-123", "Hello!",
            metadata={"session_webhook": "https://dingtalk.example/webhook"}
        )
        assert result.success is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://dingtalk.example/webhook"
        payload = call_args[1]["json"]
        assert payload["msgtype"] == "markdown"
        assert payload["markdown"]["title"] == "Hermes"
        assert payload["markdown"]["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_fails_without_webhook(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._http_client = AsyncMock()

        result = await adapter.send("chat-123", "Hello!")
        assert result.success is False
        assert "session_webhook" in result.error

    @pytest.mark.asyncio
    async def test_send_uses_cached_webhook(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._http_client = mock_client
        adapter._session_webhooks["chat-123"] = "https://cached.example/webhook"

        result = await adapter.send("chat-123", "Hello!")
        assert result.success is True
        assert mock_client.post.call_args[0][0] == "https://cached.example/webhook"

    @pytest.mark.asyncio
    async def test_send_handles_http_error(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        adapter._http_client = mock_client

        result = await adapter.send(
            "chat-123", "Hello!",
            metadata={"session_webhook": "https://example/webhook"}
        )
        assert result.success is False
        assert "400" in result.error


# ---------------------------------------------------------------------------
# Connect / disconnect
# ---------------------------------------------------------------------------


class TestConnect:

    @pytest.mark.asyncio
    async def test_connect_fails_without_sdk(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.platforms.dingtalk.DINGTALK_STREAM_AVAILABLE", False
        )
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        result = await adapter.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_fails_without_credentials(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._client_id = ""
        adapter._client_secret = ""
        result = await adapter.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self):
        from gateway.platforms.dingtalk import DingTalkAdapter
        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._session_webhooks["a"] = "http://x"
        adapter._dedup._seen["b"] = 1.0
        adapter._http_client = AsyncMock()
        adapter._stream_task = None

        await adapter.disconnect()
        assert len(adapter._session_webhooks) == 0
        assert len(adapter._dedup._seen) == 0
        assert adapter._http_client is None


# ---------------------------------------------------------------------------
# Incoming handler
# ---------------------------------------------------------------------------


class TestIncomingHandler:

    @staticmethod
    def _start_background_loop():
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        return loop, thread

    @staticmethod
    def _stop_background_loop(loop, thread):
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()

    def test_process_converts_callback_payload_before_dispatch(self, monkeypatch):
        from gateway.platforms import dingtalk
        from gateway.platforms.dingtalk import DingTalkAdapter, _IncomingHandler

        fake_stream = SimpleNamespace(AckMessage=SimpleNamespace(STATUS_OK="OK"))
        converted = SimpleNamespace(session_webhook="https://api.dingtalk.com/webhook")
        from_dict = MagicMock(return_value=converted)

        monkeypatch.setattr(dingtalk, "dingtalk_stream", fake_stream)
        monkeypatch.setattr(
            dingtalk,
            "ChatbotMessage",
            SimpleNamespace(from_dict=from_dict),
            raising=False,
        )

        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._on_message = AsyncMock()
        loop, thread = self._start_background_loop()
        try:
            handler = _IncomingHandler(adapter, loop)

            status, reason = handler.process(SimpleNamespace(data={"sessionWebhook": "present"}))

            assert (status, reason) == ("OK", "OK")
            from_dict.assert_called_once_with({"sessionWebhook": "present"})
            adapter._on_message.assert_awaited_once_with(converted)
        finally:
            self._stop_background_loop(loop, thread)

    def test_process_keeps_preconverted_message(self, monkeypatch):
        from gateway.platforms import dingtalk
        from gateway.platforms.dingtalk import DingTalkAdapter, _IncomingHandler

        fake_stream = SimpleNamespace(AckMessage=SimpleNamespace(STATUS_OK="OK"))
        from_dict = MagicMock()
        message = SimpleNamespace(session_webhook="https://api.dingtalk.com/webhook")

        monkeypatch.setattr(dingtalk, "dingtalk_stream", fake_stream)
        monkeypatch.setattr(
            dingtalk,
            "ChatbotMessage",
            SimpleNamespace(from_dict=from_dict),
            raising=False,
        )

        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter._on_message = AsyncMock()
        loop, thread = self._start_background_loop()
        try:
            handler = _IncomingHandler(adapter, loop)

            status, reason = handler.process(message)

            assert (status, reason) == ("OK", "OK")
            from_dict.assert_not_called()
            adapter._on_message.assert_awaited_once_with(message)
        finally:
            self._stop_background_loop(loop, thread)

    @pytest.mark.asyncio
    async def test_process_caches_session_webhook_for_followup_replies(self, monkeypatch):
        from gateway.platforms import dingtalk
        from gateway.platforms.dingtalk import DingTalkAdapter, _IncomingHandler

        fake_stream = SimpleNamespace(AckMessage=SimpleNamespace(STATUS_OK="OK"))
        webhook = "https://api.dingtalk.com/v1.0/gateway/conversations/sessions"
        payload = {
            "message_id": "msg-1",
            "text": {"content": "hello"},
            "conversation_id": "chat-123",
            "conversation_type": "1",
            "sender_id": "user-1",
            "sender_nick": "Tester",
            "sender_staff_id": "",
            "conversation_title": "DM",
            "create_at": "1710000000000",
            "session_webhook": webhook,
        }
        converted = SimpleNamespace(**payload)

        monkeypatch.setattr(dingtalk, "dingtalk_stream", fake_stream)
        monkeypatch.setattr(
            dingtalk,
            "ChatbotMessage",
            SimpleNamespace(from_dict=MagicMock(return_value=converted)),
            raising=False,
        )

        adapter = DingTalkAdapter(PlatformConfig(enabled=True))
        adapter.handle_message = AsyncMock()
        adapter._http_client = AsyncMock()
        adapter._http_client.post = AsyncMock(return_value=SimpleNamespace(status_code=200))
        loop, thread = self._start_background_loop()
        try:
            handler = _IncomingHandler(adapter, loop)

            status, reason = handler.process(SimpleNamespace(data=payload))

            assert (status, reason) == ("OK", "OK")
            assert adapter._session_webhooks["chat-123"] == webhook

            result = await adapter.send("chat-123", "Follow-up")

            assert result.success is True
            assert adapter._http_client.post.call_args[0][0] == webhook
        finally:
            self._stop_background_loop(loop, thread)


# ---------------------------------------------------------------------------
# Platform enum
# ---------------------------------------------------------------------------


class TestPlatformEnum:

    def test_dingtalk_in_platform_enum(self):
        assert Platform.DINGTALK.value == "dingtalk"
