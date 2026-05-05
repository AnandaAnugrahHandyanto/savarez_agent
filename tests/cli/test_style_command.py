"""Tests for /style command in the CLI."""

from unittest.mock import MagicMock, patch


class TestCLIStyleCommand:
    def _make_cli(self):
        from cli import HermesCLI

        cli = HermesCLI.__new__(HermesCLI)
        cli.response_style = "normal"
        cli.agent = MagicMock()
        cli.console = MagicMock()
        cli._console_print = MagicMock()
        return cli

    def test_style_normalizes_and_saves(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True) as mock_save:
            cli._handle_style_command("/style BRIEF")

        assert cli.response_style == "brief"
        assert cli.agent is None
        mock_save.assert_called_once_with("agent.response_style", "brief")
        cli._console_print.assert_called()

    def test_style_status_without_args(self):
        cli = self._make_cli()
        cli.response_style = "ultra"

        cli._handle_style_command("/style")

        output = " ".join(str(call) for call in cli._console_print.call_args_list)
        assert "current response style: ultra" in output.lower()
        assert "auto-clarity: on" in output.lower()
        assert "brief" in output.lower()

    def test_style_status_subcommand(self):
        cli = self._make_cli()
        cli.response_style = "brief"

        cli._handle_style_command("/style status")

        output = " ".join(str(call) for call in cli._console_print.call_args_list)
        assert "current response style: brief" in output.lower()
        assert "auto-clarity: on" in output.lower()
        assert "usage: /style <normal|brief|ultra>" in output.lower()

    def test_style_set_status_persists_when_explicit(self):
        cli = self._make_cli()
        with patch("cli.save_config_value", return_value=True) as mock_save:
            cli._handle_style_command("/style status")

        mock_save.assert_not_called()
        assert cli.response_style == "normal"

    def test_style_toggle_keywords_are_invalid(self):
        cli = self._make_cli()

        cli._handle_style_command("/style toggle")

        output = " ".join(str(call) for call in cli._console_print.call_args_list)
        assert "unknown style" in output.lower()
        assert "toggle" in output.lower()

    def test_style_invalid_value_shows_help(self):
        cli = self._make_cli()

        cli._handle_style_command("/style caveman")

        output = " ".join(str(call) for call in cli._console_print.call_args_list)
        assert "unknown style" in output.lower()
        assert "normal" in output.lower()
        assert "brief" in output.lower()
        assert "ultra" in output.lower()

    def test_process_command_dispatches_style(self):
        cli = self._make_cli()
        cli._handle_style_command = MagicMock()
        cli._handle_reload_command = MagicMock()
        cli._handle_model_switch = MagicMock()
        cli._handle_gquota_command = MagicMock()
        cli._handle_personality_command = MagicMock()
        cli.retry_last = MagicMock(return_value=None)
        cli.undo_last = MagicMock()
        cli._handle_branch_command = MagicMock()
        cli.save_conversation = MagicMock()
        cli._handle_cron_command = MagicMock()
        cli._handle_skills_command = MagicMock()
        cli._show_gateway_status = MagicMock()
        cli._show_session_status = MagicMock()
        cli._toggle_verbose = MagicMock()
        cli._toggle_yolo = MagicMock()
        cli._handle_reasoning_command = MagicMock()
        cli._handle_fast_command = MagicMock()
        cli._manual_compress = MagicMock()
        cli._show_usage = MagicMock()
        cli._show_insights = MagicMock()
        cli._handle_copy_command = MagicMock()
        cli._handle_debug_command = MagicMock()
        cli._handle_paste_command = MagicMock()
        cli._handle_image_command = MagicMock()
        cli._reload_mcp = MagicMock()
        cli._handle_browser_command = MagicMock()
        cli._handle_rollback_command = MagicMock()
        cli._handle_snapshot_command = MagicMock()
        cli._handle_stop_command = MagicMock()
        cli._handle_agents_command = MagicMock()
        cli._handle_background_command = MagicMock()
        cli._handle_btw_command = MagicMock()
        cli._pending_input = MagicMock()
        cli._agent_running = False
        cli._busy_command = MagicMock()
        cli._slow_command_status = MagicMock(return_value="")
        cli._status_bar_visible = True
        cli._console_print = MagicMock()
        cli.new_session = MagicMock()
        cli._session_db = None
        cli._pending_title = None
        cli.quick_commands = {}

        assert cli.process_command("/style brief") is True
        cli._handle_style_command.assert_called_once_with("/style brief")
