"""
Regression tests for kanban stale claim grace window (issue #23025).

release_stale_claims() previously reclaimed any running task whose
claim_expires had passed, even if the worker had heartbeated recently.
This caused slow-model workers (e.g. kimi-k2.6) to be repeatedly
reclaimed while actively processing.
"""

import sqlite3
import time
from unittest.mock import patch, MagicMock


class TestReleaseStaleClaimsGraceWindow:
    """Tests that release_stale_claims respects recent heartbeats."""

    def test_does_not_reclaim_when_heartbeated_recently(self):
        """Worker that heartbeated 2 min ago should NOT be reclaimed."""
        from hermes_cli.kanban_db import release_stale_claims, claim_task, heartbeat_worker

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        # Setup minimal schema
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT,
                claim_lock TEXT,
                claim_expires INTEGER,
                worker_pid INTEGER,
                last_heartbeat_at INTEGER,
                current_run_id INTEGER,
                title TEXT,
                assignee TEXT,
                body TEXT,
                board TEXT,
                tenant TEXT,
                priority INTEGER DEFAULT 0,
                workspace_kind TEXT DEFAULT 'scratch',
                triage INTEGER DEFAULT 0,
                created_by TEXT
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                status TEXT,
                outcome TEXT,
                started_at INTEGER,
                claim_expires INTEGER,
                last_heartbeat_at INTEGER
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                event_type TEXT,
                payload TEXT,
                run_id INTEGER,
                created_at INTEGER
            );
        """)

        now = int(time.time())
        # Insert a running task with expired claim but recent heartbeat
        conn.execute(
            "INSERT INTO tasks (id, status, claim_lock, claim_expires, worker_pid, last_heartbeat_at, title, assignee) "
            "VALUES (?, 'running', ?, ?, ?, ?, ?, ?)",
            ("t_123", "lock-abc", now - 60, 12345, now - 120, "Test", "worker"),
        )
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, claim_expires, last_heartbeat_at) "
            "VALUES (?, ?, 'running', ?, ?, ?)",
            (1, "t_123", now - 300, now - 60, now - 120),
        )
        conn.commit()

        with patch("hermes_cli.kanban_db._terminate_reclaimed_worker") as mock_term:
            reclaimed = release_stale_claims(conn)

        assert reclaimed == 0, "Should NOT reclaim worker with recent heartbeat"
        mock_term.assert_not_called()

    def test_reclaims_when_no_recent_heartbeat(self):
        """Worker that hasn't heartbeated for 10 min SHOULD be reclaimed."""
        from hermes_cli.kanban_db import release_stale_claims

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT,
                claim_lock TEXT,
                claim_expires INTEGER,
                worker_pid INTEGER,
                last_heartbeat_at INTEGER,
                current_run_id INTEGER,
                title TEXT,
                assignee TEXT,
                body TEXT,
                board TEXT,
                tenant TEXT,
                priority INTEGER DEFAULT 0,
                workspace_kind TEXT DEFAULT 'scratch',
                triage INTEGER DEFAULT 0,
                created_by TEXT
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                status TEXT,
                outcome TEXT,
                started_at INTEGER,
                claim_expires INTEGER,
                last_heartbeat_at INTEGER
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                event_type TEXT,
                payload TEXT,
                run_id INTEGER,
                created_at INTEGER
            );
        """)

        now = int(time.time())
        # Insert a running task with expired claim and OLD heartbeat (10 min ago)
        conn.execute(
            "INSERT INTO tasks (id, status, claim_lock, claim_expires, worker_pid, last_heartbeat_at, title, assignee) "
            "VALUES (?, 'running', ?, ?, ?, ?, ?, ?)",
            ("t_456", "lock-def", now - 60, 12345, now - 600, "Test", "worker"),
        )
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, claim_expires, last_heartbeat_at) "
            "VALUES (?, ?, 'running', ?, ?, ?)",
            (1, "t_456", now - 300, now - 60, now - 600),
        )
        conn.commit()

        with patch("hermes_cli.kanban_db._terminate_reclaimed_worker", return_value={}) as mock_term:
            reclaimed = release_stale_claims(conn)

        assert reclaimed == 1, "Should reclaim worker with old heartbeat"
        mock_term.assert_called_once()

    def test_reclaims_when_no_heartbeat_at_all(self):
        """Worker that never heartbeated SHOULD be reclaimed."""
        from hermes_cli.kanban_db import release_stale_claims

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                status TEXT,
                claim_lock TEXT,
                claim_expires INTEGER,
                worker_pid INTEGER,
                last_heartbeat_at INTEGER,
                current_run_id INTEGER,
                title TEXT,
                assignee TEXT,
                body TEXT,
                board TEXT,
                tenant TEXT,
                priority INTEGER DEFAULT 0,
                workspace_kind TEXT DEFAULT 'scratch',
                triage INTEGER DEFAULT 0,
                created_by TEXT
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                status TEXT,
                outcome TEXT,
                started_at INTEGER,
                claim_expires INTEGER,
                last_heartbeat_at INTEGER
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                event_type TEXT,
                payload TEXT,
                run_id INTEGER,
                created_at INTEGER
            );
        """)

        now = int(time.time())
        # Insert a running task with expired claim and NULL heartbeat
        conn.execute(
            "INSERT INTO tasks (id, status, claim_lock, claim_expires, worker_pid, last_heartbeat_at, title, assignee) "
            "VALUES (?, 'running', ?, ?, ?, NULL, ?, ?)",
            ("t_789", "lock-ghi", now - 60, 12345, "Test", "worker"),
        )
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, claim_expires, last_heartbeat_at) "
            "VALUES (?, ?, 'running', ?, ?, NULL)",
            (1, "t_789", now - 300, now - 60),
        )
        conn.commit()

        with patch("hermes_cli.kanban_db._terminate_reclaimed_worker", return_value={}) as mock_term:
            reclaimed = release_stale_claims(conn)

        assert reclaimed == 1, "Should reclaim worker that never heartbeated"
        mock_term.assert_called_once()


if __name__ == "__main__":
    import sys

    test_class = TestReleaseStaleClaimsGraceWindow()
    methods = [m for m in dir(test_class) if m.startswith("test_")]
    passed = 0
    failed = 0

    for method_name in methods:
        try:
            getattr(test_class, method_name)()
            print(f"✓ {method_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {method_name}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
