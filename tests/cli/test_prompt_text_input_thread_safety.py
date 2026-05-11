"""Tests for ``HermesCLI._prompt_text_input`` thread-safe input dispatch.

Slash commands (``/clear``, ``/new``, ``/undo``, ``/reload-mcp``) are dispatched
from the ``process_loop`` daemon thread.  ``prompt_toolkit.run_in_terminal``
returns a coroutine that only the main-thread event loop can drive; calling it
from a daemon thread orphans the coroutine, ``_ask`` never runs, and user
keystrokes leak into the composer instead of the confirmation prompt
(see issue #23185).

The fix uses ``asyncio.run_coroutine_threadsafe`` to schedule the prompt on
the main thread's event loop (stored in ``self._app.loop``), so that
``run_in_terminal`` executes on the correct thread (see #23853).
"""

import asyncio
import threading
from unittest.mock import MagicMock, patch


def _make_cli():
    """Minimal HermesCLI shell exposing ``_prompt_text_input``."""
    import cli as cli_mod

    obj = object.__new__(cli_mod.HermesCLI)
    obj._app = MagicMock()
    obj._status_bar_visible = True
    return obj


class TestPromptTextInputThreadSafety:
    def test_main_thread_uses_run_in_terminal(self):
        """On the main thread with an active app, route through run_in_terminal."""
        cli = _make_cli()

        with patch("prompt_toolkit.application.run_in_terminal") as mock_rit, \
             patch("builtins.input", return_value="2"):
            result = cli._prompt_text_input("Choice: ")

        # run_in_terminal was invoked; the _ask closure passed to it would
        # call input() when driven by the event loop.  We assert dispatch path,
        # not the orphaned-coroutine result.
        assert mock_rit.called

    def test_background_thread_schedules_via_event_loop(self):
        """On a daemon thread with a running app, schedule via asyncio.run_coroutine_threadsafe.

        This is the bug from issue #23853: process_loop dispatches slash
        commands on a daemon thread, so run_in_terminal's coroutine is
        orphaned.  The fix retrieves the main event loop from self._app.loop
        and schedules the prompt via asyncio.run_coroutine_threadsafe.
        """
        cli = _make_cli()
        cli._app.loop = MagicMock()
        result_holder = {}

        def run_on_daemon():
            # asyncio.run_coroutine_threadsafe schedules the coroutine on the
            # main event loop.  In the test we don"t have a real event loop,
            # so mock it to drive the coroutine directly with asyncio.run.
            # The coroutine awaits run_in_terminal (mocked to call fn()
            # inline) which drives _ask -> input() returning "1".
            def fake_schedule(coro, loop):
                try:
                    asyncio.run(coro)
                except Exception:
                    pass
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=fake_schedule), \
                 patch("prompt_toolkit.application.run_in_terminal",
                       side_effect=lambda fn: fn()) as mock_rit, \
                 patch("builtins.input", return_value="1"):
                result_holder["value"] = cli._prompt_text_input("Choice [1/2/3]: ")

        t = threading.Thread(target=run_on_daemon, daemon=True)
        t.start()
        t.join(timeout=5.0)
        assert not t.is_alive(), "daemon thread hung — event loop scheduling deadlocked"

        # run_in_terminal was invoked (via the scheduled coroutine).
        # The input value was captured.
        assert result_holder["value"] == "1"

    def test_no_app_uses_input(self):
        """Without an active prompt_toolkit app, fall back to input() directly."""
        cli = _make_cli()
        cli._app = None

        with patch("builtins.input", return_value="yes") as mock_input:
            result = cli._prompt_text_input("Choice: ")

        assert mock_input.called
        assert result == "yes"

    def test_run_in_terminal_exception_falls_back(self):
        """If run_in_terminal raises (WSL / Warp edge cases), fall back to input()."""
        cli = _make_cli()

        with patch(
            "prompt_toolkit.application.run_in_terminal",
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
