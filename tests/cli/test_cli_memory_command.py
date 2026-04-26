from unittest.mock import MagicMock, patch

from cli import HermesCLI



def _make_cli():
    cli_obj = HermesCLI.__new__(HermesCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = None
    cli_obj._pending_input = MagicMock()
    return cli_obj


class TestMemorySlashCommand:
    def test_memory_command_dispatches_to_memory_status_view(self):
        cli_obj = _make_cli()

        with patch.object(cli_obj, "_show_memory") as mock_show_memory:
            cli_obj.process_command("/memory")

        mock_show_memory.assert_called_once_with()

    def test_memory_prefix_dispatches_when_unique(self):
        cli_obj = _make_cli()

        with patch.object(cli_obj, "_show_memory") as mock_show_memory:
            cli_obj.process_command("/mem")

        mock_show_memory.assert_called_once_with()

    def test_memory_exact_match_wins_over_dynamic_skill(self):
        cli_obj = _make_cli()
        fake_skill = {"/memory-extra": {"name": "Memory Extra", "description": "test"}}

        import cli as cli_mod

        with patch.object(cli_mod, "_skill_commands", fake_skill), \
             patch.object(cli_obj, "_show_memory") as mock_show_memory:
            cli_obj.process_command("/memory")

        mock_show_memory.assert_called_once_with()
