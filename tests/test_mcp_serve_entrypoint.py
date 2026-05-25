"""Regression tests for package entry points that launch MCP server mode."""

from __future__ import annotations

import sys
import types


def test_hermes_agent_console_script_routes_mcp_serve(monkeypatch):
    """Keep ``hermes-agent mcp serve`` usable for MCP registry launches.

    Hermes' human-facing command is ``hermes mcp serve``. MCP registry package
    metadata launches the PyPI package console command with fixed package
    arguments (``mcp``, ``serve``), so the legacy ``hermes-agent`` console
    script must route that pair to MCP server mode instead of treating it as a
    chat query/model pair.
    """
    import run_agent

    called = {}
    fake_mcp_serve = types.SimpleNamespace(
        run_mcp_server=lambda verbose=False: called.setdefault("verbose", verbose)
    )
    monkeypatch.setitem(sys.modules, "mcp_serve", fake_mcp_serve)

    run_agent.main(query="mcp", model="serve", verbose=True)

    assert called == {"verbose": True}
