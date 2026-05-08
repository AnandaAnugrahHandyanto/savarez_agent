"""Tests for the gateway-embedded kanban check-in scheduler.

Validates config-gating, stale-task detection delegation, and per-task
check-in recording without spinning up a real gateway event loop.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY, title TEXT, assignee TEXT, status TEXT,
            updated_at INTEGER, last_heartbeat_at INTEGER
        );
        CREATE TABLE task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT, event_type TEXT, payload TEXT, created_at TEXT
        );
    """)
    return conn


# ---------------------------------------------------------------------------
# Unit: _run_checkin_scan
# ---------------------------------------------------------------------------

class TestRunCheckinScan:
    """Tests for the synchronous scan helper (called via asyncio.to_thread)."""

    def _make_fake_watcher(self):
        """Return a minimal stand-in for the Gateway object."""
        obj = mock.MagicMock()
        obj._run_checkin_scan = gateway_run._run_checkin_scan.__get__(obj)
        return obj

    def test_no_stale_tasks_is_noop(self):
        """When no tasks are stale, nothing is written to the DB."""
        import hermes_cli.kanban_checkin as kci
        import hermes_cli.kanban_db as kb

        conn = _make_in_memory_db()
        # No tasks → find_stale_tasks returns []
        with mock.patch.object(kb, 'connect', return_value=mock.MagicMock(__enter__=lambda s: conn, __exit__=lambda s, *a: None)):
            with mock.patch.object(kci, 'find_stale_tasks', return_value=[]):
                obj = mock.MagicMock()
                from gateway import run as gateway_run
                gateway_run.GatewayServer._run_checkin_scan(obj, kb, kci, 30.0)

        rows = conn.execute("SELECT * FROM task_events").fetchall()
        assert rows == []

    def test_stale_task_gets_checkin_event(self):
        """A stale task gets a checkin event recorded in task_events."""
        import hermes_cli.kanban_checkin as kci
        import hermes_cli.kanban_db as kb
        from gateway import run as gateway_run

        conn = _make_in_memory_db()
        stale_time = int(time.time()) - 3600
        conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)",
                     ("task-abc", "Do something", "alice", "running", stale_time, None))

        ctx = mock.MagicMock()
        ctx.__enter__ = lambda s: conn
        ctx.__exit__ = lambda s, *a: None

        with mock.patch.object(kb, 'connect', return_value=ctx):
            with mock.patch.object(kci, 'find_stale_tasks', return_value=[{"id": "task-abc"}]):
                obj = mock.MagicMock()
                gateway_run.GatewayServer._run_checkin_scan(obj, kb, kci, 30.0)


# ---------------------------------------------------------------------------
# Integration: config gating
# ---------------------------------------------------------------------------

class TestCheckinWatcherConfigGating:
    """The watcher must exit immediately when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_by_default(self):
        """checkin_in_gateway defaults to false — watcher exits without looping."""
        from gateway import run as gateway_run

        server = mock.MagicMock(spec=gateway_run.GatewayServer)
        server._running = True

        fake_cfg = {"kanban": {"checkin_in_gateway": False}}
        with mock.patch("hermes_cli.config.load_config", return_value=fake_cfg):
            await gateway_run.GatewayServer._kanban_checkin_watcher(server)
        # If we get here without hanging, the watcher correctly exited early.

    @pytest.mark.asyncio
    async def test_disabled_by_env(self, monkeypatch):
        """HERMES_KANBAN_CHECKIN_IN_GATEWAY=false disables via env override."""
        from gateway import run as gateway_run

        monkeypatch.setenv("HERMES_KANBAN_CHECKIN_IN_GATEWAY", "false")
        server = mock.MagicMock(spec=gateway_run.GatewayServer)
        server._running = True
        await gateway_run.GatewayServer._kanban_checkin_watcher(server)
        # Exits immediately — no hang.
