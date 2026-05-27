"""Regression tests for the -tui → -t ui argparse misparse.

When a user types `hermes -tui` instead of `hermes --tui`, argparse
interprets it as `-t ui` (toolsets="ui", tui=False), which previously
silently loaded zero tools.  The fix adds an early guard in cmd_chat()
that catches this exact pattern and exits with a descriptive error.
"""

import argparse
import sys
import pytest


def _make_args(**kwargs):
    """Create a minimal argparse.Namespace with defaults."""
    defaults = {
        "tui": False,
        "toolsets": None,
        "continue_last": None,
        "resume": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestTuiFlagTypoDetection:
    """cmd_chat() must reject toolsets='ui' when --tui is not set."""

    def test_single_dash_tui_exits_with_error(self, capsys):
        import hermes_cli.main as main_mod

        args = _make_args(toolsets="ui", tui=False)
        with pytest.raises(SystemExit) as exc_info:
            main_mod.cmd_chat(args)

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "--tui" in captured.err
        assert "-t ui" in captured.err or "toolsets" in captured.err.lower()

    def test_error_message_names_the_fix(self, capsys):
        import hermes_cli.main as main_mod

        args = _make_args(toolsets="ui", tui=False)
        with pytest.raises(SystemExit):
            main_mod.cmd_chat(args)

        captured = capsys.readouterr()
        assert "--tui" in captured.err

    def test_double_dash_tui_not_affected(self, monkeypatch, capsys):
        """hermes --tui (correct form) must not trigger the guard."""
        import hermes_cli.main as main_mod

        # Patch _launch_tui so we don't actually launch anything
        monkeypatch.setattr(main_mod, "_launch_tui", lambda *a, **kw: sys.exit(0))
        monkeypatch.setattr(main_mod, "_pin_kanban_board_env", lambda: None)

        args = _make_args(toolsets=None, tui=True)
        with pytest.raises(SystemExit) as exc_info:
            main_mod.cmd_chat(args)

        # The 0 exit comes from our patched _launch_tui — not the error guard
        assert exc_info.value.code == 0

    def test_valid_toolset_not_blocked(self, capsys):
        """A legitimate toolset name like 'web' must not trigger the guard.

        We only run the guard portion of cmd_chat by extracting its logic
        rather than calling the full function (which requires many deps).
        """
        import os
        # Replicate the exact guard logic from cmd_chat
        tui = False
        use_tui = tui or os.environ.get("HERMES_TUI") == "1"
        raw_toolsets = "web"
        exited = False
        if raw_toolsets and not use_tui:
            ts_items = [t.strip() for t in str(raw_toolsets).split(",") if t.strip()]
            if ts_items == ["ui"]:
                exited = True
        assert not exited, "Valid toolset 'web' should not trigger the -tui guard"

    def test_parser_confirms_single_dash_misparse(self):
        """Verify that the real argparse parser produces toolsets='ui' for -tui."""
        from hermes_cli._parser import build_top_level_parser

        parser, _subparsers, _chat_parser = build_top_level_parser()
        args = parser.parse_args(["-tui"])

        assert args.toolsets == "ui"
        assert getattr(args, "tui", False) is False
