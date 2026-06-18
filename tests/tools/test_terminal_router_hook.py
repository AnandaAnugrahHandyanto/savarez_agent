"""Tests for the Phase 2 Hermes resource-router hook in terminal_tool.

These cover three layers:
  * ``_should_route_command`` — the gate that decides whether a call is routed.
  * ``_route_command_via_dispatch`` — the subprocess call + envelope mapping +
    graceful fallback behavior.
  * ``terminal_tool`` — that a matching call actually triggers routing and
    returns the dispatcher's mapped envelope without touching local execution.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import tools.terminal_tool as tt
from tools.terminal_tool import (
    _route_command_via_dispatch,
    _should_route_command,
    terminal_tool,
)


HOMELAB_HOME = "/home/ubuntu/.hermes/profiles/homelab"


@pytest.fixture
def homelab_env(monkeypatch):
    """Put the process in the homelab profile with routing un-suppressed."""
    monkeypatch.setenv("HERMES_HOME", HOMELAB_HOME)
    monkeypatch.setenv(tt.HERMES_RESOURCE_ROUTER_TERMINAL_ENV, "1")
    monkeypatch.delenv("HERMES_INTERNAL_ROUTED", raising=False)


# ---------------------------------------------------------------------------
# _should_route_command
# ---------------------------------------------------------------------------
class TestShouldRouteCommand:
    def test_routes_under_homelab_profile(self, homelab_env):
        assert _should_route_command("ls -la /tmp") is True

    def test_not_routed_off_homelab_profile(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", "/home/ubuntu/.hermes/profiles/default")
        monkeypatch.delenv("HERMES_INTERNAL_ROUTED", raising=False)
        assert _should_route_command("ls -la /tmp") is False

    def test_not_routed_when_home_unset(self, monkeypatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.delenv("HERMES_INTERNAL_ROUTED", raising=False)
        assert _should_route_command("ls -la /tmp") is False

    def test_not_routed_unless_explicitly_enabled(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", HOMELAB_HOME)
        monkeypatch.delenv(tt.HERMES_RESOURCE_ROUTER_TERMINAL_ENV, raising=False)
        monkeypatch.delenv("HERMES_INTERNAL_ROUTED", raising=False)
        assert _should_route_command("ls -la /tmp") is False

    def test_not_routed_when_internal_routed(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", HOMELAB_HOME)
        monkeypatch.setenv("HERMES_INTERNAL_ROUTED", "1")
        assert _should_route_command("ls -la /tmp") is False

    def test_not_routed_when_command_mentions_router(self, homelab_env):
        # Guards the dispatcher (which shells out) from recursing into routing.
        assert _should_route_command("python3 hermes_router_dispatch.py x x") is False
        assert _should_route_command("cat Scripts/hermes_router_score.py") is False

    @pytest.mark.parametrize("bad", [None, 123, "", "   "])
    def test_not_routed_for_invalid_or_empty_command(self, homelab_env, bad):
        assert _should_route_command(bad) is False


# ---------------------------------------------------------------------------
# _route_command_via_dispatch — envelope mapping + fallback
# ---------------------------------------------------------------------------
def _make_proc(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestRouteCommandViaDispatch:
    def test_completed_maps_to_success(self):
        dispatch_json = json.dumps({
            "status": "completed",
            "selected_worker": "ds8",
            "task_class": "build",
            "routing_reason": "scored best",
            "stdout": "hello\n",
            "stderr": "",
        })
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          return_value=_make_proc(0, dispatch_json)) as run:
            result = _route_command_via_dispatch("echo hello", timeout=30)

        assert result is not None
        envelope = json.loads(result)
        assert envelope == {
            "output": "hello\n",
            "exit_code": 0,
            "error": "",
            "status": "success",
        }

        # The dispatcher was invoked with command as BOTH prompt and command,
        # and the recursion-guard env var was set on a *copied* environment.
        called_args, called_kwargs = run.call_args
        argv = called_args[0]
        assert argv[1] == tt.HERMES_ROUTER_DISPATCH_SCRIPT
        assert argv[2] == "echo hello"  # prompt
        assert argv[3] == "echo hello"  # command
        assert called_kwargs["env"]["HERMES_INTERNAL_ROUTED"] == "1"

    def test_failed_status_maps_to_error_exit_1(self):
        dispatch_json = json.dumps({
            "status": "failed",
            "selected_worker": "ds9",
            "task_class": "build",
            "routing_reason": "",
            "stdout": "partial",
            "stderr": "boom",
        })
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          return_value=_make_proc(0, dispatch_json)):
            result = _route_command_via_dispatch("make", timeout=30)

        envelope = json.loads(result)
        assert envelope["status"] == "error"
        assert envelope["exit_code"] == 1
        assert envelope["error"] == "boom"
        assert envelope["output"] == "partial"

    def test_missing_script_falls_back(self):
        with patch.object(tt.os.path, "isfile", return_value=False):
            assert _route_command_via_dispatch("echo hi") is None

    def test_invalid_json_falls_back(self):
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          return_value=_make_proc(0, "not json{")):
            assert _route_command_via_dispatch("echo hi") is None

    def test_nonzero_dispatcher_exit_falls_back(self):
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          return_value=_make_proc(2, "", "traceback")):
            assert _route_command_via_dispatch("echo hi") is None

    def test_timeout_falls_back(self):
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          side_effect=tt.subprocess.TimeoutExpired("cmd", 1)):
            assert _route_command_via_dispatch("echo hi") is None

    def test_json_missing_status_falls_back(self):
        with patch.object(tt.os.path, "isfile", return_value=True), \
             patch.object(tt.subprocess, "run",
                          return_value=_make_proc(0, json.dumps({"stdout": "x"}))):
            assert _route_command_via_dispatch("echo hi") is None


# ---------------------------------------------------------------------------
# terminal_tool integration — routing actually triggers
# ---------------------------------------------------------------------------
class TestTerminalToolRoutingTrigger:
    def test_matching_call_routes_and_returns_envelope(self, homelab_env):
        sentinel = json.dumps({
            "output": "routed",
            "exit_code": 0,
            "error": "",
            "status": "success",
        })
        with patch.object(tt, "_route_command_via_dispatch",
                          return_value=sentinel) as dispatch, \
             patch.object(tt, "_get_env_config") as get_cfg:
            result = terminal_tool("ls -la")

        assert result == sentinel
        dispatch.assert_called_once()
        assert dispatch.call_args[0][0] == "ls -la"
        # Routing short-circuits before any environment setup.
        get_cfg.assert_not_called()

    def test_fallthrough_to_local_when_dispatch_returns_none(self, homelab_env):
        # When the router declines (returns None), terminal_tool proceeds to
        # normal local execution rather than aborting.
        with patch.object(tt, "_route_command_via_dispatch",
                          return_value=None) as dispatch:
            result = terminal_tool("echo local-path")

        dispatch.assert_called_once()
        envelope = json.loads(result)
        assert "local-path" in envelope.get("output", "")
        assert envelope.get("exit_code") == 0

    def test_off_profile_does_not_route(self, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", "/home/ubuntu/.hermes/profiles/default")
        monkeypatch.setenv(tt.HERMES_RESOURCE_ROUTER_TERMINAL_ENV, "1")
        monkeypatch.delenv("HERMES_INTERNAL_ROUTED", raising=False)
        with patch.object(tt, "_route_command_via_dispatch") as dispatch:
            terminal_tool("echo no-route")
        dispatch.assert_not_called()

    def test_background_call_not_routed(self, homelab_env):
        # Background lifecycle can't be honored by the synchronous dispatcher,
        # so routing is skipped. _get_env_config is stubbed to raise so the
        # call short-circuits cheaply without real environment setup; whether
        # terminal_tool swallows the error or not, dispatch must not be called.
        with patch.object(tt, "_route_command_via_dispatch") as dispatch, \
             patch.object(tt, "_get_env_config",
                          side_effect=RuntimeError("stop")):
            terminal_tool("sleep 100", background=True)
        dispatch.assert_not_called()
