"""Tests for QQBot send_message functionality.

Tests the chat type detection logic added to _send_qqbot:
- Numeric chat_id → guild channel endpoint
- 32-char hex OpenID → C2C endpoint (fallback to group)
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from tools.send_message_tool import (
    _QQBOT_TARGET_RE,
    _parse_target_ref,
)


class TestQQBotTargetRegex:
    """Test the QQBot OpenID regex pattern."""

    def test_valid_32_char_hex_uppercase(self):
        """Valid 32-char uppercase hex should match."""
        match = _QQBOT_TARGET_RE.fullmatch("3E9A53DBB44E52DD0B7DAB6F37B4FE97")
        assert match is not None
        assert match.group(1) == "3E9A53DBB44E52DD0B7DAB6F37B4FE97"

    def test_valid_32_char_hex_with_whitespace(self):
        """Valid OpenID with leading/trailing whitespace should match."""
        match = _QQBOT_TARGET_RE.fullmatch("  3E9A53DBB44E52DD0B7DAB6F37B4FE97  ")
        assert match is not None
        assert match.group(1) == "3E9A53DBB44E52DD0B7DAB6F37B4FE97"

    def test_lowercase_hex_does_not_match(self):
        """Lowercase hex should NOT match (QQBot uses uppercase)."""
        match = _QQBOT_TARGET_RE.fullmatch("3e9a53dbb44e52dd0b7dab6f37b4fe97")
        assert match is None

    def test_too_short_does_not_match(self):
        """31-char string should not match."""
        match = _QQBOT_TARGET_RE.fullmatch("3E9A53DBB44E52DD0B7DAB6F37B4FE9")
        assert match is None

    def test_too_long_does_not_match(self):
        """33-char string should not match."""
        match = _QQBOT_TARGET_RE.fullmatch("3E9A53DBB44E52DD0B7DAB6F37B4FE97A")
        assert match is None

    def test_numeric_does_not_match(self):
        """Pure numeric (guild channel ID) should not match."""
        match = _QQBOT_TARGET_RE.fullmatch("1234567890")
        assert match is None

    def test_mixed_case_does_not_match(self):
        """Mixed case should not match."""
        match = _QQBOT_TARGET_RE.fullmatch("3E9a53DBB44E52DD0B7DAB6F37B4FE97")
        assert match is None


class TestParseTargetRefQQBot:
    """Test _parse_target_ref for QQBot platform."""

    def test_parse_qqbot_openid(self):
        """QQBot OpenID should be recognized as explicit."""
        chat_id, thread_id, is_explicit = _parse_target_ref(
            "qqbot", "3E9A53DBB44E52DD0B7DAB6F37B4FE97"
        )
        assert chat_id == "3E9A53DBB44E52DD0B7DAB6F37B4FE97"
        assert thread_id is None
        assert is_explicit is True

    def test_parse_qqbot_numeric_falls_through(self):
        """QQBot numeric ID should fall through to generic numeric handling."""
        chat_id, thread_id, is_explicit = _parse_target_ref("qqbot", "1234567890")
        # Falls through to the generic numeric check
        assert chat_id == "1234567890"
        assert thread_id is None
        assert is_explicit is True

    def test_parse_qqbot_invalid_format_not_explicit(self):
        """Invalid QQBot format should return not explicit."""
        chat_id, thread_id, is_explicit = _parse_target_ref("qqbot", "invalid-id")
        assert chat_id is None
        assert thread_id is None
        assert is_explicit is False


class TestSendQQBotEndpoints:
    """Test _send_qqbot endpoint selection logic.

    Uses integration-style testing by mocking the httpx module in sys.modules
    since httpx is imported dynamically inside the function.
    """

    def _setup_httpx_mock(self, mock_responses):
        """Create a mock httpx module with AsyncClient that returns mock responses."""
        mock_httpx = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=mock_responses)

        mock_httpx.AsyncClient.return_value = mock_client
        return mock_httpx, mock_client

    def _make_pconfig(self):
        """Create a mock platform config for QQBot."""
        return MagicMock(
            extra={
                "app_id": "test_app_id",
                "client_secret": "test_client_secret",
            }
        )

    @pytest.mark.asyncio
    async def test_guild_channel_uses_channels_endpoint(self):
        """Numeric chat_id should use guild channel endpoint."""
        from tools.send_message_tool import _send_qqbot

        pconfig = self._make_pconfig()

        mock_responses = [
            # Token response
            MagicMock(
                status_code=200,
                json=lambda: {"access_token": "test_token"}
            ),
            # Guild channel message response
            MagicMock(
                status_code=200,
                json=lambda: {"id": "msg_123"}
            ),
        ]

        mock_httpx, mock_client = self._setup_httpx_mock(mock_responses)

        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = await _send_qqbot(pconfig, "1234567890", "test message")

        assert result["success"] is True
        assert result["chat_type"] == "guild"
        # Verify guild endpoint was used (second call, after token)
        call_args = mock_client.post.call_args_list[1]
        assert "/channels/1234567890/messages" in str(call_args)

    @pytest.mark.asyncio
    async def test_c2c_uses_users_endpoint(self):
        """32-char hex OpenID should use C2C endpoint."""
        from tools.send_message_tool import _send_qqbot

        pconfig = self._make_pconfig()

        mock_responses = [
            # Token response
            MagicMock(
                status_code=200,
                json=lambda: {"access_token": "test_token"}
            ),
            # C2C message response (success)
            MagicMock(
                status_code=200,
                json=lambda: {"id": "msg_c2c"}
            ),
        ]

        mock_httpx, mock_client = self._setup_httpx_mock(mock_responses)

        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = await _send_qqbot(
                pconfig, "3E9A53DBB44E52DD0B7DAB6F37B4FE97", "test message"
            )

        assert result["success"] is True
        assert result["chat_type"] == "c2c"
        # Verify C2C endpoint was used
        call_args = mock_client.post.call_args_list[1]
        assert "/v2/users/" in str(call_args)

    @pytest.mark.asyncio
    async def test_c2c_fallback_to_group(self):
        """Should fall back to group endpoint if C2C fails."""
        from tools.send_message_tool import _send_qqbot

        pconfig = self._make_pconfig()

        mock_responses = [
            # Token response
            MagicMock(
                status_code=200,
                json=lambda: {"access_token": "test_token"}
            ),
            # C2C response (failure - 404 means user not found)
            MagicMock(
                status_code=404,
                text="Not Found"
            ),
            # Group response (success)
            MagicMock(
                status_code=200,
                json=lambda: {"id": "msg_group"}
            ),
        ]

        mock_httpx, mock_client = self._setup_httpx_mock(mock_responses)

        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = await _send_qqbot(
                pconfig, "3E9A53DBB44E52DD0B7DAB6F37B4FE97", "test message"
            )

        assert result["success"] is True
        assert result["chat_type"] == "group"
        # Verify C2C was tried first
        c2c_call_args = mock_client.post.call_args_list[1]
        assert "/v2/users/" in str(c2c_call_args)
        # Verify group was tried second
        group_call_args = mock_client.post.call_args_list[2]
        assert "/v2/groups/" in str(group_call_args)

    @pytest.mark.asyncio
    async def test_unknown_format_returns_error(self):
        """Unknown chat_id format should return error without API calls."""
        from tools.send_message_tool import _send_qqbot

        pconfig = self._make_pconfig()

        # No mock responses needed - validation happens before API calls
        mock_httpx, mock_client = self._setup_httpx_mock([])

        with patch.dict(sys.modules, {"httpx": mock_httpx}):
            result = await _send_qqbot(pconfig, "invalid-format-123", "test message")

        assert "error" in result
        assert "unrecognized chat_id format" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_error(self):
        """Missing app_id or client_secret should return error."""
        from tools.send_message_tool import _send_qqbot

        pconfig = MagicMock(extra={})  # No credentials

        result = await _send_qqbot(pconfig, "1234567890", "test message")

        assert "error" in result
        assert "not configured" in result["error"]


class TestQQBotHomeChannelEnvVars:
    """Test that both QQ_HOME_CHANNEL and QQBOT_HOME_CHANNEL are recognized."""

    def test_qq_home_channel_fallback(self, monkeypatch):
        """Test that QQBOT_HOME_CHANNEL is used when QQ_HOME_CHANNEL is not set."""
        from gateway.config import load_gateway_config

        # Set up minimal credentials
        monkeypatch.setenv("QQ_APP_ID", "test_app_id")
        monkeypatch.setenv("QQ_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("QQBOT_HOME_CHANNEL", "3E9A53DBB44E52DD0B7DAB6F37B4FE97")
        # Make sure QQ_HOME_CHANNEL is not set
        monkeypatch.delenv("QQ_HOME_CHANNEL", raising=False)

        # Clear any cached config state
        monkeypatch.delenv("QQ_HOME_CHANNEL_NAME", raising=False)

        config = load_gateway_config()

        assert config.platforms.get(Platform.QQBOT) is not None
        home = config.get_home_channel(Platform.QQBOT)
        assert home is not None
        assert home.chat_id == "3E9A53DBB44E52DD0B7DAB6F37B4FE97"

    def test_qq_home_channel_preferred(self, monkeypatch):
        """Test that QQ_HOME_CHANNEL is preferred over QQBOT_HOME_CHANNEL."""
        from gateway.config import load_gateway_config

        monkeypatch.setenv("QQ_APP_ID", "test_app_id")
        monkeypatch.setenv("QQ_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("QQ_HOME_CHANNEL", "AAAAAAAABBBBBBBCCCCCCCCDDDDDDDD")
        monkeypatch.setenv("QQBOT_HOME_CHANNEL", "3E9A53DBB44E52DD0B7DAB6F37B4FE97")

        config = load_gateway_config()

        home = config.get_home_channel(Platform.QQBOT)
        assert home is not None
        # QQ_HOME_CHANNEL should be used first
        assert home.chat_id == "AAAAAAAABBBBBBBCCCCCCCCDDDDDDDD"
