"""Tests for /sessions slash command in classic CLI mode (fixes #22951).

Before fix: process_command('/sessions') fell through to 'Unknown command'.
After fix: delegates to _show_recent_sessions(), printing a session list.
"""
from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli() -> HermesCLI:
    cli = HermesCLI.__new__(HermesCLI)
    cli.config = {}
    cli.console = MagicMock()
    cli.agent = None
    cli.conversation_history = []
    cli.session_id = "sess-test"
    cli._pending_input = MagicMock()
    cli._app = None
    cli._session_db = None
    cli._agent_running = False
    return cli


def test_sessions_command_calls_show_recent_sessions():
    """/sessions must call _show_recent_sessions, not fall to 'Unknown command'."""
    cli = _make_cli()
    called_with = {}

    def fake_show_recent(reason="history", limit=10):
        called_with["reason"] = reason
        return True

    with patch.object(cli, "_show_recent_sessions", side_effect=fake_show_recent):
        cli.process_command("/sessions")

    assert "reason" in called_with, (
        "_show_recent_sessions was never called — /sessions still hits 'Unknown command' (#22951)"
    )
    assert called_with["reason"] == "sessions"


def test_sessions_command_no_sessions_shows_fallback(capsys):
    """/sessions with no sessions should print a friendly message."""
    cli = _make_cli()

    with patch.object(cli, "_show_recent_sessions", return_value=False):
        cli.process_command("/sessions")

    captured = capsys.readouterr()
    assert "No previous sessions" in captured.out
