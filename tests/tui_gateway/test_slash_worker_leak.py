"""Regression tests for the slash_worker subprocess leak.

A long-lived dashboard accumulated orphaned ``tui_gateway.slash_worker``
subprocesses (live + ``<defunct>`` zombies) because sessions whose WebSocket
transport dropped were never finalized and their workers never closed/reaped.

These tests pin the three lifecycle guarantees of the fix:

* a transport disconnect terminates the session's slash worker (no live leak),
  while keeping the session warm for in-place resume;
* a worker's drain thread reaps the child on death (no ``<defunct>`` zombies);
* terminal ``_finalize_session`` closes the worker (unified teardown).
"""

import asyncio
import queue
import types

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def server():
    with patch.dict("sys.modules", {
        "hermes_constants": MagicMock(get_hermes_home=MagicMock(return_value="/tmp/hermes_test")),
        "hermes_cli.env_loader": MagicMock(),
        "hermes_cli.banner": MagicMock(),
        "hermes_state": MagicMock(),
    }):
        import importlib
        mod = importlib.import_module("tui_gateway.server")
        yield mod
        mod._sessions.clear()


class _FakeWorker:
    """Stand-in for ``_SlashWorker`` exposing the bits the lifecycle touches."""

    def __init__(self):
        self.closed = 0
        # Starts "alive"; close() flips poll() to a return code, like the real one.
        self._rc = None
        self.proc = types.SimpleNamespace(poll=lambda: self._rc)

    def close(self):
        self.closed += 1
        self._rc = -15  # terminated


# ── 1. transport disconnect must terminate the worker (live-leak fix) ────────


def test_detach_transport_terminates_and_nulls_worker(server):
    worker = _FakeWorker()
    transport = object()
    server._sessions["sid"] = {
        "session_key": "sid",
        "transport": transport,
        "slash_worker": worker,
    }

    detached = server._detach_transport(transport)

    assert detached == 1
    # Worker subprocess torn down — this is the leak that was accumulating.
    assert worker.closed == 1
    assert server._sessions["sid"]["slash_worker"] is None
    # Session stays warm (transport falls back to stdio) so resume still works.
    assert server._sessions["sid"]["transport"] is server._stdio_transport
    assert "sid" in server._sessions


def test_detach_transport_ignores_other_sessions(server):
    mine = _FakeWorker()
    theirs = _FakeWorker()
    dropped = object()
    other = object()
    server._sessions["a"] = {"session_key": "a", "transport": dropped, "slash_worker": mine}
    server._sessions["b"] = {"session_key": "b", "transport": other, "slash_worker": theirs}

    server._detach_transport(dropped)

    assert mine.closed == 1
    assert theirs.closed == 0  # untouched — its socket is still live
    assert server._sessions["b"]["slash_worker"] is theirs


def test_handle_ws_disconnect_terminates_session_worker(server):
    """End-to-end: a session whose WebSocket drops must have its worker closed."""
    from tui_gateway import ws as ws_mod

    captured = {}
    real_transport_cls = ws_mod.WSTransport

    class _CapturingTransport(real_transport_cls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["t"] = self

    worker = _FakeWorker()
    state = {"step": 0}

    class _FakeWS:
        client = types.SimpleNamespace(host="t", port=1)

        async def accept(self):
            return None

        async def send_text(self, _line):
            return None

        async def receive_text(self):
            if state["step"] == 0:
                state["step"] = 1
                # Bind a session to the live transport, then disconnect next read.
                server._sessions["sid"] = {
                    "session_key": "sid",
                    "transport": captured["t"],
                    "slash_worker": worker,
                }
                return ""  # blank line → loop continues without dispatch
            raise ws_mod._WebSocketDisconnect()

        async def close(self):
            return None

    with patch.object(ws_mod, "WSTransport", _CapturingTransport):
        asyncio.run(ws_mod.handle_ws(_FakeWS()))

    assert worker.closed == 1
    assert server._sessions["sid"]["slash_worker"] is None
    assert server._sessions["sid"]["transport"] is server._stdio_transport


# ── 2. drain thread must reap the child on death (zombie fix) ────────────────


def test_drain_stdout_reaps_worker_on_eof(server):
    """When the worker's stdout EOFs (child exited), the drain thread must
    ``wait()`` the child so it is reaped instead of left as ``<defunct>``."""
    worker = server._SlashWorker.__new__(server._SlashWorker)
    worker.stdout_queue = queue.Queue()

    waited = {"n": 0}

    class _Proc:
        stdout = iter(['{"id": 1, "ok": true, "output": "hi"}\n'])

        def wait(self):
            waited["n"] += 1
            return 0

    worker.proc = _Proc()

    worker._drain_stdout()

    # Message parsed and forwarded, then the None sentinel.
    assert worker.stdout_queue.get_nowait() == {"id": 1, "ok": True, "output": "hi"}
    assert worker.stdout_queue.get_nowait() is None
    # Child reaped exactly once — the missing piece that produced zombies.
    assert waited["n"] == 1


# ── 3. terminal finalize must close the worker (unified teardown) ────────────


def test_finalize_session_closes_worker(server, monkeypatch):
    monkeypatch.setattr(server, "_notify_session_boundary", lambda *a, **k: None)
    monkeypatch.setattr(server, "_get_db", lambda: None)

    worker = _FakeWorker()
    session = {
        "session_key": "sid",
        "agent": types.SimpleNamespace(session_id="sid"),
        "history": [],
        "slash_worker": worker,
    }

    server._finalize_session(session)

    assert worker.closed == 1
    assert session["slash_worker"] is None


def test_finalize_session_is_idempotent(server, monkeypatch):
    monkeypatch.setattr(server, "_notify_session_boundary", lambda *a, **k: None)
    monkeypatch.setattr(server, "_get_db", lambda: None)

    worker = _FakeWorker()
    session = {
        "session_key": "sid",
        "agent": types.SimpleNamespace(session_id="sid"),
        "history": [],
        "slash_worker": worker,
    }

    server._finalize_session(session)
    server._finalize_session(session)  # second call must be a no-op

    assert worker.closed == 1
