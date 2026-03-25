"""Tests for mem0_integration/cli.py — Mem0 CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mem0_integration.cli import (
    cmd_status,
    cmd_search,
    cmd_memories,
)


class TestCmdStatus:
    def test_shows_config_when_enabled(self, tmp_path, capsys):
        config_file = tmp_path / "mem0.json"
        config_file.write_text(json.dumps({
            "apiKey": "m0-test-key-12345",
            "hosts": {"hermes": {"enabled": True, "userId": "kartik"}}
        }))
        with patch("mem0_integration.cli._read_config_path", return_value=config_file):
            with patch("mem0_integration.cli.get_mem0_client"):
                cmd_status(MagicMock())
        output = capsys.readouterr().out
        assert "Enabled" in output
        assert "kartik" in output

    def test_shows_not_configured(self, tmp_path, capsys):
        missing = tmp_path / "nonexistent.json"
        with patch("mem0_integration.cli._read_config_path", return_value=missing):
            cmd_status(MagicMock())
        output = capsys.readouterr().out
        assert "not configured" in output.lower() or "Run" in output


class TestCmdSearch:
    def test_search_displays_results(self, capsys):
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {"memory": "Likes Python", "score": 0.9, "categories": ["tech"]},
            ]
        }
        args = MagicMock()
        args.query = "programming"
        with patch("mem0_integration.cli._get_client_and_config") as mock_get:
            mock_get.return_value = (mock_client, MagicMock(user_id="testuser", keyword_search=True))
            cmd_search(args)
        output = capsys.readouterr().out
        assert "Likes Python" in output


class TestCmdMemories:
    def test_lists_memories(self, capsys):
        mock_client = MagicMock()
        mock_client.get_all.return_value = {
            "results": [
                {"id": "m1", "memory": "Likes Python", "categories": ["tech"]},
            ]
        }
        args = MagicMock()
        with patch("mem0_integration.cli._get_client_and_config") as mock_get:
            mock_get.return_value = (mock_client, MagicMock(user_id="testuser"))
            cmd_memories(args)
        output = capsys.readouterr().out
        assert "Likes Python" in output

    def test_empty_memories(self, capsys):
        mock_client = MagicMock()
        mock_client.get_all.return_value = {"results": []}
        args = MagicMock()
        with patch("mem0_integration.cli._get_client_and_config") as mock_get:
            mock_get.return_value = (mock_client, MagicMock(user_id="testuser"))
            cmd_memories(args)
        output = capsys.readouterr().out
        assert "No memories" in output
