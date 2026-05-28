"""Regression tests for the MCP shell-like tool approval gate (#32877).

Before this gate existed, ``tools/approval.py`` was only wired into
``tools/terminal_tool.py``.  Any destructive command issued through a
shell-wrapping MCP server (``ssh``, ``docker``, the official
``@modelcontextprotocol/server-shell``, etc.) bypassed the dangerous-
command + Smart-mode + hardline pipeline entirely — no regex check, no
approval prompt, no audit trail.

The fix in ``tools/mcp_tool.py`` adds a transport-layer gate:

* If the MCP tool's name matches a known shell/exec fragment
  (``shell``, ``bash``, ``exec``, ``run_command``, ``execute``, …),
* AND the arguments expose a command-shaped field (``command``, ``cmd``,
  ``args``, ``script``, …),
* the candidate command is routed through ``check_all_command_guards``
  with ``env_type="local"`` BEFORE ``server.session.call_tool`` is
  invoked.

These tests lock in that behavior end-to-end via the existing tool
handler factory, mirroring the patterns used in ``test_mcp_tool.py``
and ``test_mcp_circuit_breaker.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers (mirrored from tests/tools/test_mcp_tool.py)
# ---------------------------------------------------------------------------


def _make_call_result(text: str = "ok", is_error: bool = False):
    block = SimpleNamespace(text=text)
    return SimpleNamespace(content=[block], isError=is_error, structuredContent=None)


def _install_stub_server(mcp_tool, name: str, call_tool: AsyncMock):
    from tools.mcp_tool import MCPServerTask

    server = MCPServerTask(name)
    session = MagicMock()
    session.call_tool = call_tool
    server.session = session
    mcp_tool._servers[name] = server
    mcp_tool._server_error_counts.pop(name, None)
    if hasattr(mcp_tool, "_server_breaker_opened_at"):
        mcp_tool._server_breaker_opened_at.pop(name, None)
    return server


def _patch_mcp_loop():
    def fake_run(coro_or_factory, timeout=30):
        coro = coro_or_factory() if callable(coro_or_factory) else coro_or_factory
        return asyncio.run(coro)

    return patch("tools.mcp_tool._run_on_mcp_loop", side_effect=fake_run)


@pytest.fixture(autouse=True)
def _reset_approval_state():
    """Approval state is process-global; reset around every test."""
    from tools import approval

    saved = {
        k: os.environ.get(k)
        for k in (
            "HERMES_INTERACTIVE",
            "HERMES_GATEWAY_SESSION",
            "HERMES_YOLO_MODE",
            "HERMES_CRON_SESSION",
            "HERMES_SESSION_KEY",
        )
    }
    for k in list(saved):
        os.environ.pop(k, None)
    approval._session_approved.clear()
    approval._session_yolo.clear()
    approval._permanent_approved.clear()
    approval._pending.clear()
    approval._gateway_queues.clear()
    approval._gateway_notify_cbs.clear()
    yield
    approval._session_approved.clear()
    approval._session_yolo.clear()
    approval._permanent_approved.clear()
    approval._pending.clear()
    approval._gateway_queues.clear()
    approval._gateway_notify_cbs.clear()
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ---------------------------------------------------------------------------
# Pure-helper coverage
# ---------------------------------------------------------------------------


class TestShellLikeDetection:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "shell",
            "bash",
            "exec",
            "execute",
            "execute_command",
            "run_command",
            "runShell",
            "docker_exec",
            "ssh_exec",
            "subprocess_run",
            "spawn_process",
        ],
    )
    def test_shell_like_names_detected(self, tool_name):
        from tools.mcp_tool import _is_shell_like_mcp_tool

        assert _is_shell_like_mcp_tool(tool_name) is True

    @pytest.mark.parametrize(
        "tool_name",
        ["read_file", "search_web", "list_resources", "get_weather", "", "fetch_url"],
    )
    def test_safe_names_not_detected(self, tool_name):
        from tools.mcp_tool import _is_shell_like_mcp_tool

        assert _is_shell_like_mcp_tool(tool_name) is False


class TestCommandExtraction:
    def test_command_key(self):
        from tools.mcp_tool import _extract_mcp_command_payload

        assert _extract_mcp_command_payload({"command": "ls -la"}) == "ls -la"

    def test_cmd_key(self):
        from tools.mcp_tool import _extract_mcp_command_payload

        assert _extract_mcp_command_payload({"cmd": "whoami"}) == "whoami"

    def test_argv_list_is_joined(self):
        from tools.mcp_tool import _extract_mcp_command_payload

        payload = _extract_mcp_command_payload({"argv": ["rm", "-rf", "/tmp/x"]})
        assert payload == "rm -rf /tmp/x"

    def test_returns_none_when_no_command_key(self):
        from tools.mcp_tool import _extract_mcp_command_payload

        assert _extract_mcp_command_payload({"path": "/tmp/foo"}) is None

    def test_returns_none_for_non_dict(self):
        from tools.mcp_tool import _extract_mcp_command_payload

        assert _extract_mcp_command_payload(None) is None
        assert _extract_mcp_command_payload("ls") is None
        assert _extract_mcp_command_payload([1, 2, 3]) is None


# ---------------------------------------------------------------------------
# End-to-end handler behavior — the actual #32877 regression
# ---------------------------------------------------------------------------


class TestHandlerApprovalGate:
    def test_hardline_command_blocks_before_mcp_call(self):
        """``rm -rf /`` through a shell-MCP must NEVER reach the server."""
        from tools import mcp_tool

        call_tool = AsyncMock()
        _install_stub_server(mcp_tool, "ssh", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("ssh", "execute_command", 30)
            with _patch_mcp_loop():
                raw = handler({"command": "rm -rf /"})
            parsed = json.loads(raw)
            assert "error" in parsed
            assert "BLOCKED" in parsed["error"]
            assert "hardline" in parsed["error"].lower()
            # Critical: the MCP session was never invoked.
            call_tool.assert_not_called()
        finally:
            mcp_tool._servers.pop("ssh", None)

    def test_dangerous_command_blocked_in_gateway_when_user_denies(self):
        """Smart/manual mode in a gateway session must gate dangerous MCP calls."""
        from tools import approval, mcp_tool

        os.environ["HERMES_GATEWAY_SESSION"] = "1"
        os.environ["HERMES_SESSION_KEY"] = "test-session-32877"

        # Register a notify callback that immediately denies — simulates
        # the user clicking "Deny" on the gateway approval prompt.
        def deny(_data):
            approval.resolve_gateway_approval("test-session-32877", "deny")

        approval.register_gateway_notify("test-session-32877", deny)

        # Pin gateway timeout short so a regression that fails to wire
        # the gate doesn't hang the test suite.
        with patch.object(
            approval,
            "_get_approval_config",
            return_value={"mode": "manual", "gateway_timeout": 5, "timeout": 5},
        ):
            call_tool = AsyncMock()
            _install_stub_server(mcp_tool, "docker", call_tool)
            try:
                handler = mcp_tool._make_tool_handler("docker", "exec_in_container", 30)
                with _patch_mcp_loop():
                    raw = handler({"command": "rm -rf /home/user"})
                parsed = json.loads(raw)
                assert "error" in parsed
                assert "BLOCKED" in parsed["error"]
                # Critical: the MCP session was never invoked.
                call_tool.assert_not_called()
            finally:
                mcp_tool._servers.pop("docker", None)
                approval.unregister_gateway_notify("test-session-32877")

    def test_safe_mcp_tool_call_passes_through_unchanged(self):
        """Non-shell-like MCP tools must NOT be gated."""
        from tools import mcp_tool

        call_tool = AsyncMock(return_value=_make_call_result("file body", is_error=False))
        _install_stub_server(mcp_tool, "fs", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("fs", "read_file", 30)
            with _patch_mcp_loop():
                raw = handler({"path": "/tmp/safe.txt"})
            parsed = json.loads(raw)
            assert parsed["result"] == "file body"
            call_tool.assert_called_once_with("read_file", arguments={"path": "/tmp/safe.txt"})
        finally:
            mcp_tool._servers.pop("fs", None)

    def test_shell_tool_with_safe_command_passes_through(self):
        """``ls -la`` through a shell-MCP is fine — only dangerous patterns block."""
        from tools import mcp_tool

        call_tool = AsyncMock(return_value=_make_call_result("listing", is_error=False))
        _install_stub_server(mcp_tool, "ssh", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("ssh", "execute_command", 30)
            with _patch_mcp_loop():
                raw = handler({"command": "ls -la /tmp"})
            parsed = json.loads(raw)
            assert parsed["result"] == "listing"
            call_tool.assert_called_once()
        finally:
            mcp_tool._servers.pop("ssh", None)

    def test_shell_tool_without_command_field_passes_through(self):
        """A shell-named tool with no recognizable command arg isn't gated.

        Some MCPs expose ``run_*``-named tools that don't actually take a
        shell command (e.g. a ``run_query`` tool taking SQL).  Without a
        command-shaped argument we can't scan, so we let the call through
        rather than firing a false-positive block.
        """
        from tools import mcp_tool

        call_tool = AsyncMock(return_value=_make_call_result("rows", is_error=False))
        _install_stub_server(mcp_tool, "db", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("db", "run_query", 30)
            with _patch_mcp_loop():
                raw = handler({"sql": "SELECT 1"})
            parsed = json.loads(raw)
            assert parsed["result"] == "rows"
            call_tool.assert_called_once()
        finally:
            mcp_tool._servers.pop("db", None)

    def test_yolo_mode_bypasses_gate(self):
        """YOLO must propagate to the MCP gate, not just terminal_tool."""
        from tools import approval, mcp_tool

        os.environ["HERMES_SESSION_KEY"] = "yolo-session"
        approval.enable_session_yolo("yolo-session")

        call_tool = AsyncMock(return_value=_make_call_result("done", is_error=False))
        _install_stub_server(mcp_tool, "ssh", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("ssh", "execute_command", 30)
            with _patch_mcp_loop():
                raw = handler({"command": "rm -rf /tmp/scratch"})
            parsed = json.loads(raw)
            # YOLO lets the regular dangerous pattern through, but NOT
            # the hardline list (rm -rf /). /tmp/scratch is dangerous-
            # but-recoverable, so YOLO should let it pass.
            assert parsed.get("result") == "done"
            call_tool.assert_called_once()
        finally:
            mcp_tool._servers.pop("ssh", None)
            approval.disable_session_yolo("yolo-session")

    def test_yolo_does_not_bypass_hardline(self):
        """Hardline floor (rm -rf /) must hold even with YOLO."""
        from tools import approval, mcp_tool

        os.environ["HERMES_SESSION_KEY"] = "yolo-session-2"
        approval.enable_session_yolo("yolo-session-2")

        call_tool = AsyncMock()
        _install_stub_server(mcp_tool, "ssh", call_tool)

        try:
            handler = mcp_tool._make_tool_handler("ssh", "execute_command", 30)
            with _patch_mcp_loop():
                raw = handler({"command": "rm -rf /"})
            parsed = json.loads(raw)
            assert "error" in parsed
            assert "hardline" in parsed["error"].lower()
            call_tool.assert_not_called()
        finally:
            mcp_tool._servers.pop("ssh", None)
            approval.disable_session_yolo("yolo-session-2")
