"""Tests for rendering plugin startup advisories in the interactive CLI."""

from unittest.mock import MagicMock

from cli import HermesCLI


def test_cli_prints_plugin_startup_advisories_between_banner_and_welcome(monkeypatch, capsys):
    """Plugin advisories should have a visible startup slot before welcome text."""
    shell = HermesCLI.__new__(HermesCLI)
    manager = MagicMock()
    manager.get_startup_advisories.return_value = [
        "⚠ Update available: 0.3.8 → 0.3.10",
        "stale auth token",
    ]
    monkeypatch.setattr("hermes_cli.plugins.get_plugin_manager", lambda: manager)

    shell._show_plugin_startup_advisories()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "⚠ Update available: 0.3.8 → 0.3.10" in captured.err
    assert "stale auth token" in captured.err
