"""Tests for `/clear --then "<message>"` one-shot post-clear handoff.

Spec: /tmp/clear-then-spec.md (May 2026).  The handoff message is queued
into ``HermesCLI._pending_input`` after the /clear body finishes so the
process_loop dispatches it as the first user turn of the new session.
Consumed exactly once.  Default /clear (no --then) is unchanged.
"""

from __future__ import annotations

import queue
from unittest.mock import MagicMock, patch


def _make_cli():
    """Bare HermesCLI suitable for /clear process_command() tests.

    Uses ``__new__`` to skip the heavy __init__; only sets the attributes the
    /clear branch actually touches.  All UI side effects (banner, tip, screen
    clear, new_session bookkeeping) are stubbed to no-ops so the test focuses
    on argument parsing + the handoff queue push.
    """
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli.config = {}
    cli.console = MagicMock()
    cli._app = None  # take the non-TUI branch
    cli.agent = None
    cli.conversation_history = []
    cli.session_id = "old-session"
    cli.model = "test-model"
    cli.enabled_toolsets = []
    cli.compact = True  # avoids the heavy welcome banner branch
    cli._pending_input = queue.Queue()

    # Auto-approve the destructive prompt by default.
    cli._confirm_destructive_slash = MagicMock(return_value="once")

    # new_session rotates the session id; in real life it does much more.
    def _fake_new_session(silent=False, **_kw):
        cli.session_id = "new-session"
    cli.new_session = _fake_new_session

    # show_banner is the non-TUI fresh banner; stub it.
    cli.show_banner = MagicMock()
    cli._console_print = MagicMock()
    cli._force_full_redraw = MagicMock()
    return cli


def _run_clear(cli, command):
    """Invoke process_command(/clear ...) with side-effect functions stubbed."""
    with patch("cli._clear_output_history", lambda: None):
        return cli.process_command(command)


class TestClearDefault:
    def test_plain_clear_still_works(self):
        """Regression: /clear with no args clears + rotates session and does
        NOT queue anything to _pending_input."""
        cli = _make_cli()
        result = _run_clear(cli, "/clear")
        # process_command for /clear returns None (falls off the if/elif chain
        # with implicit return) — we only care that it didn't raise and the
        # queue stayed empty.
        assert result is None or result is True
        assert cli.session_id == "new-session"
        assert cli._pending_input.empty()


class TestClearThenHandoff:
    def test_then_queues_message_after_new_session(self):
        cli = _make_cli()
        _run_clear(cli, '/clear --then "do the thing"')
        # Message was queued exactly once.
        assert cli._pending_input.get_nowait() == "do the thing"
        assert cli._pending_input.empty()
        # Session rotated — handoff lands in the NEW session.
        assert cli.session_id == "new-session"

    def test_handoff_consumed_once_only(self):
        cli = _make_cli()
        _run_clear(cli, '/clear --then "hello"')
        assert cli._pending_input.get_nowait() == "hello"
        # Second peek returns nothing — message is one-shot.
        with __import__("pytest").raises(queue.Empty):
            cli._pending_input.get_nowait()

    def test_single_quoted_handoff(self):
        cli = _make_cli()
        _run_clear(cli, "/clear --then 'single quoted msg'")
        assert cli._pending_input.get_nowait() == "single quoted msg"

    def test_double_quoted_handoff(self):
        cli = _make_cli()
        _run_clear(cli, '/clear --then "double quoted msg"')
        assert cli._pending_input.get_nowait() == "double quoted msg"

    def test_internal_whitespace_preserved(self):
        cli = _make_cli()
        _run_clear(cli, '/clear --then "go run plan-phase 6"')
        assert cli._pending_input.get_nowait() == "go run plan-phase 6"

    def test_cancel_aborts_and_does_not_queue(self):
        """If the destructive confirm returns None (user cancelled), the
        clear is aborted and the handoff message is NOT queued."""
        cli = _make_cli()
        cli._confirm_destructive_slash = MagicMock(return_value=None)
        _run_clear(cli, '/clear --then "should not run"')
        assert cli.session_id == "old-session"  # not rotated
        assert cli._pending_input.empty()

    def test_empty_then_message_errors_and_no_clear(self):
        cli = _make_cli()
        result = _run_clear(cli, '/clear --then ""')
        assert result is True  # CLI keeps running
        # Did not call confirm or rotate session.
        cli._confirm_destructive_slash.assert_not_called()
        assert cli.session_id == "old-session"
        assert cli._pending_input.empty()

    def test_unknown_arg_errors_and_no_clear(self):
        cli = _make_cli()
        result = _run_clear(cli, "/clear --bogus foo")
        assert result is True
        cli._confirm_destructive_slash.assert_not_called()
        assert cli.session_id == "old-session"

    def test_unbalanced_quotes_errors_and_no_clear(self):
        cli = _make_cli()
        result = _run_clear(cli, '/clear --then "unclosed')
        assert result is True
        cli._confirm_destructive_slash.assert_not_called()
        assert cli.session_id == "old-session"


class TestCommandRegistry:
    def test_clear_command_advertises_then_flag(self):
        from hermes_cli.commands import resolve_command
        cmd = resolve_command("clear")
        assert cmd is not None
        assert "--then" in (cmd.args_hint or "")
        assert "--then" in cmd.description or "handoff" in cmd.description.lower()
