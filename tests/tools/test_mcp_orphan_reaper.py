"""Tests for the MCP orphan-reaper and tree-kill helpers.

Covers:
- HERMES_MCP_PARENT_PID tag is injected by _build_safe_env.
- _proc_descendant_pids walks /proc correctly (and degrades silently
  off-Linux).
- _reap_orphaned_mcp_children kills tagged processes whose parent has
  died and leaves processes whose parent is alive untouched.
"""

import os
import platform
import subprocess
import sys
import time

import pytest

from tools.mcp_tool import (
    _HERMES_MCP_PARENT_PID_VAR,
    _build_safe_env,
    _proc_descendant_pids,
    _reap_orphaned_mcp_children,
)


pytestmark = [
    pytest.mark.skipif(
        platform.system() != "Linux" or not os.path.isdir("/proc"),
        reason="Orphan reaper is Linux/proc-based",
    ),
    # The reaper exists to send real SIGKILLs; tests must be allowed to
    # do so even under the conftest live-system guard.  Each test scopes
    # its kills to subprocesses it spawns itself.
    pytest.mark.live_system_guard_bypass,
]


# ---------------------------------------------------------------------------
# _build_safe_env tag injection
# ---------------------------------------------------------------------------

def test_build_safe_env_injects_parent_pid_tag():
    env = _build_safe_env(user_env=None)
    assert env.get(_HERMES_MCP_PARENT_PID_VAR) == str(os.getpid())


def test_build_safe_env_user_env_overrides_tag_when_explicit():
    # If a server config explicitly sets the var (rare), the user wins.
    env = _build_safe_env(user_env={_HERMES_MCP_PARENT_PID_VAR: "99999"})
    assert env[_HERMES_MCP_PARENT_PID_VAR] == "99999"


# ---------------------------------------------------------------------------
# _proc_descendant_pids
# ---------------------------------------------------------------------------

def test_proc_descendant_pids_returns_empty_for_self_no_children():
    # No descendants for this test process (excluding pytest's runtime
    # state which is process-local; we only care that the call doesn't
    # explode and returns a list).
    result = _proc_descendant_pids(os.getpid())
    assert isinstance(result, list)
    # The current PID itself is never included.
    assert os.getpid() not in result


def test_proc_descendant_pids_finds_subprocess_tree():
    # Spawn shell that spawns sleep; verify both PIDs show in the tree.
    proc = subprocess.Popen(
        ["sh", "-c", "sleep 30 & wait"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Wait briefly for the inner `sleep` to spawn.
        time.sleep(0.4)
        descendants = _proc_descendant_pids(proc.pid)
        # The grandchild sleep should be reachable.
        assert any(
            "sleep" in _maybe_cmd(p)
            for p in descendants
        ), f"sleep grandchild not found in {descendants}"
    finally:
        proc.terminate()
        proc.wait(timeout=2)


def test_proc_descendant_pids_handles_nonexistent_pid():
    assert _proc_descendant_pids(4_194_300) == []


# ---------------------------------------------------------------------------
# _reap_orphaned_mcp_children
# ---------------------------------------------------------------------------

def test_reaper_kills_tagged_process_with_dead_parent():
    dead_parent = 4_194_300
    assert not os.path.isdir(f"/proc/{dead_parent}")  # sanity

    env = dict(os.environ)
    env[_HERMES_MCP_PARENT_PID_VAR] = str(dead_parent)
    orphan = subprocess.Popen(
        ["sleep", "60"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        assert orphan.poll() is None  # alive

        reaped = _reap_orphaned_mcp_children()
        assert reaped >= 1

        # Wait briefly for SIGKILL delivery.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if orphan.poll() is not None:
                break
            time.sleep(0.05)
        assert orphan.poll() is not None, "reaper did not kill the orphan"
    finally:
        if orphan.poll() is None:
            orphan.kill()
            orphan.wait(timeout=2)


def test_reaper_leaves_tagged_process_with_live_parent_alone():
    env = dict(os.environ)
    env[_HERMES_MCP_PARENT_PID_VAR] = str(os.getpid())  # we are alive
    keeper = subprocess.Popen(
        ["sleep", "5"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        assert keeper.poll() is None

        # Reaper run should NOT touch this — our PID is alive.
        before = keeper.poll()
        _reap_orphaned_mcp_children()
        time.sleep(0.5)
        after = keeper.poll()
        assert before is None and after is None, "reaper killed a live-parent child"
    finally:
        keeper.terminate()
        try:
            keeper.wait(timeout=2)
        except subprocess.TimeoutExpired:
            keeper.kill()
            keeper.wait(timeout=2)


def test_reaper_ignores_processes_without_tag():
    # Plain sleep without the env var should be invisible to the reaper.
    plain = subprocess.Popen(
        ["sleep", "5"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.2)
        _reap_orphaned_mcp_children()
        time.sleep(0.3)
        assert plain.poll() is None, "reaper killed a process without the tag"
    finally:
        plain.terminate()
        try:
            plain.wait(timeout=2)
        except subprocess.TimeoutExpired:
            plain.kill()
            plain.wait(timeout=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_cmd(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return ""
