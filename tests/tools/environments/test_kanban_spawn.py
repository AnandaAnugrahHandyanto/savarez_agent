"""Tests for the WorkerRuntime protocol + builtin runtimes (D1 Task 1)."""
from __future__ import annotations

import os
import signal
import time
from unittest.mock import MagicMock

import pytest

from tools.environments.kanban_spawn import (
    LocalRuntime,
    WorkerRuntime,
    load_runtime,
    register_runtime,
)


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------

def test_load_runtime_default_returns_local():
    rt = load_runtime("local", {})
    assert isinstance(rt, LocalRuntime)
    assert rt.name == "local"


def test_load_runtime_unknown_raises():
    with pytest.raises(ValueError, match="unknown worker_runtime"):
        load_runtime("does-not-exist", {})


def test_load_runtime_passes_cfg():
    """Config dict reaches the runtime constructor."""
    rt = load_runtime("local", {"future_key": "future_value"})
    # LocalRuntime stashes config for future use; just verify no crash
    assert rt._cfg == {"future_key": "future_value"}


def test_load_runtime_none_cfg_is_safe():
    rt = load_runtime("local", None)
    assert rt._cfg == {}


def test_register_runtime_blocks_duplicates():
    """Re-registering a name is a bug; raise loudly."""
    class _Stub:
        name = "stub-test-dup"
        def __init__(self, cfg): pass
        def spawn(self, *a, **kw): return None
        def is_alive(self, h): return False
        def terminate(self, h, reason=""): pass

    register_runtime("__test_register_dup__", _Stub)
    with pytest.raises(ValueError, match="already registered"):
        register_runtime("__test_register_dup__", _Stub)
    # Cleanup
    from tools.environments.kanban_spawn import _RUNTIMES
    _RUNTIMES.pop("__test_register_dup__", None)


# ---------------------------------------------------------------------------
# LocalRuntime delegation
# ---------------------------------------------------------------------------

def test_local_runtime_delegates_to_default_spawn(monkeypatch):
    """LocalRuntime.spawn must call kanban_db._default_spawn unchanged.

    This is the regression-safety guarantee — `worker_runtime: local` is
    byte-identical to pre-D1 behavior.
    """
    rt = LocalRuntime({})

    fake_pid = 4242
    captured = {}

    def fake_default_spawn(task, workspace, *, board=None):
        captured["task"] = task
        captured["workspace"] = workspace
        captured["board"] = board
        return fake_pid

    monkeypatch.setattr(
        "hermes_cli.kanban_db._default_spawn", fake_default_spawn
    )

    fake_task = MagicMock()
    fake_task.id = "t_test001"
    pid = rt.spawn(fake_task, workspace="/tmp/ws", board="main")

    assert pid == fake_pid
    assert captured["task"] is fake_task
    assert captured["workspace"] == "/tmp/ws"
    assert captured["board"] == "main"


def test_local_runtime_passes_through_none_board(monkeypatch):
    """When board=None is passed, default_spawn receives board=None."""
    rt = LocalRuntime({})
    captured = {}

    def fake_default_spawn(task, workspace, *, board=None):
        captured["board"] = board
        return 1

    monkeypatch.setattr(
        "hermes_cli.kanban_db._default_spawn", fake_default_spawn
    )
    rt.spawn(MagicMock(id="t_x"), workspace="/tmp")
    assert captured["board"] is None


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_worker_runtime_protocol_methods(monkeypatch):
    """LocalRuntime exposes the WorkerRuntime contract."""
    rt = LocalRuntime({})
    assert hasattr(rt, "name")
    assert hasattr(rt, "spawn")
    assert hasattr(rt, "is_alive")
    assert hasattr(rt, "terminate")
    # is_alive on an obviously-dead PID returns False without raising.
    # Mock os.kill to avoid the test-suite's live-system guard on
    # out-of-subtree PIDs.
    monkeypatch.setattr(os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    assert rt.is_alive(handle=999999999) is False


def test_local_runtime_is_alive_handles_bad_input():
    """is_alive is robust against non-integer / negative input."""
    rt = LocalRuntime({})
    assert rt.is_alive(0) is False
    assert rt.is_alive(-1) is False
    assert rt.is_alive("not-a-pid") is False
    assert rt.is_alive(None) is False  # type: ignore[arg-type]


def test_local_runtime_is_alive_returns_true_for_self():
    """The current Python process is alive."""
    rt = LocalRuntime({})
    assert rt.is_alive(os.getpid()) is True


def test_local_runtime_terminate_handles_dead_pid_silently(monkeypatch):
    """terminate() on an already-dead PID does not raise.

    Mocks os.kill to raise ProcessLookupError, which terminate() must swallow.
    Test-suite's live-system guard would otherwise block os.kill on out-of-subtree PIDs.
    """
    rt = LocalRuntime({})

    def _raise_dead(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(os, "kill", _raise_dead)
    rt.terminate(999999999, reason="test")
    # No exception raised → pass.


def test_local_runtime_terminate_handles_bad_input():
    """terminate() on non-integer / negative input is a no-op."""
    rt = LocalRuntime({})
    rt.terminate(0, reason="zero")
    rt.terminate(-1, reason="neg")
    rt.terminate("not-a-pid", reason="str")
    rt.terminate(None, reason="none")  # type: ignore[arg-type]
    # No exceptions → pass.


def test_local_runtime_terminate_actually_signals(monkeypatch):
    """terminate() calls os.kill(pid, SIGTERM) for a valid PID."""
    rt = LocalRuntime({})
    captured = {}

    def fake_kill(pid, sig):
        captured["pid"] = pid
        captured["sig"] = sig

    monkeypatch.setattr(os, "kill", fake_kill)
    rt.terminate(12345, reason="test")
    assert captured["pid"] == 12345
    assert captured["sig"] == signal.SIGTERM
