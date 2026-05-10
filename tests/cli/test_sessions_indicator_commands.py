"""Tests for /sessions and /indicator slash command handling in classic CLI."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _import_cli():
    import hermes_cli.config as config_mod

    if not hasattr(config_mod, "save_env_value_secure"):
        config_mod.save_env_value_secure = lambda key, value: {
            "success": True,
            "stored_as": key,
            "validated": False,
        }

    import cli as cli_mod

    return cli_mod


def _make_cli():
    cli_mod = _import_cli()
    cli_obj = cli_mod.HermesCLI.__new__(cli_mod.HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = None
    cli_obj._pending_input = MagicMock()
    return cli_mod, cli_obj


class TestSessionsCommand:
    def test_sessions_dispatches_recent_sessions_view(self):
        _, cli_obj = _make_cli()

        with patch.object(cli_obj, "_show_recent_sessions", return_value=True) as mock_show:
            cli_obj.process_command("/sessions")

        mock_show.assert_called_once_with(reason="resume")

    def test_sessions_prints_empty_state_when_no_sessions_exist(self):
        _, cli_obj = _make_cli()

        with (
            patch.object(cli_obj, "_show_recent_sessions", return_value=False),
            patch("builtins.print") as mock_print,
        ):
            cli_obj.process_command("/sessions")

        printed = " ".join(str(call) for call in mock_print.call_args_list)
        assert "No recent sessions yet." in printed


class TestIndicatorCommand:
    def _make_stub(self):
        return SimpleNamespace()

    def test_indicator_without_args_shows_normalized_status(self):
        cli_mod = _import_cli()
        stub = self._make_stub()

        with (
            patch.object(cli_mod, "_cprint") as mock_cprint,
            patch.object(cli_mod, "save_config_value") as mock_save,
            patch("hermes_cli.config.load_config", return_value={"display": {"tui_status_indicator": "  EMOJI "}}),
        ):
            cli_mod.HermesCLI._handle_indicator_command(stub, "/indicator")

        mock_save.assert_not_called()
        printed = " ".join(str(call) for call in mock_cprint.call_args_list)
        assert "emoji" in printed.lower()
        assert "Usage: /indicator" in printed

    def test_indicator_status_falls_back_to_default_for_unknown_config(self):
        cli_mod = _import_cli()
        stub = self._make_stub()

        with (
            patch.object(cli_mod, "_cprint") as mock_cprint,
            patch("hermes_cli.config.load_config", return_value={"display": {"tui_status_indicator": "sparkles"}}),
        ):
            cli_mod.HermesCLI._handle_indicator_command(stub, "/indicator status")

        printed = " ".join(str(call) for call in mock_cprint.call_args_list)
        assert "kaomoji" in printed.lower()

    def test_indicator_valid_value_saves_config(self):
        cli_mod = _import_cli()
        stub = self._make_stub()

        with (
            patch.object(cli_mod, "_cprint") as mock_cprint,
            patch.object(cli_mod, "save_config_value", return_value=True) as mock_save,
        ):
            cli_mod.HermesCLI._handle_indicator_command(stub, "/indicator ascii")

        mock_save.assert_called_once_with("display.tui_status_indicator", "ascii")
        printed = " ".join(str(call) for call in mock_cprint.call_args_list)
        assert "ascii" in printed.lower()

    def test_indicator_invalid_value_prints_usage(self):
        cli_mod = _import_cli()
        stub = self._make_stub()

        with (
            patch.object(cli_mod, "_cprint") as mock_cprint,
            patch.object(cli_mod, "save_config_value") as mock_save,
        ):
            cli_mod.HermesCLI._handle_indicator_command(stub, "/indicator glitter")

        mock_save.assert_not_called()
        printed = " ".join(str(call) for call in mock_cprint.call_args_list)
        assert "Unknown indicator" in printed
        assert "Usage: /indicator" in printed

    def test_indicator_dispatches_from_process_command(self):
        _, cli_obj = _make_cli()

        with patch.object(cli_obj, "_handle_indicator_command") as mock_indicator:
            cli_obj.process_command("/indicator unicode")

        mock_indicator.assert_called_once_with("/indicator unicode")
