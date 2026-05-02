"""Tests for CLI redraw helpers used to recover from terminal buffer drift.

Covers:
  - _force_full_redraw (#8688 cmux tab switch, /redraw, Ctrl+L)
  - the resize handler we install over prompt_toolkit's _on_resize (#5474)

Both behaviors are exercised against fake prompt_toolkit renderer/output
objects — we're asserting the escape sequences the CLI sends, not that
the terminal physically repainted.
"""

from unittest.mock import MagicMock, patch

import pytest

from cli import HermesCLI


@pytest.fixture
def bare_cli():
    """A HermesCLI with no __init__ — we only exercise the redraw helper."""
    cli = object.__new__(HermesCLI)
    return cli


class TestForceFullRedraw:
    def test_no_app_is_safe(self, bare_cli):
        # _force_full_redraw must be a no-op when the TUI isn't running.
        bare_cli._app = None
        bare_cli._force_full_redraw()  # must not raise

    def test_missing_app_attr_is_safe(self, bare_cli):
        # Simulate HermesCLI before the TUI has ever been constructed.
        bare_cli._force_full_redraw()  # must not raise

    def test_sends_full_clear_and_invalidates(self, bare_cli):
        app = MagicMock()
        out = app.renderer.output
        bare_cli._app = app

        bare_cli._force_full_redraw()

        # Must erase screen, home cursor, and flush — in that order.
        out.reset_attributes.assert_called_once()
        out.erase_screen.assert_called_once()
        out.cursor_goto.assert_called_once_with(0, 0)
        out.flush.assert_called_once()

        # Must reset prompt_toolkit's tracked screen/cursor state so the
        # next incremental redraw starts from a clean (0, 0) origin.
        app.renderer.reset.assert_called_once_with(leave_alternate_screen=False)

        # Must schedule a repaint.
        app.invalidate.assert_called_once()

    def test_swallows_renderer_exceptions(self, bare_cli):
        # If the renderer blows up for any reason, the helper must not
        # propagate — otherwise a stray Ctrl+L would crash the CLI.
        app = MagicMock()
        app.renderer.output.erase_screen.side_effect = RuntimeError("boom")
        bare_cli._app = app

        bare_cli._force_full_redraw()  # must not raise

        # invalidate() is still attempted after a renderer failure.
        app.invalidate.assert_called_once()

    def test_swallows_invalidate_exceptions(self, bare_cli):
        app = MagicMock()
        app.invalidate.side_effect = RuntimeError("boom")
        bare_cli._app = app

        bare_cli._force_full_redraw()  # must not raise


class TestFocusReporting:
    def test_enable_focus_reporting_writes_escape_sequence(self, bare_cli):
        app = MagicMock()
        bare_cli._app = app
        bare_cli._focus_reporting_enabled = False

        with patch("cli.time.monotonic", return_value=123.0):
            bare_cli._set_terminal_focus_reporting(True)

        app.renderer.output.write_raw.assert_called_once_with("\x1b[?1004h")
        app.renderer.output.flush.assert_called_once()
        assert bare_cli._focus_reporting_enabled is True
        assert bare_cli._focus_reporting_started_at == 123.0

    def test_disable_focus_reporting_writes_escape_sequence(self, bare_cli):
        app = MagicMock()
        bare_cli._app = app
        bare_cli._focus_reporting_enabled = True
        bare_cli._focus_redraw_pending = True

        bare_cli._set_terminal_focus_reporting(False)

        app.renderer.output.write_raw.assert_called_once_with("\x1b[?1004l")
        app.renderer.output.flush.assert_called_once()
        assert bare_cli._focus_reporting_enabled is False
        assert bare_cli._focus_redraw_pending is False

    def test_focus_in_after_focus_out_forces_redraw(self, bare_cli):
        bare_cli._focus_redraw_pending = False
        bare_cli._focus_reporting_started_at = 0.0
        bare_cli._last_focus_redraw = 0.0
        bare_cli._force_full_redraw = MagicMock()

        with patch("cli.time.monotonic", return_value=10.0):
            bare_cli._handle_terminal_focus_out()
        assert bare_cli._focus_redraw_pending is True

        with patch("cli.time.monotonic", return_value=11.0):
            bare_cli._handle_terminal_focus_in()

        bare_cli._force_full_redraw.assert_called_once()
        assert bare_cli._focus_redraw_pending is False
        assert bare_cli._last_focus_redraw == 11.0

    def test_focus_in_without_pending_focus_out_is_noop(self, bare_cli):
        bare_cli._focus_redraw_pending = False
        bare_cli._focus_reporting_started_at = 0.0
        bare_cli._last_focus_redraw = 0.0
        bare_cli._force_full_redraw = MagicMock()

        with patch("cli.time.monotonic", return_value=11.0):
            bare_cli._handle_terminal_focus_in()

        bare_cli._force_full_redraw.assert_not_called()

    def test_startup_focus_handshake_does_not_redraw(self, bare_cli):
        bare_cli._focus_redraw_pending = True
        bare_cli._focus_reporting_started_at = 10.0
        bare_cli._last_focus_redraw = 0.0
        bare_cli._force_full_redraw = MagicMock()

        with patch("cli.time.monotonic", return_value=10.1):
            bare_cli._handle_terminal_focus_in()

        bare_cli._force_full_redraw.assert_not_called()
        assert bare_cli._focus_redraw_pending is True
