"""Tests for ``HermesCLI._prompt_text_input`` thread-safe input dispatch.

Raw ``input()`` prompts can race with prompt_toolkit when called from the TUI.
The normal slash confirmations now use a prompt_toolkit-native modal, but
``_prompt_text_input`` remains as a fallback for non-interactive calls and edge
cases.
"""

import threading
from unittest.mock import MagicMock, patch


def _make_cli():
    """Minimal HermesCLI shell exposing prompt fallback helpers."""
    import cli as cli_mod

    obj = object.__new__(cli_mod.HermesCLI)
    obj._app = MagicMock()
    obj._status_bar_visible = True
    return obj


class TestPromptTextInputThreadSafety:
    def test_main_thread_uses_ptk_prompt(self):
        """On the main thread with an active app, route through ptk_prompt."""
        cli = _make_cli()

        with patch("prompt_toolkit.shortcuts.prompt", return_value="2") as mock_ptk, \
             patch("builtins.input", return_value="2"):
            result = cli._prompt_text_input("Choice: ")

        assert mock_ptk.called
        assert result == "2"

    def test_background_thread_falls_back_to_direct_input(self):
        """On a daemon thread, skip ptk_prompt and call input() directly.

        This preserves the fallback for any prompt that still runs off the main
        UI thread: ptk_prompt would otherwise fail without an event loop.
        """
        cli = _make_cli()
        captured = {}

        def fake_input(prompt):
            captured["prompt"] = prompt
            return "1"

        result_holder = {}

        def run_on_daemon():
            with patch("prompt_toolkit.shortcuts.prompt") as mock_ptk, \
                 patch("builtins.input", side_effect=fake_input):
                result_holder["value"] = cli._prompt_text_input("Choice [1/2/3]: ")
                result_holder["ptk_called"] = mock_ptk.called

        t = threading.Thread(target=run_on_daemon, daemon=True)
        t.start()
        t.join(timeout=2.0)
        assert not t.is_alive(), "daemon thread hung — input() was not driven"

        # ptk_prompt was bypassed entirely on the background thread.
        assert result_holder["ptk_called"] is False
        # input() was invoked with the prompt and its return value was captured.
        assert captured.get("prompt") == "Choice [1/2/3]: "
        assert result_holder["value"] == "1"

    def test_no_app_uses_direct_input(self):
        """Without an active prompt_toolkit app, always call input() directly."""
        cli = _make_cli()
        cli._app = None

        with patch("builtins.input", return_value="cancel") as mock_input:
            result = cli._prompt_text_input("Choice: ")

        assert mock_input.called
        assert result == "cancel"

    def test_run_in_terminal_exception_falls_back(self):
        """If ptk_prompt raises (WSL / Warp edge cases), fall back to input()."""
        cli = _make_cli()

        with patch(
            "prompt_toolkit.shortcuts.prompt",
            side_effect=RuntimeError("event loop dropped the coroutine"),
        ), patch("builtins.input", return_value="3") as mock_input:
            result = cli._prompt_text_input("Choice: ")

        assert mock_input.called
        assert result == "3"

    def test_eof_returns_none(self):
        """EOFError from input() yields None, not an unhandled exception."""
        cli = _make_cli()
        cli._app = None

        with patch("builtins.input", side_effect=EOFError()):
            result = cli._prompt_text_input("Choice: ")

        assert result is None
