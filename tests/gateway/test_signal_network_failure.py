"""Tests for Signal error embedding and retry behavior via base.py patterns."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_signal_adapter(monkeypatch, account="+155****4567", **extra):
    """Create a SignalAdapter with sensible test defaults."""
    monkeypatch.setenv("SIGNAL_GROUP_ALLOWED_USERS", extra.pop("group_allowed", ""))
    from gateway.config import PlatformConfig
    from gateway.platforms.signal import SignalAdapter

    config = PlatformConfig()
    config.enabled = True
    config.extra = {
        "http_url": "http://localhost:8080",
        "account": account,
        **extra,
    }
    return SignalAdapter(config)


# ---------------------------------------------------------------------------
# _rpc_error_str helper
# ---------------------------------------------------------------------------


class TestRpcErrorStr:
    """Verify the static helper embeds error data for base.py pattern matching."""

    def test_embeds_dict_error(self):
        from gateway.platforms.signal import SignalAdapter

        error_data = {
            "code": -1,
            "message": "Failed to send message",
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }
        result = SignalAdapter._rpc_error_str(error_data, "RPC send failed")

        assert "RPC send failed" in result
        assert "NETWORK_FAILURE" in result
        # Verify base.py patterns catch it
        assert "network" in result.lower()  # matches _RETRYABLE_ERROR_PATTERNS

    def test_embeds_string_error(self):
        from gateway.platforms.signal import SignalAdapter

        error_data = "ReadTimeout(request URL='POST http://...')"
        result = SignalAdapter._rpc_error_str(error_data, "RPC send failed")

        assert "RPC send failed" in result
        assert "ReadTimeout" in result
        # Verify base.py timeout detection catches it
        assert "readtimeout" in result.lower()  # matches _is_timeout_error

    def test_returns_fallback_when_none(self):
        from gateway.platforms.signal import SignalAdapter

        result = SignalAdapter._rpc_error_str(None, "RPC send failed")
        assert result == "RPC send failed"
        # No retryable patterns should match the bare fallback
        assert "network" not in result.lower()


# ---------------------------------------------------------------------------
# _rpc() returns (result, error_data) tuple
# ---------------------------------------------------------------------------


class TestRpcReturnsTuple:
    """Verify _rpc() returns a two-element tuple for all code paths."""

    @pytest.mark.asyncio
    async def test_rpc_returns_none_none_when_no_client(self, monkeypatch):
        adapter = _make_signal_adapter(monkeypatch)
        # client is None by default in tests
        result, error_data = await adapter._rpc("test", {})
        assert result is None
        assert error_data is None

    @pytest.mark.asyncio
    async def test_rpc_returns_result_none_on_success(self, monkeypatch):
        adapter = _make_signal_adapter(monkeypatch)
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"timestamp": 123}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        adapter.client = mock_client

        result, error_data = await adapter._rpc("test", {})
        assert result == {"timestamp": 123}
        assert error_data is None

    @pytest.mark.asyncio
    async def test_rpc_returns_none_error_on_rpc_error(self, monkeypatch):
        adapter = _make_signal_adapter(monkeypatch)
        network_error_data = {
            "code": -1,
            "message": "Failed to send message",
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"error": network_error_data}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        adapter.client = mock_client

        result, error_data = await adapter._rpc("send", {})
        assert result is None
        assert error_data == network_error_data

    @pytest.mark.asyncio
    async def test_rpc_returns_none_str_on_exception(self, monkeypatch):
        adapter = _make_signal_adapter(monkeypatch)

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("ReadTimeout")
        adapter.client = mock_client

        result, error_data = await adapter._rpc("send", {})
        assert result is None
        assert isinstance(error_data, str)
        assert "ReadTimeout" in error_data


# ---------------------------------------------------------------------------
# send() embeds error data for base.py retry detection
# ---------------------------------------------------------------------------


class TestSendEmbedsErrorData:
    """Verify that send() returns SendResult with error data embedded for pattern matching."""

    @pytest.mark.asyncio
    async def test_send_error_contains_network_failure_for_retry(self, monkeypatch):
        """When _rpc returns NETWORK_FAILURE error data, send() should embed it
        so base.py's _is_retryable_error pattern matches 'network' and retries."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        network_error_data = {
            "code": -1,
            "message": "Failed to send message",
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        async def mock_rpc(method, params, **kwargs):
            return None, network_error_data

        adapter._rpc = mock_rpc

        result = await adapter.send(chat_id="+155****4567", content="hello")

        assert result.success is False
        # Error string should contain the NETWORK_FAILURE data
        assert "NETWORK_FAILURE" in result.error
        # base.py _is_retryable_error catches it via 'network' pattern
        from gateway.platforms.base import _RETRYABLE_ERROR_PATTERNS
        assert any(p in result.error.lower() for p in _RETRYABLE_ERROR_PATTERNS)

    @pytest.mark.asyncio
    async def test_send_non_network_error_no_retry(self, monkeypatch):
        """Non-network errors should not match retryable patterns."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        other_error_data = {
            "code": -1,
            "message": "Invalid recipient",
            "data": {"response": {"results": [{"type": "UNKNOWN_USER"}]}},
        }

        async def mock_rpc(method, params, **kwargs):
            return None, other_error_data

        adapter._rpc = mock_rpc

        result = await adapter.send(chat_id="+155****4567", content="hello")

        assert result.success is False
        # Should not match retryable patterns
        from gateway.platforms.base import _RETRYABLE_ERROR_PATTERNS
        has_retry_pattern = any(p in result.error.lower() for p in _RETRYABLE_ERROR_PATTERNS)
        # UNKNOWN_USER doesn't contain 'network', 'connecterror', etc.
        assert not has_retry_pattern

    @pytest.mark.asyncio
    async def test_send_no_error_data_returns_fallback(self, monkeypatch):
        """When _rpc returns None error data (httpx exception), fallback is used."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        async def mock_rpc(method, params, **kwargs):
            return None, "ReadTimeout(request URL='...')"

        adapter._rpc = mock_rpc

        result = await adapter.send(chat_id="+155****4567", content="hello")

        assert result.success is False
        assert "RPC send failed" in result.error
        assert "ReadTimeout" in result.error
        # base.py _is_timeout_error catches it via 'readtimeout' pattern
        from gateway.platforms.base import BasePlatformAdapter
        assert BasePlatformAdapter._is_timeout_error(result.error)

    @pytest.mark.asyncio
    async def test_send_success_ignores_error(self, monkeypatch):
        """Successful sends work normally."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        async def mock_rpc(method, params, **kwargs):
            return {"timestamp": 1234567890}, None

        adapter._rpc = mock_rpc

        result = await adapter.send(chat_id="+155****4567", content="hello")

        assert result.success is True
        assert result.message_id == "1234567890"


# ---------------------------------------------------------------------------
# Attachment methods embed error data too
# ---------------------------------------------------------------------------


class TestSendAttachmentEmbedsErrorData:
    """Verify that attachment methods also embed error data for pattern matching."""

    @pytest.mark.asyncio
    async def test_send_document_embeds_error(self, monkeypatch, tmp_path):
        """send_document should embed RPC error in SendResult.error."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        doc_path = tmp_path / "report.pdf"
        doc_path.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        network_error_data = {
            "code": -1,
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        async def mock_rpc(method, params, **kwargs):
            return None, network_error_data

        adapter._rpc = mock_rpc

        result = await adapter.send_document(chat_id="+155****4567", file_path=str(doc_path))

        assert result.success is False
        assert "NETWORK_FAILURE" in result.error
        from gateway.platforms.base import _RETRYABLE_ERROR_PATTERNS
        assert any(p in result.error.lower() for p in _RETRYABLE_ERROR_PATTERNS)

    @pytest.mark.asyncio
    async def test_send_image_file_embeds_error(self, monkeypatch, tmp_path):
        """send_image_file should embed RPC error in SendResult.error."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        img_path = tmp_path / "chart.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        network_error_data = {
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        async def mock_rpc(method, params, **kwargs):
            return None, network_error_data

        adapter._rpc = mock_rpc

        result = await adapter.send_image_file(chat_id="+155****4567", image_path=str(img_path))

        assert result.success is False
        from gateway.platforms.base import _RETRYABLE_ERROR_PATTERNS
        assert any(p in result.error.lower() for p in _RETRYABLE_ERROR_PATTERNS)


# ---------------------------------------------------------------------------
# Integration: base.py _send_with_retry correctly handles Signal errors
# ---------------------------------------------------------------------------


class TestSendWithRetryIntegration:
    """Verify that _send_with_retry from base.py correctly retries Signal errors."""

    @pytest.mark.asyncio
    async def test_send_with_retry_retries_network_failure(self, monkeypatch):
        """_send_with_retry should retry when send() error contains 'network' pattern."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        network_error_data = {
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        attempt_count = 0

        async def mock_rpc(method, params, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            # First two attempts fail with NETWORK_FAILURE, third succeeds
            if attempt_count <= 2:
                return None, network_error_data
            return {"timestamp": 999}, None

        adapter._rpc = mock_rpc

        result = await adapter._send_with_retry(
            chat_id="+155****4567", content="hello", max_retries=3, base_delay=0.01,
        )

        assert result.success is True
        assert attempt_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_send_with_retry_exhausted(self, monkeypatch):
        """_send_with_retry gives up after max_retries on persistent failures."""
        adapter = _make_signal_adapter(monkeypatch)
        adapter._stop_typing_indicator = AsyncMock()

        network_error_data = {
            "data": {"response": {"results": [{"type": "NETWORK_FAILURE"}]}},
        }

        attempt_count = 0

        async def mock_rpc(method, params, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            return None, network_error_data

        adapter._rpc = mock_rpc

        result = await adapter._send_with_retry(
            chat_id="+155****4567", content="hello", max_retries=2, base_delay=0.01,
        )

        assert result.success is False
        # 1 initial + 2 retries + 1 delivery-failure notice send = 4 total sends
        assert attempt_count == 4
