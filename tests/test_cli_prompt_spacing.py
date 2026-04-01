"""Regression tests for CLI prompt spacing after foreground responses."""

from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj._agent_running = True
    cli_obj._spinner_text = "thinking"
    cli_obj._app = None
    return cli_obj


def test_finish_agent_turn_refreshes_status_without_printing_blank_padding():
    """Foreground turn cleanup should not emit spacer newlines."""
    cli_obj = _make_cli()
    cli_obj._app = MagicMock()

    with patch("cli._cprint") as mock_cprint:
        cli_obj._finish_agent_turn()

    assert cli_obj._agent_running is False
    assert cli_obj._spinner_text == ""
    cli_obj._app.invalidate.assert_called_once_with()
    mock_cprint.assert_not_called()


def test_finish_agent_turn_skips_invalidate_when_no_tui_app():
    """Non-TUI callers can reuse the cleanup helper safely."""
    cli_obj = _make_cli()

    with patch("cli._cprint") as mock_cprint:
        cli_obj._finish_agent_turn()

    assert cli_obj._agent_running is False
    assert cli_obj._spinner_text == ""
    mock_cprint.assert_not_called()
