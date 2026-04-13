"""Tests for the standalone ``hermes server`` command (hermes_cli/api_server.py).

Tests cover:
- server_command dispatches to run_api_server with correct args
- run_api_server exits when aiohttp is missing
- PlatformConfig construction from CLI flags / env vars
- _run_adapter lifecycle (connect failure → exit)
"""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# server_command — dispatches args correctly
# ---------------------------------------------------------------------------


class TestServerCommand:
    """Test that server_command passes args through to run_api_server."""

    @patch("hermes_cli.api_server.run_api_server")
    def test_dispatches_default_args(self, mock_run):
        from hermes_cli.api_server import server_command
        args = SimpleNamespace(
            host="127.0.0.1",
            port=8642,
            key="",
            cors_origins="",
            model_name="",
            verbose=0,
            quiet=False,
        )
        server_command(args)
        mock_run.assert_called_once_with(
            host="127.0.0.1",
            port=8642,
            key="",
            cors_origins="",
            model_name="",
            verbose=0,
            quiet=False,
        )

    @patch("hermes_cli.api_server.run_api_server")
    def test_dispatches_custom_args(self, mock_run):
        from hermes_cli.api_server import server_command
        args = SimpleNamespace(
            host="0.0.0.0",
            port=9000,
            key="sk-test-key",
            cors_origins="http://localhost:3000",
            model_name="my-agent",
            verbose=2,
            quiet=False,
        )
        server_command(args)
        mock_run.assert_called_once_with(
            host="0.0.0.0",
            port=9000,
            key="sk-test-key",
            cors_origins="http://localhost:3000",
            model_name="my-agent",
            verbose=2,
            quiet=False,
        )

    @patch("hermes_cli.api_server.run_api_server")
    def test_handles_missing_attrs_gracefully(self, mock_run):
        """Attributes missing from args should fall back to defaults."""
        from hermes_cli.api_server import server_command
        args = SimpleNamespace()  # no attributes at all
        server_command(args)
        mock_run.assert_called_once_with(
            host="127.0.0.1",
            port=8642,
            key="",
            cors_origins="",
            model_name="",
            verbose=0,
            quiet=False,
        )


# ---------------------------------------------------------------------------
# run_api_server — pre-flight checks
# ---------------------------------------------------------------------------


class TestRunApiServerChecks:
    """Test pre-flight checks in run_api_server.

    These rely on the conftest's _isolate_hermes_home autouse fixture which
    sets HERMES_HOME to a temp directory, so real get_hermes_home() works.
    """

    def test_exits_when_aiohttp_missing(self):
        """run_api_server should sys.exit(1) if aiohttp is not available."""
        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", False
        ):
            from hermes_cli.api_server import run_api_server
            with pytest.raises(SystemExit) as exc_info:
                run_api_server(quiet=True)
            assert exc_info.value.code == 1

    def test_platform_config_includes_key_from_flag(self):
        """--key flag should appear in the PlatformConfig extra."""
        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", True
        ):
            with patch("gateway.config.PlatformConfig") as mock_pc:
                mock_pc.return_value = MagicMock()
                with patch("asyncio.run", side_effect=lambda c: c.close()):
                    from hermes_cli.api_server import run_api_server
                    run_api_server(
                        host="0.0.0.0", port=9000, key="sk-test", quiet=True,
                    )
                    _, kwargs = mock_pc.call_args
                    assert kwargs["extra"]["key"] == "sk-test"
                    assert kwargs["extra"]["host"] == "0.0.0.0"
                    assert kwargs["extra"]["port"] == 9000

    def test_env_var_fallback_for_key(self, monkeypatch):
        """API_SERVER_KEY env var should be used when --key is empty."""
        monkeypatch.setenv("API_SERVER_KEY", "env-key-123")

        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", True
        ):
            with patch("gateway.config.PlatformConfig") as mock_pc:
                mock_pc.return_value = MagicMock()
                with patch("asyncio.run", side_effect=lambda c: c.close()):
                    from hermes_cli.api_server import run_api_server
                    run_api_server(key="", quiet=True)
                    _, kwargs = mock_pc.call_args
                    assert kwargs["extra"]["key"] == "env-key-123"

    def test_no_key_in_extra_when_empty(self, monkeypatch):
        """When no key is provided and env is empty, 'key' should not be in extra."""
        monkeypatch.delenv("API_SERVER_KEY", raising=False)

        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", True
        ):
            with patch("gateway.config.PlatformConfig") as mock_pc:
                mock_pc.return_value = MagicMock()
                with patch("asyncio.run", side_effect=lambda c: c.close()):
                    from hermes_cli.api_server import run_api_server
                    run_api_server(key="", quiet=True)
                    _, kwargs = mock_pc.call_args
                    assert "key" not in kwargs["extra"]

    def test_cors_origins_in_extra_when_provided(self):
        """--cors-origins should appear in extra when non-empty."""
        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", True
        ):
            with patch("gateway.config.PlatformConfig") as mock_pc:
                mock_pc.return_value = MagicMock()
                with patch("asyncio.run", side_effect=lambda c: c.close()):
                    from hermes_cli.api_server import run_api_server
                    run_api_server(
                        cors_origins="http://localhost:3000,http://example.com",
                        quiet=True,
                    )
                    _, kwargs = mock_pc.call_args
                    assert kwargs["extra"]["cors_origins"] == "http://localhost:3000,http://example.com"

    def test_model_name_in_extra_when_provided(self):
        """--model-name should appear in extra when non-empty."""
        with patch(
            "gateway.platforms.api_server.AIOHTTP_AVAILABLE", True
        ):
            with patch("gateway.config.PlatformConfig") as mock_pc:
                mock_pc.return_value = MagicMock()
                with patch("asyncio.run", side_effect=lambda c: c.close()):
                    from hermes_cli.api_server import run_api_server
                    run_api_server(model_name="my-custom-agent", quiet=True)
                    _, kwargs = mock_pc.call_args
                    assert kwargs["extra"]["model_name"] == "my-custom-agent"


# ---------------------------------------------------------------------------
# _run_adapter — lifecycle
# ---------------------------------------------------------------------------


class TestRunAdapter:
    """Test the async adapter lifecycle."""

    @pytest.mark.asyncio
    async def test_exits_on_connect_failure(self):
        """_run_adapter should sys.exit(1) if adapter.connect() returns False."""
        from hermes_cli.api_server import _run_adapter

        mock_adapter = AsyncMock()
        mock_adapter.connect = AsyncMock(return_value=False)

        with patch("gateway.platforms.api_server.APIServerAdapter", return_value=mock_adapter):
            with pytest.raises(SystemExit) as exc_info:
                await _run_adapter(MagicMock())
            assert exc_info.value.code == 1
