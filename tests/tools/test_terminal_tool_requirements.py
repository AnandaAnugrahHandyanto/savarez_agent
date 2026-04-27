"""Tests for terminal/file tool availability in local dev environments."""

import importlib

from model_tools import get_tool_definitions
from tools.registry import registry

terminal_tool_module = importlib.import_module("tools.terminal_tool")


class TestTerminalRequirements:
    def test_local_backend_requirements(self, monkeypatch):
        monkeypatch.setattr(
            terminal_tool_module,
            "_get_env_config",
            lambda: {"env_type": "local"},
        )
        assert terminal_tool_module.check_terminal_requirements() is True

    def test_terminal_and_file_tools_resolve_for_local_backend(self, monkeypatch):
        monkeypatch.setattr(
            terminal_tool_module,
            "_get_env_config",
            lambda: {"env_type": "local"},
        )
        tools = get_tool_definitions(enabled_toolsets=["terminal", "file"], quiet_mode=True)
        names = {tool["function"]["name"] for tool in tools}
        assert "terminal" in names
        assert {"read_file", "write_file", "patch", "search_files"}.issubset(names)

    def test_terminal_and_execute_code_tools_resolve_for_managed_modal(self, monkeypatch, tmp_path):
        """execute_code + terminal are listed when their registry checks pass.

        The registry holds direct references to the original check functions,
        so patching module-level names is not always enough. Mutate
        ToolEntry.check_fn briefly to avoid full-suite flakiness from Modal
        credentials, HOME, feature flags, and sandbox state in other tests.
        """
        monkeypatch.setenv("HERMES_ENABLE_NOUS_MANAGED_TOOLS", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
        monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)

        term_entry = registry._tools.get("terminal")
        code_entry = registry._tools.get("execute_code")
        assert term_entry is not None and code_entry is not None
        orig_t, orig_e = term_entry.check_fn, code_entry.check_fn
        term_entry.check_fn = lambda: True
        code_entry.check_fn = lambda: True
        try:
            tools = get_tool_definitions(
                enabled_toolsets=["terminal", "code_execution"],
                quiet_mode=True,
            )
            names = {tool["function"]["name"] for tool in tools}

            assert "terminal" in names, names
            assert "execute_code" in names, names
        finally:
            term_entry.check_fn = orig_t
            code_entry.check_fn = orig_e
