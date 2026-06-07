"""Tests for shell-hook registration in TUI and ACP entry points.

Regression guard for #41457: shell hooks must be registered at startup
in both the desktop app (TUI gateway) and the ACP adapter (IDE integration),
matching the CLI and gateway behavior.
"""

import types
from unittest.mock import patch

import pytest


class TestTUIHookRegistration:
    """Verify tui_gateway/entry.py registers shell hooks at startup."""

    def test_register_from_config_called_at_startup(self, monkeypatch):
        """register_from_config is invoked during TUI main()."""
        from tui_gateway import entry

        registered = {}

        def fake_register(config, accept_hooks=False):
            registered["called"] = True
            registered["config"] = config

        monkeypatch.setattr(entry, "_install_sidecar_publisher", lambda: None)
        monkeypatch.setattr(
            "agent.shell_hooks.register_from_config", fake_register
        )
        monkeypatch.setattr(
            "hermes_cli.config.load_config", lambda: {"hooks": {}}
        )
        # Prevent MCP discovery and stdin loop from running
        monkeypatch.setattr(
            entry, "write_json", lambda d: False
        )

        with pytest.raises(SystemExit):
            entry.main()

        assert registered.get("called") is True

    def test_hook_registration_failure_does_not_crash(self, monkeypatch):
        """If register_from_config raises, TUI startup continues."""
        from tui_gateway import entry

        monkeypatch.setattr(entry, "_install_sidecar_publisher", lambda: None)
        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config broken")),
        )
        monkeypatch.setattr(entry, "write_json", lambda d: False)

        # Should not raise — the exception is caught and logged
        with pytest.raises(SystemExit):
            entry.main()


class TestACPAdapterHookRegistration:
    """Verify acp_adapter/entry.py registers shell hooks at startup."""

    def test_register_from_config_called_at_startup(self, monkeypatch):
        """register_from_config is invoked during ACP main()."""
        import acp
        from acp_adapter import entry

        registered = {}

        def fake_register(config, accept_hooks=False):
            registered["called"] = True
            registered["config"] = config

        monkeypatch.setattr(entry, "_setup_logging", lambda: None)
        monkeypatch.setattr(entry, "_load_env", lambda: None)

        async def fake_run_agent(agent, **kwargs):
            pass

        monkeypatch.setattr(acp, "run_agent", fake_run_agent)
        monkeypatch.setattr(
            "agent.shell_hooks.register_from_config", fake_register
        )
        monkeypatch.setattr(
            "hermes_cli.config.load_config", lambda: {"hooks": {}}
        )

        entry.main([])

        assert registered.get("called") is True

    def test_hook_registration_failure_does_not_crash(self, monkeypatch):
        """If register_from_config raises, ACP startup continues."""
        import acp
        from acp_adapter import entry

        monkeypatch.setattr(entry, "_setup_logging", lambda: None)
        monkeypatch.setattr(entry, "_load_env", lambda: None)

        async def fake_run_agent(agent, **kwargs):
            pass

        monkeypatch.setattr(acp, "run_agent", fake_run_agent)
        monkeypatch.setattr(
            "hermes_cli.config.load_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config broken")),
        )

        # Should not raise — the exception is caught and logged
        entry.main([])
