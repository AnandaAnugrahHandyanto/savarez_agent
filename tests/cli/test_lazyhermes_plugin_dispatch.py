import queue
import sys
from unittest.mock import MagicMock, patch


def test_plugin_command_dispatch_payload_is_queued_for_agent():
    prompt_toolkit_stubs = {
        "prompt_toolkit": MagicMock(),
        "prompt_toolkit.history": MagicMock(),
        "prompt_toolkit.styles": MagicMock(),
        "prompt_toolkit.patch_stdout": MagicMock(),
        "prompt_toolkit.application": MagicMock(),
        "prompt_toolkit.layout": MagicMock(),
        "prompt_toolkit.layout.processors": MagicMock(),
        "prompt_toolkit.filters": MagicMock(),
        "prompt_toolkit.layout.dimension": MagicMock(),
        "prompt_toolkit.layout.menus": MagicMock(),
        "prompt_toolkit.widgets": MagicMock(),
        "prompt_toolkit.key_binding": MagicMock(),
        "prompt_toolkit.completion": MagicMock(),
        "prompt_toolkit.formatted_text": MagicMock(),
        "prompt_toolkit.auto_suggest": MagicMock(),
    }
    with patch.dict(sys.modules, prompt_toolkit_stubs):
        from cli import HermesCLI

        cli = HermesCLI.__new__(HermesCLI)
        cli.config = {}
        cli.console = MagicMock()
        cli.agent = None
        cli.conversation_history = []
        cli.session_id = "test-session"
        cli._pending_input = queue.Queue()

        payload = {
            "display": "Started LazyHermes Ultrawork run: /tmp/run",
            "agent_message": "<lazyhermes-ultrawork-run>\nTask: QA\n</lazyhermes-ultrawork-run>",
        }

        with patch("cli._get_plugin_cmd_handler_names", return_value={"ulw"}), \
             patch("hermes_cli.plugins.get_plugin_command_handler", return_value=lambda _args: payload), \
             patch("cli._cprint") as printed:
            assert cli.process_command("/ulw QA") is True

        printed.assert_called_once_with(payload["display"])
        assert cli._pending_input.get_nowait() == payload["agent_message"]


def test_stringified_plugin_command_dispatch_payload_is_queued_for_agent():
    prompt_toolkit_stubs = {
        "prompt_toolkit": MagicMock(),
        "prompt_toolkit.history": MagicMock(),
        "prompt_toolkit.styles": MagicMock(),
        "prompt_toolkit.patch_stdout": MagicMock(),
        "prompt_toolkit.application": MagicMock(),
        "prompt_toolkit.layout": MagicMock(),
        "prompt_toolkit.layout.processors": MagicMock(),
        "prompt_toolkit.filters": MagicMock(),
        "prompt_toolkit.layout.dimension": MagicMock(),
        "prompt_toolkit.layout.menus": MagicMock(),
        "prompt_toolkit.widgets": MagicMock(),
        "prompt_toolkit.key_binding": MagicMock(),
        "prompt_toolkit.completion": MagicMock(),
        "prompt_toolkit.formatted_text": MagicMock(),
        "prompt_toolkit.auto_suggest": MagicMock(),
    }
    with patch.dict(sys.modules, prompt_toolkit_stubs):
        from cli import HermesCLI

        cli = HermesCLI.__new__(HermesCLI)
        cli.config = {}
        cli.console = MagicMock()
        cli.agent = None
        cli.conversation_history = []
        cli.session_id = "test-session"
        cli._pending_input = queue.Queue()

        payload = {
            "display": "Started LazyHermes Ultrawork run: /tmp/run",
            "agent_message": "QA",
        }

        with patch("cli._get_plugin_cmd_handler_names", return_value={"ulw"}), \
             patch("hermes_cli.plugins.get_plugin_command_handler", return_value=lambda _args: str(payload)), \
             patch("cli._cprint") as printed:
            assert cli.process_command("/ulw QA") is True

        printed.assert_called_once_with(payload["display"])
        assert cli._pending_input.get_nowait() == payload["agent_message"]
