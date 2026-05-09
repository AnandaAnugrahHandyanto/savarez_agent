"""Gate 0 long-running Kanban workflow harness tests.

These tests intentionally stay at the SQLite/kernel seam: no live gateway,
no live ~/.hermes DB, and no real Hermes worker process. The goal is to pin
the trust boundary for long-running work before adding higher-level harness
telemetry.
"""

from __future__ import annotations

import hashlib
import os
import signal
import time
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Use an isolated Hermes home so tests never touch live kanban.db."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _host_local_claimer(worker_name: str) -> str:
    host = kb._claimer_id().split(":", 1)[0]
    return f"{host}:{worker_name}"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_dirty_stale_reclaim_sigkills_worker_and_preserves_context(kanban_home, monkeypatch):
    """R-02: stale long-running work is safely reclaimed.

    Worker-1 claims and heartbeats a task, then its claim expires while the
    worker is still apparently alive. Reclaim should terminate the host-local
    pid, close worker-1's run as reclaimed, put the same task back to ready,
    and preserve the task context for worker-2.
    """
    body = "long-running payload: context survives dirty reclaim"
    expected_checksum = _checksum(body)
    sent_signals: list[tuple[int, signal.Signals]] = []
    state = {"sigkill_sent": False}

    def fake_pid_alive(pid: int) -> bool:
        # Stay alive after SIGTERM so reclaim escalates to SIGKILL; become
        # dead immediately after SIGKILL without sleeping in real time.
        return not state["sigkill_sent"]

    def fake_signal(pid: int, sig: signal.Signals) -> None:
        sent_signals.append((pid, sig))
        if sig == signal.SIGKILL:
            state["sigkill_sent"] = True

    monkeypatch.setattr(kb, "_pid_alive", fake_pid_alive)
    monkeypatch.setattr(kb.time, "sleep", lambda _seconds: None)

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="gate0 dirty reclaim", body=body, assignee="worker")

        worker1 = _host_local_claimer("worker-1")
        first_claim = kb.claim_task(conn, tid, ttl_seconds=-1, claimer=worker1)
        assert first_claim is not None
        run1_id = first_claim.current_run_id
        assert run1_id is not None
        kb._set_worker_pid(conn, tid, 424242)
        assert kb.heartbeat_worker(conn, tid, note="worker-1 still alive", expected_run_id=run1_id)

        reclaimed = kb.release_stale_claims(conn, signal_fn=fake_signal)
        assert reclaimed == 1
        assert sent_signals == [(424242, signal.SIGTERM), (424242, signal.SIGKILL)]

        ready = kb.get_task(conn, tid)
        assert ready.status == "ready"
        assert ready.claim_lock is None
        assert ready.claim_expires is None
        assert ready.worker_pid is None
        assert _checksum(ready.body or "") == expected_checksum

        run1 = kb.get_run(conn, run1_id)
        assert run1.status == "reclaimed"
        assert run1.outcome == "reclaimed"
        assert run1.ended_at is not None
        assert run1.metadata["sigkill"] is True

        events = kb.list_events(conn, tid)
        assert any(e.kind == "heartbeat" and e.run_id == run1_id for e in events)
        assert any(e.kind == "reclaimed" and e.run_id == run1_id for e in events)

        worker2 = _host_local_claimer("worker-2")
        second_claim = kb.claim_task(conn, tid, ttl_seconds=60, claimer=worker2)
        assert second_claim is not None
        assert second_claim.id == tid
        assert second_claim.current_run_id != run1_id
        assert second_claim.claim_lock == worker2
        assert second_claim.body == body
        assert _checksum(second_claim.body or "") == expected_checksum

        active_runs = [r for r in kb.list_runs(conn, tid) if r.ended_at is None]
        assert [r.id for r in active_runs] == [second_claim.current_run_id]
    finally:
        conn.close()


def test_zombie_crash_detection_requeues_for_second_worker(kanban_home, monkeypatch):
    """Z-01: vanished/zombie worker pids requeue the same task once.

    The first run has a host-local worker pid that is no longer alive. Crash
    detection should close that run, emit a crashed event, and make the task
    claimable by worker-2 without losing the original body/checksum.
    """
    body = "zombie worker payload: retry me with identical context"
    expected_checksum = _checksum(body)

    monkeypatch.setattr(kb, "_pid_alive", lambda _pid: False)
    monkeypatch.setattr(kb, "_classify_worker_exit", lambda _pid: ("signaled", signal.SIGKILL))

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="gate0 zombie requeue", body=body, assignee="worker")

        worker1 = _host_local_claimer("worker-1")
        first_claim = kb.claim_task(conn, tid, ttl_seconds=300, claimer=worker1)
        assert first_claim is not None
        run1_id = first_claim.current_run_id
        assert run1_id is not None
        kb._set_worker_pid(conn, tid, 515151)
        assert kb.heartbeat_worker(conn, tid, note="last worker-1 heartbeat", expected_run_id=run1_id)

        crashed = kb.detect_crashed_workers(conn)
        assert crashed == [tid]

        ready = kb.get_task(conn, tid)
        assert ready.status == "ready"
        assert ready.claim_lock is None
        assert ready.worker_pid is None
        assert ready.consecutive_failures == 1
        assert _checksum(ready.body or "") == expected_checksum

        run1 = kb.get_run(conn, run1_id)
        assert run1.status == "crashed"
        assert run1.outcome == "crashed"
        assert run1.ended_at is not None
        assert "signal" in (run1.error or "")

        events = kb.list_events(conn, tid)
        crashed_events = [e for e in events if e.kind == "crashed"]
        assert len(crashed_events) == 1
        assert crashed_events[0].payload["pid"] == 515151
        assert crashed_events[0].payload["exit_kind"] == "signaled"
        assert crashed_events[0].payload["exit_code"] == signal.SIGKILL

        worker2 = _host_local_claimer("worker-2")
        second_claim = kb.claim_task(conn, tid, ttl_seconds=60, claimer=worker2)
        assert second_claim is not None
        assert second_claim.id == tid
        assert second_claim.current_run_id != run1_id
        assert second_claim.claim_lock == worker2
        assert second_claim.body == body
        assert _checksum(second_claim.body or "") == expected_checksum

        runs = kb.list_runs(conn, tid)
        assert len(runs) == 2
        assert [r.status for r in runs] == ["crashed", "running"]
    finally:
        conn.close()
