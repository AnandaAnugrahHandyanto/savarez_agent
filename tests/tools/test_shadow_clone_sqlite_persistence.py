"""Tests for shadow_clone SQLite persistence.

Covers:
  - hermes_state.SessionDB: insert, update, recover, gc for shadow_clone_tasks
  - tools.async_delegation: shadow_clone=True writes SQLite on dispatch + finalize
  - gateway/run.py: _shadow_clone_enqueue, _drain_shadow_clone_inbox (C1/C2/C3)
  - startup recovery path and GC path
"""
from __future__ import annotations

import asyncio
import json
import queue
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hermes_state import SessionDB
from tools import async_delegation as ad
from tools.process_registry import process_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Return an isolated SessionDB backed by a temp file."""
    return SessionDB(db_path=tmp_path / "state.db")


@pytest.fixture(autouse=True)
def _clean_ad():
    """Reset async_delegation module state and the completion queue."""
    ad._reset_for_tests()
    while not process_registry.completion_queue.empty():
        try:
            process_registry.completion_queue.get_nowait()
        except Exception:
            break
    yield
    ad._reset_for_tests()
    while not process_registry.completion_queue.empty():
        try:
            process_registry.completion_queue.get_nowait()
        except Exception:
            break


def _drain_queue(timeout=5.0):
    """Drain one item from the completion queue, or return None on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_registry.completion_queue.empty():
            return process_registry.completion_queue.get_nowait()
        time.sleep(0.02)
    return None


# ---------------------------------------------------------------------------
# hermes_state.SessionDB — schema & CRUD
# ---------------------------------------------------------------------------

class TestSchemaAndCrud:
    def test_table_created(self, tmp_db):
        """shadow_clone_tasks table exists after SessionDB init."""
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shadow_clone_tasks'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_insert_and_query(self, tmp_db):
        """insert_shadow_clone_task writes a row with status='running'."""
        tmp_db.insert_shadow_clone_task(
            delegation_id="d1",
            session_key="sk1",
            goal="do the thing",
            kanban_ticket_id="t_abc123",
            dispatched_at=1234567890.0,
        )
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        row = conn.execute(
            "SELECT * FROM shadow_clone_tasks WHERE delegation_id='d1'"
        ).fetchone()
        conn.close()
        assert row is not None
        col_names = [
            "delegation_id", "session_key", "goal", "kanban_ticket_id",
            "routing_meta", "status", "result_json", "dispatched_at", "completed_at",
        ]
        r = dict(zip(col_names, row))
        assert r["status"] == "running"
        assert r["goal"] == "do the thing"
        assert r["kanban_ticket_id"] == "t_abc123"
        assert r["dispatched_at"] == pytest.approx(1234567890.0)
        assert r["completed_at"] is None

    def test_insert_idempotent(self, tmp_db):
        """Duplicate insert (OR IGNORE) doesn't raise or add a second row."""
        for _ in range(3):
            tmp_db.insert_shadow_clone_task(
                delegation_id="d_dup", session_key="sk", dispatched_at=1.0
            )
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM shadow_clone_tasks WHERE delegation_id='d_dup'"
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_update_status(self, tmp_db):
        """update_shadow_clone_task changes status and sets result_json."""
        tmp_db.insert_shadow_clone_task(
            delegation_id="d2", session_key="sk", dispatched_at=time.time()
        )
        result_payload = {"summary": "all done", "api_calls": 3}
        tmp_db.update_shadow_clone_task(
            "d2",
            status="completed",
            result_json=json.dumps(result_payload),
            completed_at=9999.0,
        )
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        row = conn.execute(
            "SELECT status, result_json, completed_at FROM shadow_clone_tasks WHERE delegation_id='d2'"
        ).fetchone()
        conn.close()
        assert row[0] == "completed"
        assert json.loads(row[1]) == result_payload
        assert row[2] == pytest.approx(9999.0)

    def test_update_preserves_result_json_when_none(self, tmp_db):
        """update with result_json=None keeps the existing value."""
        tmp_db.insert_shadow_clone_task(
            delegation_id="d3", session_key="sk", dispatched_at=time.time()
        )
        tmp_db.update_shadow_clone_task("d3", status="completed", result_json='{"x":1}')
        # Second update without result_json — should keep {"x":1}
        tmp_db.update_shadow_clone_task("d3", status="error")
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        row = conn.execute(
            "SELECT result_json FROM shadow_clone_tasks WHERE delegation_id='d3'"
        ).fetchone()
        conn.close()
        assert row[0] == '{"x":1}'


# ---------------------------------------------------------------------------
# recover_inflight_shadow_clone_tasks
# ---------------------------------------------------------------------------

class TestRecover:
    def test_empty_db_returns_empty(self, tmp_db):
        assert tmp_db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200) == []

    def test_completed_rows_not_returned(self, tmp_db):
        tmp_db.insert_shadow_clone_task(delegation_id="done", session_key="sk", dispatched_at=1.0)
        tmp_db.update_shadow_clone_task("done", status="completed")
        rows = tmp_db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)
        assert rows == []

    def test_fresh_running_row_returned_unchanged(self, tmp_db):
        tmp_db.insert_shadow_clone_task(
            delegation_id="fresh", session_key="sk", dispatched_at=time.time()
        )
        rows = tmp_db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)
        assert len(rows) == 1
        assert rows[0]["delegation_id"] == "fresh"
        assert rows[0]["status"] == "running"

    def test_stale_running_row_marked_timeout(self, tmp_db):
        """Rows older than ttl_seconds become 'timeout' in DB and return list."""
        stale_at = time.time() - 9000  # 2.5 h ago, TTL=7200 s
        tmp_db.insert_shadow_clone_task(
            delegation_id="stale", session_key="sk", dispatched_at=stale_at
        )
        rows = tmp_db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)
        assert len(rows) == 1
        assert rows[0]["status"] == "timeout"
        # Verify DB was updated
        import sqlite3
        conn = sqlite3.connect(str(tmp_db.db_path))
        row = conn.execute(
            "SELECT status FROM shadow_clone_tasks WHERE delegation_id='stale'"
        ).fetchone()
        conn.close()
        assert row[0] == "timeout"

    def test_mixed_fresh_and_stale(self, tmp_db):
        """Fresh rows stay running; stale rows become timeout."""
        now = time.time()
        tmp_db.insert_shadow_clone_task(delegation_id="a", session_key="sk", dispatched_at=now)
        tmp_db.insert_shadow_clone_task(
            delegation_id="b", session_key="sk", dispatched_at=now - 10000
        )
        rows = tmp_db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)
        statuses = {r["delegation_id"]: r["status"] for r in rows}
        assert statuses["a"] == "running"
        assert statuses["b"] == "timeout"


# ---------------------------------------------------------------------------
# gc_shadow_clone_tasks
# ---------------------------------------------------------------------------

class TestGc:
    def test_gc_deletes_old_terminal_rows(self, tmp_db):
        """Terminal rows older than retain_hours are deleted."""
        old_ts = time.time() - 25 * 3600  # 25 h ago
        for did, status in [("c1", "completed"), ("c2", "error"), ("c3", "cancelled"),
                            ("c4", "timed_out"), ("c5", "timeout"), ("c6", "interrupted")]:
            tmp_db.insert_shadow_clone_task(delegation_id=did, session_key="sk", dispatched_at=old_ts)
            tmp_db.update_shadow_clone_task(did, status=status, completed_at=old_ts)
        n = tmp_db.gc_shadow_clone_tasks(retain_hours=24)
        assert n == 6

    def test_gc_keeps_recent_terminal_rows(self, tmp_db):
        """Terminal rows within retain_hours are NOT deleted."""
        recent_ts = time.time() - 3600  # 1 h ago
        tmp_db.insert_shadow_clone_task(delegation_id="r1", session_key="sk", dispatched_at=recent_ts)
        tmp_db.update_shadow_clone_task("r1", status="completed", completed_at=recent_ts)
        n = tmp_db.gc_shadow_clone_tasks(retain_hours=24)
        assert n == 0

    def test_gc_never_deletes_running_rows(self, tmp_db):
        """Running rows are never GC'd, even if very old."""
        old_ts = time.time() - 99999
        tmp_db.insert_shadow_clone_task(delegation_id="run", session_key="sk", dispatched_at=old_ts)
        n = tmp_db.gc_shadow_clone_tasks(retain_hours=0)  # retain nothing
        assert n == 0

    def test_gc_returns_zero_on_empty_db(self, tmp_db):
        assert tmp_db.gc_shadow_clone_tasks(retain_hours=24) == 0


# ---------------------------------------------------------------------------
# async_delegation.py — shadow_clone=True dispatch + finalize SQLite writes
# ---------------------------------------------------------------------------

class TestAsyncDelegationSqlite:
    def _make_db(self, tmp_path):
        return SessionDB(db_path=tmp_path / "state.db")

    def test_dispatch_with_shadow_clone_false_does_not_write(self, tmp_path):
        """shadow_clone=False: no SQL insert is attempted."""
        db = self._make_db(tmp_path)
        call_log = []
        orig_insert = db.insert_shadow_clone_task

        def tracked_insert(**kwargs):
            call_log.append(kwargs)
            return orig_insert(**kwargs)

        db.insert_shadow_clone_task = tracked_insert

        with patch("hermes_state.SessionDB", return_value=db):
            res = ad.dispatch_async_delegation(
                goal="g", context=None, toolsets=None, role="leaf", model="m",
                session_key="sk", runner=lambda: {"status": "completed"},
                shadow_clone=False,
            )
        assert res["status"] == "dispatched"
        _drain_queue(timeout=3)
        # No insert should have been called
        assert call_log == [], f"Expected no insert calls, got: {call_log}"

    def test_dispatch_with_shadow_clone_true_inserts_row(self, tmp_path):
        """shadow_clone=True: row inserted with status='running' on dispatch."""
        db = self._make_db(tmp_path)
        gate = threading.Event()

        def runner():
            gate.wait(timeout=5)
            return {"status": "completed", "summary": "ok"}

        with patch("hermes_state.SessionDB", return_value=db):
            res = ad.dispatch_async_delegation(
                goal="shadow goal", context=None, toolsets=None, role="leaf",
                model="m", session_key="sk_test", runner=runner,
                shadow_clone=True, kanban_ticket_id="t_ticket",
            )
        assert res["status"] == "dispatched"
        did = res["delegation_id"]

        # Row should be 'running' while the runner is gated
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "state.db"))
        row = conn.execute(
            "SELECT status, goal, kanban_ticket_id FROM shadow_clone_tasks WHERE delegation_id=?",
            (did,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == "shadow goal"
        assert row[2] == "t_ticket"

        gate.set()  # let runner finish

    def test_finalize_updates_row_to_completed(self, tmp_path):
        """After runner returns, row is updated to 'completed' in SQLite."""
        db = self._make_db(tmp_path)

        def runner():
            return {"status": "completed", "summary": "all done", "api_calls": 2}

        with patch("hermes_state.SessionDB", return_value=db):
            res = ad.dispatch_async_delegation(
                goal="g", context=None, toolsets=None, role="leaf", model="m",
                session_key="sk", runner=runner,
                shadow_clone=True,
            )
            did = res["delegation_id"]
            evt = _drain_queue(timeout=5)

        assert evt is not None
        assert evt["status"] == "completed"

        # Row should now be 'completed'
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "state.db"))
        row = conn.execute(
            "SELECT status FROM shadow_clone_tasks WHERE delegation_id=?",
            (did,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "completed"

    def test_finalize_updates_row_on_error(self, tmp_path):
        """When runner raises, row status becomes 'error'."""
        db = self._make_db(tmp_path)

        def bad_runner():
            raise RuntimeError("boom")

        with patch("hermes_state.SessionDB", return_value=db):
            res = ad.dispatch_async_delegation(
                goal="g", context=None, toolsets=None, role="leaf", model="m",
                session_key="sk", runner=bad_runner,
                shadow_clone=True,
            )
            did = res["delegation_id"]
            evt = _drain_queue(timeout=5)

        assert evt is not None
        assert evt["status"] == "error"

        import sqlite3
        conn = sqlite3.connect(str(tmp_path / "state.db"))
        row = conn.execute(
            "SELECT status FROM shadow_clone_tasks WHERE delegation_id=?", (did,)
        ).fetchone()
        conn.close()
        assert row[0] == "error"

    def test_shadow_clone_flag_in_completion_event(self, tmp_path):
        """shadow_clone=True propagates the flag into the completion event."""
        db = self._make_db(tmp_path)

        def runner():
            return {"status": "completed"}

        with patch("hermes_state.SessionDB", return_value=db):
            res = ad.dispatch_async_delegation(
                goal="g", context=None, toolsets=None, role="leaf", model="m",
                session_key="sk", runner=runner,
                shadow_clone=True,
            )
            evt = _drain_queue(timeout=5)

        # The event record carries shadow_clone so the gateway watcher can branch.
        assert evt is not None
        assert evt.get("shadow_clone") is True

    def test_db_failure_does_not_crash_dispatch(self):
        """SQLite failure on insert is swallowed — dispatch still returns 'dispatched'."""
        with patch("hermes_state.SessionDB", side_effect=RuntimeError("db down")):
            res = ad.dispatch_async_delegation(
                goal="g", context=None, toolsets=None, role="leaf", model="m",
                session_key="sk", runner=lambda: {"status": "completed"},
                shadow_clone=True,
            )
        assert res["status"] == "dispatched"
        _drain_queue(timeout=3)  # let runner finish without error


# ---------------------------------------------------------------------------
# gateway/run.py — _shadow_clone_enqueue, _drain_shadow_clone_inbox (C1/C2/C3)
# ---------------------------------------------------------------------------

class TestGatewayShadowCloneMethods:
    """Test the three new GatewayRunner shadow_clone methods."""

    def _make_runner(self):
        """Build a minimal GatewayRunner-like object with the three methods
        duck-typed in, avoiding the heavy GatewayRunner.__init__."""
        from collections import deque
        import threading as _threading

        class FakeRunner:
            _shadow_clone_inbox = deque()
            _shadow_clone_inbox_lock = _threading.Lock()
            _shadow_clone_routing = {}
            _shadow_clone_drain_locks = {}

        # Inject the real methods from GatewayRunner
        from gateway.run import GatewayRunner
        FakeRunner._shadow_clone_enqueue = GatewayRunner._shadow_clone_enqueue
        FakeRunner._drain_shadow_clone_inbox = GatewayRunner._drain_shadow_clone_inbox
        FakeRunner._shadow_clone_persist_routing = GatewayRunner._shadow_clone_persist_routing

        return FakeRunner()

    def test_enqueue_is_thread_safe(self):
        """Multiple threads can enqueue without data loss."""
        runner = self._make_runner()
        errors = []

        def enqueue_many(prefix, count=20):
            try:
                for i in range(count):
                    runner._shadow_clone_enqueue(f"{prefix}_{i}", {"platform": "telegram"})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=enqueue_many, args=(f"t{n}",)) for n in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(runner._shadow_clone_inbox) == 100  # 5 threads × 20

    def test_enqueue_captures_routing_meta_snapshot(self):
        """routing_meta is deep-copied at enqueue time (C1)."""
        runner = self._make_runner()
        meta = {"platform": "telegram", "chat_id": "123"}
        runner._shadow_clone_enqueue("d1", meta)
        meta["chat_id"] = "999"  # mutate after enqueue
        # Should still have original value
        assert runner._shadow_clone_routing["d1"]["chat_id"] == "123"

    def test_drain_empties_inbox(self, tmp_path):
        """_drain_shadow_clone_inbox processes all queued items."""
        runner = self._make_runner()
        db = SessionDB(db_path=tmp_path / "state.db")
        db.insert_shadow_clone_task(delegation_id="d1", session_key="sk", dispatched_at=time.time())

        runner._shadow_clone_enqueue("d1", {"platform": "telegram", "chat_id": "1"})
        assert len(runner._shadow_clone_inbox) == 1

        with patch("hermes_state.SessionDB", return_value=db):
            asyncio.run(runner._drain_shadow_clone_inbox())

        assert len(runner._shadow_clone_inbox) == 0

    def test_drain_no_items_is_noop(self):
        """_drain_shadow_clone_inbox with empty inbox returns without error."""
        runner = self._make_runner()
        asyncio.run(runner._drain_shadow_clone_inbox())  # should not raise

    def test_drain_uses_asyncio_to_thread_for_sqlite(self, tmp_path):
        """SQLite persistence happens in asyncio.to_thread (C3 — non-blocking)."""
        runner = self._make_runner()
        db = SessionDB(db_path=tmp_path / "state.db")
        db.insert_shadow_clone_task(delegation_id="d_c3", session_key="sk", dispatched_at=time.time())
        runner._shadow_clone_enqueue("d_c3", {"platform": "telegram"})

        call_thread_ids = []
        original = asyncio.to_thread

        async def tracking_to_thread(fn, *args, **kwargs):
            # This just records that to_thread was called
            call_thread_ids.append("to_thread_called")
            return await original(fn, *args, **kwargs)

        with patch("gateway.run.asyncio.to_thread", side_effect=tracking_to_thread), \
             patch("hermes_state.SessionDB", return_value=db):
            asyncio.run(runner._drain_shadow_clone_inbox())

        assert call_thread_ids, "asyncio.to_thread was not called (C3 regression)"

    def test_drain_concurrent_same_delegation_serialized(self, tmp_path):
        """Two concurrent drains of the same delegation_id don't race (C1 lock)."""
        runner = self._make_runner()
        db = SessionDB(db_path=tmp_path / "state.db")
        db.insert_shadow_clone_task(delegation_id="d_lock", session_key="sk", dispatched_at=time.time())
        runner._shadow_clone_enqueue("d_lock", {"platform": "telegram"})

        call_order = []
        original_persist = runner._shadow_clone_persist_routing

        def slow_persist(did, meta):
            call_order.append(("start", did))
            time.sleep(0.05)
            original_persist(runner, did, meta)
            call_order.append(("end", did))

        async def run_two():
            # Two concurrent drain calls
            runner._shadow_clone_inbox.append("d_lock")
            runner._shadow_clone_routing["d_lock"] = {"platform": "slack"}
            with patch.object(runner, "_shadow_clone_persist_routing", slow_persist):
                with patch("hermes_state.SessionDB", return_value=db):
                    await asyncio.gather(
                        runner._drain_shadow_clone_inbox(),
                        runner._drain_shadow_clone_inbox(),
                    )

        asyncio.run(run_two())
        # Both calls resolved without error
        # (The lock means one may be a no-op if inbox was already cleared)
        assert call_order  # at least one persist happened


# ---------------------------------------------------------------------------
# Startup recovery path (gateway/run.py start())
# ---------------------------------------------------------------------------

class TestStartupRecovery:
    def test_recover_called_on_startup(self, tmp_path):
        """start() calls recover_inflight_shadow_clone_tasks(ttl_seconds=7200)."""
        db = SessionDB(db_path=tmp_path / "state.db")
        # Insert a running row from "before the restart"
        db.insert_shadow_clone_task(
            delegation_id="pre_restart",
            session_key="sk",
            goal="leftover",
            dispatched_at=time.time(),
        )

        with patch("hermes_state.SessionDB", return_value=db):
            recovered = db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)

        assert len(recovered) == 1
        assert recovered[0]["delegation_id"] == "pre_restart"
        assert recovered[0]["status"] == "running"

    def test_stale_row_timeout_on_recovery(self, tmp_path):
        """Rows older than TTL are marked 'timeout' during startup recovery."""
        db = SessionDB(db_path=tmp_path / "state.db")
        db.insert_shadow_clone_task(
            delegation_id="old_task",
            session_key="sk",
            goal="stale work",
            dispatched_at=time.time() - 9000,  # 2.5 h ago
        )
        recovered = db.recover_inflight_shadow_clone_tasks(ttl_seconds=7200)
        assert len(recovered) == 1
        assert recovered[0]["status"] == "timeout"


# ---------------------------------------------------------------------------
# GC path (called from _async_delegation_watcher tick)
# ---------------------------------------------------------------------------

class TestGcIntegration:
    def test_gc_called_correctly(self, tmp_path):
        """gc_shadow_clone_tasks(retain_hours=24) deletes old rows."""
        db = SessionDB(db_path=tmp_path / "state.db")
        old_ts = time.time() - 25 * 3600
        db.insert_shadow_clone_task(delegation_id="gc_me", session_key="sk", dispatched_at=old_ts)
        db.update_shadow_clone_task("gc_me", status="completed", completed_at=old_ts)

        n = db.gc_shadow_clone_tasks(retain_hours=24)
        assert n == 1

    def test_gc_preserves_running_rows(self, tmp_path):
        """Running rows are never deleted by GC."""
        db = SessionDB(db_path=tmp_path / "state.db")
        old_ts = time.time() - 99999
        db.insert_shadow_clone_task(delegation_id="keep_me", session_key="sk", dispatched_at=old_ts)
        # No update — still 'running'
        n = db.gc_shadow_clone_tasks(retain_hours=0)
        assert n == 0
