"""Focused tests for the gateway /reload-mcp command."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str = "/reload-mcp") -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.session_store = MagicMock()
    session_entry = MagicMock(session_id="sess-1")
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.append_to_transcript = MagicMock()
    return runner, session_entry


@pytest.mark.asyncio
async def test_reload_mcp_command_reports_success_summary(monkeypatch):
    import tools.mcp_tool as mcp_mod

    runner, session_entry = _make_runner()
    servers = {"alpha": object(), "gone": object()}
    lock = threading.RLock()

    monkeypatch.setattr(mcp_mod, "_servers", servers)
    monkeypatch.setattr(mcp_mod, "_lock", lock)

    def fake_shutdown():
        with lock:
            servers.clear()

    def fake_discover():
        with lock:
            servers["alpha"] = object()
            servers["beta"] = object()
        return ["mcp_alpha_ping", "mcp_beta_ping"]

    monkeypatch.setattr(mcp_mod, "shutdown_mcp_servers", fake_shutdown)
    monkeypatch.setattr(mcp_mod, "discover_mcp_tools", fake_discover)

    result = await runner._handle_reload_mcp_command(_make_event())

    assert "🔄 **MCP Servers Reloaded**" in result
    assert "♻️ Reconnected: alpha" in result
    assert "➕ Added: beta" in result
    assert "➖ Removed: gone" in result
    assert "🔧 2 tool(s) available from 2 server(s)" in result

    runner.session_store.get_or_create_session.assert_called_once()
    runner.session_store.append_to_transcript.assert_called_once()
    session_id, reload_msg = runner.session_store.append_to_transcript.call_args.args
    assert session_id == session_entry.session_id
    assert reload_msg["role"] == "user"
    assert "Added servers: beta" in reload_msg["content"]
    assert "Removed servers: gone" in reload_msg["content"]
    assert "Reconnected servers: alpha" in reload_msg["content"]
    assert "2 MCP tool(s) now available" in reload_msg["content"]


@pytest.mark.asyncio
async def test_reload_mcp_command_reports_empty_summary(monkeypatch):
    import tools.mcp_tool as mcp_mod

    runner, session_entry = _make_runner()
    servers: dict[str, object] = {}
    lock = threading.RLock()

    monkeypatch.setattr(mcp_mod, "_servers", servers)
    monkeypatch.setattr(mcp_mod, "_lock", lock)

    def fake_shutdown():
        with lock:
            servers.clear()

    def fake_discover():
        return []

    monkeypatch.setattr(mcp_mod, "shutdown_mcp_servers", fake_shutdown)
    monkeypatch.setattr(mcp_mod, "discover_mcp_tools", fake_discover)

    result = await runner._handle_reload_mcp_command(_make_event())

    assert "🔄 **MCP Servers Reloaded**" in result
    assert "No MCP servers connected." in result
    assert "tool(s) available" not in result

    runner.session_store.append_to_transcript.assert_called_once()
    session_id, reload_msg = runner.session_store.append_to_transcript.call_args.args
    assert session_id == session_entry.session_id
    assert "No MCP tools available" in reload_msg["content"]
