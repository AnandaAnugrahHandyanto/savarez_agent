"""Detached-session liveness filter + reaper.

Regression coverage for the "N sessions" footer leak: ws disconnects used to
rebind a session's transport to stdio but never remove the ``_sessions`` entry,
so ``session.active_list`` counted every session ever opened against the gateway
and the count only reset on a gateway restart. The fix stamps ``detached_at`` on
disconnect, filters disconnected-idle sessions out of ``active_list`` after a
short grace, and reaps them — running the full ``session.close`` teardown
(finalize + unregister notify + ``AIAgent.close`` + slash worker) to reclaim the
agent's subprocesses/sandbox/browser/httpx resources.
"""

from __future__ import annotations

import threading
import time

import pytest

from tui_gateway import server


@pytest.fixture(autouse=True)
def _isolate_sessions():
    """Run each test against an empty, restored ``_sessions`` registry."""
    saved = dict(server._sessions)
    server._sessions.clear()
    try:
        yield
    finally:
        server._sessions.clear()
        server._sessions.update(saved)


def _mk(
    sid: str,
    *,
    running: bool = False,
    detached_at: float | None = None,
    last_active: float | None = None,
    **extra,
):
    if last_active is None:
        # A detached session went idle when its client left, so model
        # last_active as tracking detached_at unless a test overrides it (to
        # exercise the "detached but still running autonomous turns" guard).
        last_active = detached_at if detached_at is not None else time.time()
    session = {
        "session_key": sid,
        "agent": None,
        "history": [],
        "history_lock": threading.Lock(),
        "running": running,
        "created_at": time.time(),
        "last_active": last_active,
        "detached_at": detached_at,
        "slash_worker": None,
    }
    session.update(extra)
    server._sessions[sid] = session
    return session


def _old() -> float:
    return time.time() - (server._SESSION_REAP_AFTER_S + 60)


# ── _session_is_live ──────────────────────────────────────────────────────


def test_attached_session_is_live():
    assert server._session_is_live(_mk("a")) is True  # detached_at None == attached


def test_running_session_is_live_even_if_detached():
    s = _mk("a", running=True, detached_at=time.time() - 10_000)
    assert server._session_is_live(s) is True


def test_recently_detached_session_is_live_within_grace():
    s = _mk("a", detached_at=time.time() - 1)
    assert server._session_is_live(s) is True


def test_long_detached_idle_session_is_not_live():
    s = _mk("a", detached_at=time.time() - (server._SESSION_LIVE_GRACE_S + 5))
    assert server._session_is_live(s) is False


# ── session.active_list filtering ─────────────────────────────────────────


def test_active_list_drops_detached_idle_but_keeps_current(monkeypatch):
    # Keep the test independent of the heavy per-row builder (DB/agent/title).
    monkeypatch.setattr(
        server,
        "_session_live_item",
        lambda sid, sess, cur="": {"id": sid, "current": sid == cur},
    )

    _mk("live")  # attached
    _mk("run", running=True, detached_at=time.time() - 9_999)  # running
    _mk("fresh", detached_at=time.time() - 1)  # within grace
    _mk("stale", detached_at=_old())

    # 'stale' is the focused session -> must be kept despite being idle/detached.
    resp = server.handle_request(
        {
            "id": "1",
            "method": "session.active_list",
            "params": {"current_session_id": "stale"},
        }
    )
    ids = {row["id"] for row in resp["result"]["sessions"]}
    assert ids == {"live", "run", "fresh", "stale"}

    # Not focused -> the long-detached idle session drops out of the count.
    resp2 = server.handle_request(
        {"id": "2", "method": "session.active_list", "params": {}}
    )
    ids2 = {row["id"] for row in resp2["result"]["sessions"]}
    assert ids2 == {"live", "run", "fresh"}
    assert "stale" not in ids2


# ── _reap_detached_sessions ───────────────────────────────────────────────


def test_reaper_tears_down_only_idle_detached_sessions(monkeypatch):
    torn: list[str] = []
    monkeypatch.setattr(
        server,
        "_teardown_session",
        lambda sess, end_reason="": torn.append(sess.get("session_key")),
    )

    _mk("live")  # attached -> keep
    _mk("run", running=True, detached_at=_old())  # running -> keep
    _mk("fresh", detached_at=time.time() - 1)  # detached but recent -> keep
    _mk("stale", detached_at=_old())  # detached + idle -> reap

    assert server._reap_detached_sessions() == 1
    assert set(server._sessions) == {"live", "run", "fresh"}
    assert torn == ["stale"]


def test_reaper_keeps_detached_session_running_autonomous_turns(monkeypatch):
    # Finding-3 guard: a detached session whose notification poller / goal loop
    # keeps last_active fresh must NOT be reaped even though detached_at is old.
    monkeypatch.setattr(
        server,
        "_teardown_session",
        lambda *a, **k: pytest.fail("must not reap an actively-progressing session"),
    )
    _mk("auto", detached_at=_old(), last_active=time.time())
    assert server._reap_detached_sessions() == 0
    assert "auto" in server._sessions


def test_reaper_skips_session_that_reattached_before_sweep(monkeypatch):
    monkeypatch.setattr(
        server,
        "_teardown_session",
        lambda *a, **k: pytest.fail("must not reap a re-attached session"),
    )
    _mk("x", detached_at=_old())
    # Simulate a client re-attaching (prompt.submit/activate clears detached_at).
    server._sessions["x"]["detached_at"] = None

    assert server._reap_detached_sessions() == 0
    assert "x" in server._sessions


def test_reaper_closes_agent_worker_and_unregisters_notify(monkeypatch):
    # The whole point of the reaper is to reclaim the OS resources the agent
    # holds — assert it runs the full teardown, not just a DB finalize.
    monkeypatch.setattr(server, "_finalize_session", lambda *a, **k: None)
    unregistered: list[str] = []
    monkeypatch.setattr(
        "tools.approval.unregister_gateway_notify",
        lambda key: unregistered.append(key),
    )
    closed = {"agent": 0, "worker": 0}

    class _Agent:
        def close(self):
            closed["agent"] += 1

    class _Worker:
        def close(self):
            closed["worker"] += 1

    _mk("stale", detached_at=_old(), agent=_Agent(), slash_worker=_Worker())

    assert server._reap_detached_sessions() == 1
    assert "stale" not in server._sessions
    assert closed == {"agent": 1, "worker": 1}
    assert unregistered == ["stale"]


def test_reap_window_is_at_least_the_live_grace():
    # A session must stop counting as live (grace window) before it becomes
    # reapable, otherwise active_list could still show a session the reaper is
    # about to remove.
    assert server._SESSION_REAP_AFTER_S >= server._SESSION_LIVE_GRACE_S
