"""Regression: _cprint survives when prompt_toolkit cannot attach a Win32 console."""

from __future__ import annotations

from unittest.mock import patch

import cli


def test_safe_pt_print_fallback_when_pt_print_raises(capsys):
    with patch.object(cli, "_pt_print", side_effect=RuntimeError("simulated NoConsoleScreenBufferError")):
        cli._safe_pt_print("worker log line")
    assert capsys.readouterr().out.strip() == "worker log line"


def test_cprint_fallback_when_no_running_app(capsys):
    with patch("prompt_toolkit.application.get_app_or_none", return_value=None):
        with patch.object(cli, "_record_output_history", lambda _t: None):
            with patch.object(cli, "_pt_print", side_effect=RuntimeError("no console")):
                cli._cprint("kanban worker init")
    assert "kanban worker init" in capsys.readouterr().out


def test_replay_output_history_fallback(capsys):
    cli._configure_output_history(True)
    cli._clear_output_history()
    cli._OUTPUT_HISTORY.append("history line")
    try:
        with patch.object(cli, "_pt_print", side_effect=RuntimeError("no console")):
            cli._replay_output_history()
    finally:
        cli._configure_output_history(True)
    assert "history line" in capsys.readouterr().out
