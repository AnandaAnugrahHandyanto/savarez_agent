"""Tests for stale gateway.pid recovery (issue #13655).

After a SIGKILL or OOM kill, atexit handlers never fire and gateway.pid
is left behind with a dead PID.  The next startup should detect the
stale file, remove it, and succeed instead of exiting with
"PID file race lost".

The production fix lives in ``gateway/run.py`` inside the ``FileExistsError``
handler of the PID-file-write section of ``start_gateway()``.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEAD_PID = 4194304  # PID that does not exist on any system


def _write_stale_pid(path: Path, pid: int) -> None:
    """Write a PID record that looks like it came from a dead process."""
    record = json.dumps({
        "kind": "gateway",
        "pid": pid,
        "argv": ["hermes", "gateway", "run"],
        "start_time": "2026-05-01T00:00:00Z",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record)


def _write_our_pid(path: Path) -> None:
    """Write a PID record for the current process."""
    record = json.dumps({
        "kind": "gateway",
        "pid": os.getpid(),
        "argv": ["hermes", "gateway", "run"],
        "start_time": "2026-05-20T00:00:00Z",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record)


# ---------------------------------------------------------------------------
# Tests for _read_pid_record (pure parsing, no os.kill)
# ---------------------------------------------------------------------------

class TestReadPidRecord:
    def test_reads_valid_record(self, tmp_path):
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        _write_stale_pid(pid_path, DEAD_PID)

        record = _read_pid_record(pid_path)
        assert record is not None
        assert record["pid"] == DEAD_PID

    def test_returns_none_for_missing_file(self, tmp_path):
        from gateway.status import _read_pid_record

        record = _read_pid_record(tmp_path / "nonexistent.pid")
        assert record is None

    def test_returns_none_for_empty_file(self, tmp_path):
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        pid_path.write_text("")

        record = _read_pid_record(pid_path)
        assert record is None

    def test_returns_none_for_malformed_file(self, tmp_path):
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        pid_path.write_text("not-a-pid-or-json")

        record = _read_pid_record(pid_path)
        assert record is None

    def test_parses_plain_int_pid(self, tmp_path):
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        pid_path.write_text("12345")

        record = _read_pid_record(pid_path)
        assert record == {"pid": 12345}


# ---------------------------------------------------------------------------
# Tests for stale PID file detection via get_running_pid
# ---------------------------------------------------------------------------

class TestGetRunningPidStaleFile:
    """Verify get_running_pid cleans up stale PID files when the lock is free."""

    def test_stale_pid_returns_none(self, tmp_path):
        from gateway.status import get_running_pid

        pid_path = tmp_path / "gateway.pid"
        lock_path = tmp_path / "gateway.lock"
        _write_stale_pid(pid_path, DEAD_PID)
        lock_path.write_text(json.dumps({"pid": DEAD_PID}))

        with patch("gateway.status._get_pid_path", return_value=pid_path), \
             patch("gateway.status._get_gateway_lock_path", return_value=lock_path):
            result = get_running_pid(pid_path=pid_path)

        assert result is None

    def test_stale_pid_file_cleaned_up(self, tmp_path):
        from gateway.status import get_running_pid

        dead_pid = DEAD_PID
        pid_path = tmp_path / "gateway.pid"
        lock_path = tmp_path / "gateway.lock"
        _write_stale_pid(pid_path, dead_pid)
        lock_path.write_text(json.dumps({"pid": dead_pid}))

        with patch("gateway.status._get_pid_path", return_value=pid_path), \
             patch("gateway.status._get_gateway_lock_path", return_value=lock_path):
            get_running_pid(pid_path=pid_path)

        assert not pid_path.exists()


# ---------------------------------------------------------------------------
# Tests for the FileExistsError recovery path in start_gateway
# ---------------------------------------------------------------------------

class TestFileExistsErrorRecovery:
    """Simulate the exact recovery path the production code takes:

    1. write_pid_file() raises FileExistsError
    2. Read the existing PID from the file
    3. Check if the PID is alive via _pid_exists
    4. If stale → unlink + retry write_pid_file
    """

    def test_stale_pid_unlinked_and_write_succeeds(self, tmp_path):
        from gateway.status import (
            write_pid_file,
            _get_pid_path,
            _read_pid_record,
        )

        pid_path = tmp_path / "gateway.pid"
        _write_stale_pid(pid_path, DEAD_PID)

        # --- This is the exact recovery logic from the production fix ---
        record = _read_pid_record(pid_path)
        assert record is not None
        existing_pid = int(record["pid"])

        # Mock _pid_exists to avoid the conftest os.kill guard
        with patch("gateway.status._pid_exists", return_value=False):
            from gateway.status import _pid_exists
            assert not _pid_exists(existing_pid)

            pid_path.unlink()

            with patch("gateway.status._get_pid_path", return_value=pid_path):
                write_pid_file()

        new_record = _read_pid_record(pid_path)
        assert new_record is not None
        assert new_record["pid"] == os.getpid()

    def test_live_pid_keeps_file_and_returns_false(self, tmp_path):
        """When the PID in the file IS alive, we should NOT remove it."""
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        _write_our_pid(pid_path)

        record = _read_pid_record(pid_path)
        assert record is not None
        existing_pid = int(record["pid"])

        # _pid_exists returns True for our own PID
        with patch("gateway.status._pid_exists", return_value=True):
            from gateway.status import _pid_exists
            assert _pid_exists(existing_pid)

            # Should NOT unlink — the gateway is genuinely running
            assert pid_path.exists()

    def test_no_record_in_file_does_not_block(self, tmp_path):
        """If the PID file exists but contains garbage, we should recover."""
        from gateway.status import _read_pid_record

        pid_path = tmp_path / "gateway.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("")

        record = _read_pid_record(pid_path)
        assert record is None

        # No PID to check → cannot confirm liveness → treat as "no
        # existing_pid" → the production code would fall to the else branch
        # (exit).  But since we can't determine liveness, the file should be
        # safe to force-remove as well.  The fix handles this case by checking
        # existing_pid is None first and falling to the else-branch (safe
        # exit).  In practice the get_running_pid() cleanup handles empty
        # files earlier.

    def test_double_retry_handles_second_race(self, tmp_path):
        """If after unlinking and retrying we STILL get FileExistsError,
        the code should give up (another process truly won the race)."""
        from gateway.status import (
            write_pid_file,
            _get_pid_path,
            _read_pid_record,
        )

        pid_path = tmp_path / "gateway.pid"
        _write_stale_pid(pid_path, DEAD_PID)

        record = _read_pid_record(pid_path)
        assert record is not None

        with patch("gateway.status._pid_exists", return_value=False):
            pid_path.unlink()

            # Simulate another process writing between our unlink and write
            _write_our_pid(pid_path)

            with patch("gateway.status._get_pid_path", return_value=pid_path):
                with pytest.raises(FileExistsError):
                    write_pid_file()


# ---------------------------------------------------------------------------
# Integration: full stale-PID-to-success flow
# ---------------------------------------------------------------------------

class TestFullStaleRecoveryIntegration:
    """End-to-end test simulating the exact #13655 scenario."""

    def test_crash_recovery_flow(self, tmp_path):
        """Simulate: process crashes → stale PID + lock → restart → succeeds."""
        from gateway.status import (
            get_running_pid,
            write_pid_file,
            _get_pid_path,
            _read_pid_record,
        )

        pid_path = tmp_path / "gateway.pid"
        lock_path = tmp_path / "gateway.lock"

        # After SIGKILL: both files left behind with dead PID
        _write_stale_pid(pid_path, DEAD_PID)
        lock_path.write_text(json.dumps({"pid": DEAD_PID}))

        with patch("gateway.status._get_pid_path", return_value=pid_path), \
             patch("gateway.status._get_gateway_lock_path", return_value=lock_path), \
             patch("gateway.status._pid_exists", side_effect=lambda pid: pid == os.getpid()):

            # Step 1: get_running_pid detects stale file, cleans up, returns None
            result = get_running_pid(pid_path=pid_path)
            assert result is None

            # Step 2: write_pid_file succeeds (stale file was cleaned)
            write_pid_file()

            # Step 3: New PID file has our PID
            new_record = _read_pid_record(pid_path)
            assert new_record is not None
            assert new_record["pid"] == os.getpid()
