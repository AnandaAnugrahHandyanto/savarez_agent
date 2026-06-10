"""Test that tui_gateway/entry.py registers shell hooks at startup.

Regression test for GitHub issue #43823 — shell hooks configured in
config.yaml were silently ignored in the desktop/TUI entry point because
``register_from_config()`` was never called from ``tui_gateway/entry.py``.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestTuiEntryShellHooks:
    """Verify shell hooks are registered during TUI startup."""

    def test_register_from_config_called_at_startup(self):
        """``main()`` must call ``register_from_config`` so that
        declarative shell hooks (e.g. ``pre_tool_call``) fire in desktop
        sessions just like they do in CLI and gateway sessions."""
        # We need to mock the entire startup sequence so main() doesn't
        # actually start reading stdin or writing to stdout.
        mock_register = MagicMock()

        with patch("tui_gateway.entry._install_sidecar_publisher"), \
             patch("tui_gateway.entry.write_json", side_effect=[True, lambda *a, **k: True]) as mock_write, \
             patch("hermes_cli.config.load_config", return_value={}), \
             patch("agent.shell_hooks.register_from_config", mock_register), \
             patch("sys.stdin", []):
            # Reload to pick up the mock targets
            import tui_gateway.entry as entry_mod
            # main() reads from sys.stdin — empty list means no lines, exits loop
            try:
                entry_mod.main()
            except SystemExit:
                pass

        mock_register.assert_called_once()
        call_kwargs = mock_register.call_args
        assert call_kwargs[1].get("accept_hooks") is False

    def test_register_failure_does_not_block_startup(self):
        """If ``register_from_config`` raises, the TUI must still start."""
        mock_register = MagicMock(side_effect=RuntimeError("boom"))

        with patch("tui_gateway.entry._install_sidecar_publisher"), \
             patch("tui_gateway.entry.write_json", side_effect=[True, lambda *a, **k: True]), \
             patch("hermes_cli.config.load_config", return_value={}), \
             patch("agent.shell_hooks.register_from_config", mock_register), \
             patch("sys.stdin", []):
            import tui_gateway.entry as entry_mod
            try:
                entry_mod.main()
            except SystemExit:
                pass
            # main() should not have crashed — it completed normally

        mock_register.assert_called_once()
