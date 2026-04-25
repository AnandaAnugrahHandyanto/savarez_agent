"""Tests for _update_mcp_packages — MCP server package update logic."""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from hermes_cli.main import _update_mcp_packages


class TestUpdateMcpPackages:
    """Tests for the MCP package update helper."""

    @patch("hermes_cli.main.subprocess.run")
    @patch("hermes_cli.main.load_config", create=True)
    def test_npx_packages_detected(self, mock_config, mock_run, capsys):
        """npx -y @scope/package is detected and npm update -g is called."""
        # Patch the lazy import inside _update_mcp_packages
        with patch("hermes_cli.config.load_config", return_value={
            "mcp_servers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
            }
        }):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="", stderr=""
            )
            _update_mcp_packages()

        captured = capsys.readouterr()
        assert "Updating MCP server packages" in captured.out

    @patch("hermes_cli.config.load_config", return_value={
        "mcp_servers": {
            "sqlite": {
                "command": "uvx",
                "args": ["mcp-server-sqlite", "--db", "test.db"],
            },
        }
    })
    @patch("hermes_cli.main.subprocess.run")
    def test_uvx_packages_detected(self, mock_run, mock_config, capsys):
        """uvx package is detected and uvx upgrade is called."""
        mock_run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="", stderr=""
        )
        _update_mcp_packages()

        captured = capsys.readouterr()
        assert "Updating MCP server packages" in captured.out

    @patch("hermes_cli.config.load_config", return_value={
        "mcp_servers": {
            "remote": {
                "url": "https://example.com/mcp",
            },
        }
    })
    def test_url_servers_skipped(self, mock_config, capsys):
        """URL-based (remote) MCP servers are skipped."""
        _update_mcp_packages()

        captured = capsys.readouterr()
        assert "No package-managed MCP servers found" in captured.out

    @patch("hermes_cli.config.load_config", return_value={"mcp_servers": {}})
    def test_no_servers(self, mock_config, capsys):
        """No MCP servers configured — early return."""
        _update_mcp_packages()

        captured = capsys.readouterr()
        assert "No MCP servers configured" in captured.out
