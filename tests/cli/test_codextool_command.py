from unittest.mock import MagicMock, patch

from cli import HermesCLI


def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj._app = None
    cli_obj._pending_input = MagicMock()
    return cli_obj


def test_codextool_usage_when_no_args():
    cli = _make_cli()

    cli._handle_codextool_command("/codexTool")

    printed = " ".join(str(call) for call in cli.console.print.call_args_list)
    assert "Usage: /codexTool" in printed
    assert "watch" in printed


def test_process_command_dispatches_codextool():
    cli = _make_cli()
    with patch.object(cli, "_handle_codextool_command") as mock_handler:
        cli.process_command("/codexTool probe --json")
    mock_handler.assert_called_once_with("/codexTool probe --json")


def test_codextool_runs_script_and_prints_stdout():
    cli = _make_cli()
    with patch.object(cli, "_run_codextool_cli", return_value=(0, '{"ok": true}\n', "")):
        cli._handle_codextool_command("/codexTool probe --json")

    printed = " ".join(str(call) for call in cli.console.print.call_args_list)
    assert '{"ok": true}' in printed


def test_codextool_reports_nonzero_exit_and_stderr():
    cli = _make_cli()
    with patch.object(cli, "_run_codextool_cli", return_value=(2, "", "boom")):
        cli._handle_codextool_command("/codexTool doctor --fix")

    printed = " ".join(str(call) for call in cli.console.print.call_args_list)
    assert "/codexTool failed (exit 2)" in printed
    assert "boom" in printed


def test_codextool_dispatches_watch_subcommand():
    cli = _make_cli()
    with patch.object(cli, "_run_codextool_cli", return_value=(0, "ok\n", "")) as mock_run:
        cli._handle_codextool_command("/codexTool watch --once --skip-request")

    mock_run.assert_called_once_with(["watch", "--once", "--skip-request"])
