"""Regression test for _prompt_text_input thread guard (issue #23297).

_confirm_destructive_slash runs inside process_loop (a daemon thread).
_prompt_text_input must NOT call run_in_terminal from a background thread
because run_in_terminal requires an asyncio event loop that only exists in
the main prompt_toolkit thread.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _prompt_text_input(self, prompt_text: str) -> str | None:
    """Copy of cli.HermesCLI._prompt_text_input for isolated testing."""
    import threading as _threading
    result = [None]

    def _ask():
        try:
            result[0] = input(prompt_text).strip() or None
        except (KeyboardInterrupt, EOFError):
            pass

    in_main_thread = _threading.current_thread() is _threading.main_thread()

    if self._app and in_main_thread:
        from prompt_toolkit.application import run_in_terminal
        was_visible = self._status_bar_visible
        self._status_bar_visible = False
        self._app.invalidate()
        try:
            run_in_terminal(_ask)
        finally:
            self._status_bar_visible = was_visible
            self._app.invalidate()
    else:
        _ask()
    return result[0]


def test_prompt_text_input_skips_run_in_terminal_from_background_thread():
    """When called from a non-main thread, _prompt_text_input must fall
    back to direct input() instead of run_in_terminal (which requires an
    event loop).  Previously this produced:
        RuntimeWarning: coroutine 'run_in_terminal.<locals>.run' was never awaited
    """
    mock_app = MagicMock()
    self_ = SimpleNamespace(
        _app=mock_app,
        _status_bar_visible=True,
    )

    captured = {}

    def _bg():
        with patch("builtins.input", return_value="1"):
            captured["result"] = _prompt_text_input(self_, "Choice: ")

    t = threading.Thread(target=_bg)
    t.start()
    t.join(timeout=5)

    assert captured["result"] == "1"
    # run_in_terminal must NOT have been called from the background thread
    mock_app.invalidate.assert_not_called()


def test_prompt_text_input_uses_run_in_terminal_from_main_thread():
    """When called from the main thread with _app set, _prompt_text_input
    should use run_in_terminal (the normal prompt_toolkit path)."""
    mock_app = MagicMock()
    self_ = SimpleNamespace(
        _app=mock_app,
        _status_bar_visible=True,
    )

    with patch("builtins.input", return_value="2"),          patch("prompt_toolkit.application.run_in_terminal") as mock_rit:
        # run_in_terminal should call the function synchronously
        mock_rit.side_effect = lambda fn: fn()
        result = _prompt_text_input(self_, "Choice: ")

    assert result == "2"
    mock_rit.assert_called_once()
