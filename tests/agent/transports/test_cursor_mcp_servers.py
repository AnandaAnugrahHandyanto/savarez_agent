"""Tests for Cursor SDK MCP server wiring."""

from __future__ import annotations

from agent.transports.cursor_sdk_session import (
    _hermes_package_root,
    _translate_hermes_mcp_for_cursor,
    build_cursor_mcp_servers,
    build_hermes_tools_mcp_servers,
)


def test_hermes_tools_mcp_uses_package_root_cwd():
    servers = build_hermes_tools_mcp_servers()
    entry = servers["hermes-tools"]
    assert entry["cwd"] == _hermes_package_root()
    assert entry["command"]
    assert "-m" in entry["args"]
    assert "agent.transports.hermes_tools_mcp_server" in entry["args"]


def test_cursor_mcp_entry_enables_cursor_surface_and_kanban_env(monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-abc")
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "default")
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", "/tmp/worktree")
    monkeypatch.setenv("HERMES_PROFILE", "work")

    entry = build_cursor_mcp_servers(hermes_config={})["hermes-tools"]
    env = entry.get("env", {})
    assert env.get("HERMES_MCP_CURSOR_SURFACE") == "1"
    assert env.get("HERMES_KANBAN_TASK") == "task-abc"
    assert env.get("HERMES_KANBAN_BOARD") == "default"
    assert env.get("HERMES_KANBAN_WORKSPACE") == "/tmp/worktree"
    assert env.get("HERMES_PROFILE") == "work"


def test_translate_http_mcp_headers_for_cursor():
    translated = _translate_hermes_mcp_for_cursor(
        "notion",
        {
            "url": "https://mcp.example/notion",
            "headers": {"Authorization": "Bearer x"},
        },
    )
    assert translated is not None
    assert translated["url"] == "https://mcp.example/notion"
    assert translated["headers"] == {"Authorization": "Bearer x"}
    assert "http_headers" not in translated


def test_build_cursor_mcp_servers_skips_disabled():
    cfg = {
        "mcp_servers": {
            "off": {"command": "echo", "enabled": False},
            "on": {"command": "echo", "args": ["hi"]},
        }
    }
    servers = build_cursor_mcp_servers(hermes_config=cfg)
    assert "hermes-tools" in servers
    assert "off" not in servers
    assert "on" in servers
