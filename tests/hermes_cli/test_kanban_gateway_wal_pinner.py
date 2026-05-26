"""Tests for the gateway WAL pinner.

The pinner holds a BEGIN read transaction per board for the gateway's
lifetime. SQLite skips its "last connection closing" teardown path while
any shared lock exists, so wal/shm sidecars are never unlinked under the
gateway's open FDs.
"""

import os
import pathlib
import sqlite3
import sys
import tempfile
import threading
import time

import pytest


def _make_wal_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()


def _open_pinner(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=30)
    conn.execute("PRAGMA query_only=ON")
    # DO NOT execute COMMIT or ROLLBACK on this connection — the open
    # transaction is what holds the shared lock for the connection lifetime.
    conn.execute("BEGIN")
    # A bare BEGIN does not acquire the shared lock until the first WAL read.
    # SELECT 1 is a pure expression that never touches the WAL; reading
    # sqlite_master establishes the read-mark that prevents SQLite from
    # entering the "last connection closing" path and unlinking wal/shm sidecars.
    conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    return conn


def _count_deleted_wal_fds(db_path: str) -> int:
    pid = os.getpid()
    fd_dir = pathlib.Path(f"/proc/{pid}/fd")
    wal_suffix = db_path + "-wal"
    shm_suffix = db_path + "-shm"
    count = 0
    for fd_entry in fd_dir.iterdir():
        try:
            target = os.readlink(fd_entry)
        except OSError:
            continue
        if "(deleted)" in target and (wal_suffix in target or shm_suffix in target):
            count += 1
    return count


def _spam_connections(db_path: str, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            c = sqlite3.connect(db_path, timeout=5)
            c.execute("SELECT * FROM t").fetchone()
            c.close()
        except sqlite3.Error:
            pass


def test_wal_pinner_holds_shared_lock():
    """Pinner's BEGIN+SELECT snapshot blocks wal_checkpoint(FULL) when behind WAL head.

    SQLite cannot move the WAL log pointer past any reader's read-mark. When
    the pinner opens at snapshot T0 (empty table) and a writer commits at T1,
    wal_checkpoint(FULL) returns busy=1 because the pinner's read-mark is older
    than the new WAL frames. The SELECT after BEGIN is what acquires the lock —
    a bare BEGIN alone does not establish a read-mark.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")

        # Init WAL-mode DB; disable auto-checkpoint so WAL pages don't vanish
        # before the checkpoint call under test.
        setup = sqlite3.connect(db_path)
        setup.execute("PRAGMA journal_mode=WAL")
        setup.execute("PRAGMA wal_autocheckpoint=0")
        setup.execute("CREATE TABLE t (x INTEGER)")
        setup.commit()

        # Pinner opens at T0 (empty table).  BEGIN + SELECT establishes the
        # read-mark at this point; subsequent writes land in frames the pinner
        # cannot see, so checkpoint cannot advance past them.
        pinner = _open_pinner(db_path)

        # Write at T1 — creates WAL frames newer than the pinner's read-mark.
        writer = sqlite3.connect(db_path)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO t VALUES (1)")
        writer.commit()
        writer.close()
        setup.close()

        try:
            conn3 = sqlite3.connect(db_path, timeout=2)
            result = conn3.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
            conn3.close()
            # busy=1: checkpoint cannot restart the WAL because pinner holds T0 read-mark.
            assert result[0] == 1, (
                f"Expected busy=1 from checkpoint blocked by pinner, got {result}"
            )
        finally:
            pinner.close()


@pytest.mark.skipif(sys.platform != "linux", reason="/proc/pid/fd only on Linux")
def test_wal_pinner_no_deleted_fds_after_dispatcher_traffic():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")
        _make_wal_db(db_path)

        pinner = _open_pinner(db_path)
        stop_event = threading.Event()

        threads = [
            threading.Thread(
                target=_spam_connections, args=(db_path, stop_event), daemon=True
            )
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        time.sleep(5)
        stop_event.set()
        for t in threads:
            t.join(timeout=10)

        deleted_count = _count_deleted_wal_fds(db_path)
        pinner.close()

        assert deleted_count == 0, (
            f"Found {deleted_count} deleted WAL/shm FD(s) — pinner failed to "
            "hold the sidecar"
        )


def test_wal_pinner_graceful_shutdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")
        _make_wal_db(db_path)

        pinner = _open_pinner(db_path)
        pinner.close()

        with pytest.raises(sqlite3.ProgrammingError):
            pinner.execute("SELECT 1")


def test_pinner_query_only_cannot_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")

        setup = sqlite3.connect(db_path)
        setup.execute("PRAGMA journal_mode=WAL")
        setup.execute("CREATE TABLE items (v INTEGER)")
        setup.commit()
        setup.close()

        pinner = _open_pinner(db_path)
        try:
            with pytest.raises(sqlite3.OperationalError):
                pinner.execute("INSERT INTO items VALUES (42)")
        finally:
            pinner.close()


@pytest.mark.skipif(sys.platform != "linux", reason="/proc/pid/fd only on Linux")
def test_no_pinner_accumulates_deleted_fds():
    """Regression guard: the wal/shm unlink IS triggered without a WAL read-mark.

    Uses raw os.open() FDs (not sqlite3 connection FDs) to deterministically
    observe deleted-inode state. When the last SQLite connection closes without
    a live read-mark, SQLite unlinks wal/shm; any process FD that was open to
    those files beforehand now shows up as (deleted) in /proc/<pid>/fd.

    This test is the complement of test_wal_pinner_no_deleted_fds_after_
    dispatcher_traffic — it confirms that the unlink DOES happen when the
    pinner's read-mark is absent, making the positive test non-vacuous.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")

        # Create WAL-mode DB with data so sidecars are created.
        setup = sqlite3.connect(db_path)
        setup.execute("PRAGMA journal_mode=WAL")
        setup.execute("PRAGMA wal_autocheckpoint=0")
        setup.execute("CREATE TABLE t (x INTEGER)")
        setup.execute("INSERT INTO t VALUES (1)")
        setup.commit()

        wal_path = db_path + "-wal"
        shm_path = db_path + "-shm"

        assert os.path.exists(wal_path), "wal sidecar must exist before the unlink test"

        # Hold raw OS-level FDs so we can observe the unlink via /proc/<pid>/fd.
        # SQLite's own FDs are closed by sqlite3_close before returning, so we
        # need out-of-band FDs to catch the (deleted) state.
        wal_fd = os.open(wal_path, os.O_RDONLY)
        shm_fd = os.open(shm_path, os.O_RDONLY)

        try:
            # Close setup — it is the last connection that holds a WAL read lock
            # (no other connection has called BEGIN+SELECT). SQLite enters the
            # "last connection closing" path and unlinks wal/shm.
            setup.close()

            assert not os.path.exists(wal_path), (
                "setup.close() should have unlinked the WAL (no read-mark held by anyone)"
            )

            pid = os.getpid()
            wal_link = os.readlink(f"/proc/{pid}/fd/{wal_fd}")
            shm_link = os.readlink(f"/proc/{pid}/fd/{shm_fd}")

            assert "(deleted)" in wal_link, (
                f"expected wal_fd to be a deleted inode after unlink, got: {wal_link}"
            )
            assert "(deleted)" in shm_link, (
                f"expected shm_fd to be a deleted inode after unlink, got: {shm_link}"
            )
        finally:
            os.close(wal_fd)
            os.close(shm_fd)


def test_pinner_does_not_affect_cli_connect():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "kanban.db")
        _make_wal_db(db_path)

        pinner = _open_pinner(db_path)
        result: dict = {}

        def _worker() -> None:
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                try:
                    row = conn.execute("PRAGMA integrity_check").fetchone()
                    result["integrity"] = row[0] if row else None
                    conn.execute("CREATE TABLE extra (y INTEGER)")
                    conn.execute("INSERT INTO extra VALUES (99)")
                    conn.commit()
                    result["wrote"] = True
                finally:
                    conn.close()
            except Exception as exc:
                result["error"] = repr(exc)

        try:
            t = threading.Thread(target=_worker)
            t.start()
            t.join(timeout=15)
            assert not t.is_alive(), "worker thread blocked by pinner"
            assert result.get("error") is None, f"worker raised: {result.get('error')}"
            assert result.get("integrity") == "ok"
            assert result.get("wrote") is True
        finally:
            pinner.close()
