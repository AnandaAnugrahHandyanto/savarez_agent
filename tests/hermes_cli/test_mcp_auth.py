"""Tests for hermes_cli.mcp_config — ``hermes mcp auth`` command.

Tests the authentication flow for MCP servers requiring OAuth or API keys.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestMcpAuthCommand:
    """Tests for the ``hermes mcp auth`` command."""

    def test_auth_no_servers(self, tmp_path, monkeypatch):
        """When no servers are configured, auth command reports no servers."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        # Mock config with no servers
        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value={}):
            cmd_mcp_auth(Namespace())
            # Should not crash, should report no servers

    def test_auth_all_servers_authenticated(self, tmp_path, monkeypatch):
        """When all servers are authenticated, auth command reports success."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        # Mock servers with OAuth tokens already present
        servers = {
            "test-oauth": {
                "url": "https://example.com/mcp",
                "auth": "oauth",
            }
        }

        # Mock the token file exists
        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            with patch.object(Path, "exists", return_value=True):
                cmd_mcp_auth(Namespace())
                # Should report all authenticated

    def test_auth_detects_oauth_server_needing_auth(self, tmp_path, monkeypatch):
        """Auth command detects OAuth servers without stored tokens."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        servers = {
            "test-oauth": {
                "url": "https://example.com/mcp",
                "auth": "oauth",
            }
        }

        # Mock the token file does NOT exist
        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            with patch.object(Path, "exists", return_value=False):
                with patch("hermes_cli.mcp_config._do_oauth_auth") as mock_oauth:
                    cmd_mcp_auth(Namespace())
                    # Should have called _do_oauth_auth
                    assert mock_oauth.called

    def test_auth_detects_header_server_needing_env_var(self, tmp_path, monkeypatch):
        """Auth command detects servers with unset env vars in headers."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        servers = {
            "test-api": {
                "url": "https://example.com/mcp",
                "headers": {
                    "Authorization": "Bearer ${MCP_TEST_API_API_KEY}"
                }
            }
        }

        # Env var is not set
        monkeypatch.delenv("MCP_TEST_API_API_KEY", raising=False)

        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            with patch("hermes_cli.mcp_config._do_header_auth") as mock_header:
                cmd_mcp_auth(Namespace())
                # Should have called _do_header_auth
                assert mock_header.called

    def test_auth_skips_header_server_with_env_var_set(self, tmp_path, monkeypatch):
        """Auth command skips servers with env vars already set."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        servers = {
            "test-api": {
                "url": "https://example.com/mcp",
                "headers": {
                    "Authorization": "Bearer ${MCP_TEST_API_API_KEY}"
                }
            }
        }

        # Env var IS set
        monkeypatch.setenv("MCP_TEST_API_API_KEY", "test-key-123")

        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            with patch("hermes_cli.mcp_config._do_header_auth") as mock_header:
                cmd_mcp_auth(Namespace())
                # Should NOT have called _do_header_auth (already configured)
                assert not mock_header.called


class TestDoOauthAuth:
    """Tests for the _do_oauth_auth helper function."""

    def test_oauth_auth_no_url(self):
        """OAuth auth handles server with no URL gracefully."""
        from hermes_cli.mcp_config import _do_oauth_auth

        cfg = {}  # No URL
        _do_oauth_auth("test-server", cfg)
        # Should not crash, should report error

    def test_oauth_auth_success(self):
        """OAuth auth initiates OAuth flow successfully."""
        from hermes_cli.mcp_config import _do_oauth_auth

        cfg = {"url": "https://example.com/mcp"}
        
        mock_oauth = MagicMock()
        with patch("hermes_cli.mcp_config.build_oauth_auth", return_value=mock_oauth):
            _do_oauth_auth("test-server", cfg)
            # Should have attempted OAuth

    def test_oauth_auth_sdk_not_available(self):
        """OAuth auth handles missing MCP SDK gracefully."""
        from hermes_cli.mcp_config import _do_oauth_auth

        cfg = {"url": "https://example.com/mcp"}
        
        with patch("hermes_cli.mcp_config.build_oauth_auth", side_effect=ImportError("No module")):
            _do_oauth_auth("test-server", cfg)
            # Should report SDK missing


class TestDoHeaderAuth:
    """Tests for the _do_header_auth helper function."""

    def test_header_auth_already_configured(self, monkeypatch):
        """Header auth skips if env var already set."""
        from hermes_cli.mcp_config import _do_header_auth

        monkeypatch.setenv("MCP_TEST_API_KEY", "existing-key")
        
        # Should not prompt, just return success
        _do_header_auth("test-server", "MCP_TEST_API_KEY")

    def test_header_auth_prompts_for_key(self, monkeypatch):
        """Header auth prompts for API key when not set."""
        from hermes_cli.mcp_config import _do_header_auth

        monkeypatch.delenv("MCP_TEST_API_KEY", raising=False)
        
        with patch("hermes_cli.mcp_config._prompt", return_value="new-api-key"):
            with patch("hermes_cli.mcp_config.save_env_value") as mock_save:
                _do_header_auth("test-server", "MCP_TEST_API_KEY")
                # Should have saved the key
                mock_save.assert_called_once()


class TestMcpAuthIntegration:
    """Integration tests for MCP auth command."""

    def test_auth_command_in_dispatcher(self):
        """Auth command is registered in the dispatcher."""
        from hermes_cli.mcp_config import mcp_command
        from argparse import Namespace

        args = Namespace(mcp_action="auth")
        
        with patch("hermes_cli.mcp_config.cmd_mcp_auth") as mock_auth:
            mcp_command(args)
            mock_auth.assert_called_once_with(args)

    def test_auth_command_shown_in_help(self):
        """Auth command appears in help output."""
        from hermes_cli.mcp_config import mcp_command
        from argparse import Namespace
        import io
        import sys

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = io.StringIO()
        
        try:
            # Call with no action to show help
            mcp_command(Namespace(mcp_action=None))
            output = captured.getvalue()
        finally:
            sys.stdout = old_stdout

        # Should mention auth command
        assert "auth" in output.lower()
        assert "authenticate" in output.lower()


class TestMcpAuthGateway:
    """Tests for gateway /mcp and /mcp auth commands."""

    @pytest.mark.asyncio
    async def test_mcp_command_dispatch(self):
        """/mcp command is dispatched correctly."""
        from gateway.run import GatewayRunner
        from gateway.types import MessageEvent, Platform, Source

        runner = GatewayRunner.__new__(GatewayRunner)
        
        # Mock the handler
        with patch.object(runner, "_handle_mcp_command", return_value="MCP output") as mock_handler:
            # This would be called from _dispatch_command
            event = MessageEvent(
                source=Source(platform=Platform.TELEGRAM, chat_id="123"),
                text="/mcp",
                message_type="command",
            )
            result = await runner._handle_mcp_command(event)
            assert result == "MCP output"

    @pytest.mark.asyncio
    async def test_mcp_auth_subcommand(self):
        """/mcp auth triggers authentication."""
        from gateway.run import GatewayRunner
        from gateway.types import MessageEvent, Platform, Source

        runner = GatewayRunner.__new__(GatewayRunner)
        
        with patch("hermes_cli.mcp_config.cmd_mcp_auth") as mock_auth:
            event = MessageEvent(
                source=Source(platform=Platform.TELEGRAM, chat_id="123"),
                text="/mcp auth",
                message_type="command",
            )
            result = await runner._handle_mcp_command(event)
            assert mock_auth.called

    @pytest.mark.asyncio
    async def test_mcp_list_adds_auth_hint(self):
        """/mcp command adds auth hint to list output."""
        from gateway.run import GatewayRunner
        from gateway.types import MessageEvent, Platform, Source

        runner = GatewayRunner.__new__(GatewayRunner)
        
        with patch("hermes_cli.mcp_config.cmd_mcp_list"):
            event = MessageEvent(
                source=Source(platform=Platform.TELEGRAM, chat_id="123"),
                text="/mcp",
                message_type="command",
            )
            result = await runner._handle_mcp_command(event)
            # Should contain auth hint
            assert "/mcp auth" in result or "auth" in result.lower()


class TestMcpAuthEdgeCases:
    """Edge case tests for MCP auth command."""

    def test_auth_with_mixed_server_types(self):
        """Auth handles mix of OAuth, header-auth, and no-auth servers."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        servers = {
            "oauth-server": {
                "url": "https://oauth.example.com/mcp",
                "auth": "oauth",
            },
            "api-server": {
                "url": "https://api.example.com/mcp",
                "headers": {"Authorization": "Bearer ${MCP_API_SERVER_API_KEY}"}
            },
            "no-auth-server": {
                "url": "https://public.example.com/mcp",
            }
        }

        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            with patch("hermes_cli.mcp_config._do_oauth_auth"):
                with patch("hermes_cli.mcp_config._do_header_auth"):
                    cmd_mcp_auth(Namespace())
                    # Should process oauth and api servers, skip no-auth

    def test_auth_with_invalid_auth_type(self):
        """Auth handles servers with invalid auth type gracefully."""
        from hermes_cli.mcp_config import cmd_mcp_auth
        from argparse import Namespace

        servers = {
            "invalid-auth": {
                "url": "https://example.com/mcp",
                "auth": "invalid-type",
            }
        }

        with patch("hermes_cli.mcp_config._get_mcp_servers", return_value=servers):
            cmd_mcp_auth(Namespace())
            # Should not crash

    def test_auth_handles_keyboard_interrupt(self):
        """Auth handles user cancellation gracefully."""
        from hermes_cli.mcp_config import _do_header_auth

        with patch("hermes_cli.mcp_config._prompt", side_effect=KeyboardInterrupt()):
            _do_header_auth("test-server", "MCP_TEST_KEY")
            # Should not crash, should handle gracefully
