"""Regression tests for _wait_for_process subprocess cleanup on exception exit.

When the poll loop exits via KeyboardInterrupt or SystemExit (SIGTERM via
cli.py signal handler, SIGINT on the main thread in non-interactive -q mode,
or explicit sys.exit from some caller), the child subprocess must be killed
before the exception propagates — otherwise the local backend's use of
os.setsid leaves an orphan with PPID=1.

The live repro that motivated this: hermes chat -q ... 'sleep 300', SIGTERM
to the python process, sleep 300 survived with PPID=1 for the full 300 s
because _wait_for_process never got to call _kill_process before python
died.  See commit message for full context.
"""
import os
import signal
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

from tools.environments.local import LocalEnvironment


@pytest.fixture(autouse=True)
def _isolate_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "logs").mkdir(exist_ok=True)


def _pgid_still_alive(pgid: int) -> bool:
    """Return True if any non-zombie process in the group is still alive."""
    try:
        import psutil

        for proc in psutil.process_iter(["status"]):
            try:
                if os.getpgid(proc.pid) == pgid and proc.info.get("status") != psutil.STATUS_ZOMBIE:
                    return True
            except (ProcessLookupError, PermissionError, psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except ImportError:
        pass

    try:
        ps = subprocess.run(
            ["ps", "-axo", "pid,pgid,state"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in ps.stdout.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) >= 3 and parts[1].isdigit() and int(parts[1]) == pgid:
                if "Z" not in parts[2]:
                    return True
        return False
    except Exception:
        try:
            os.killpg(pgid, 0)  # signal 0 = existence check
            return True
        except ProcessLookupError:
            return False


def _process_group_snapshot(pgid: int) -> str:
    """Return a process-table snapshot for diagnostics."""
    return subprocess.run(
        ["ps", "-o", "pid,ppid,pgid,stat,cmd", "-g", str(pgid)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def _wait_for_pgid_exit(pgid: int, timeout: float = 10.0) -> bool:
    """Wait for a process group to disappear under loaded xdist hosts."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pgid_still_alive(pgid):
            return True
        time.sleep(0.1)
    return not _pgid_still_alive(pgid)


def test_kill_process_uses_cached_pgid_if_wrapper_already_exited(monkeypatch):
    """If the shell wrapper exits before cleanup, still kill its process group.

    Without the cached pgid fallback, ``os.getpgid(proc.pid)`` raises for the
    dead wrapper and cleanup falls back to ``proc.kill()``, which cannot reach
    orphaned grandchildren still running in the original process group.
    """
    env = object.__new__(LocalEnvironment)
    proc = SimpleNamespace(
        pid=12345,
        _hermes_pgid=67890,
        poll=lambda: 0,
        kill=lambda: None,
    )
    killpg_calls = []

    def fake_getpgid(_pid):
        raise ProcessLookupError

    def fake_killpg(pgid, sig):
        killpg_calls.append((pgid, sig))
        if sig == 0:
            raise ProcessLookupError

    monkeypatch.setattr(os, "getpgid", fake_getpgid)
    monkeypatch.setattr(os, "killpg", fake_killpg)

    env._kill_process(proc)

    assert killpg_calls == [(67890, signal.SIGTERM), (67890, 0)]


@pytest.mark.live_system_guard_bypass
def test_wait_for_process_kills_subprocess_on_keyboardinterrupt():
    """When KeyboardInterrupt arrives mid-poll, the subprocess group must be
    killed before the exception is re-raised."""
    env = LocalEnvironment(cwd="/tmp")
    try:
        proc = env._run_bash("sleep 30", timeout=60)
        pgid = os.getpgid(proc.pid)
        assert _pgid_still_alive(pgid), "sanity: subprocess should be alive"

        wait_thread_id = threading.get_ident()
        real_poll = proc.poll
        poll_count = 0

        def interrupting_poll():
            nonlocal poll_count
            if threading.get_ident() == wait_thread_id:
                poll_count += 1
                if poll_count >= 2:
                    raise KeyboardInterrupt
            return real_poll()

        proc.poll = interrupting_poll

        with pytest.raises(KeyboardInterrupt):
            env._wait_for_process(proc, timeout=60)

        # The critical assertion: the subprocess GROUP must be dead.  Not
        # just the bash wrapper — the 'sleep 30' child too.
        assert _wait_for_pgid_exit(pgid), (
            f"subprocess group {pgid} is STILL ALIVE after _wait_for_process received "
            f"KeyboardInterrupt — orphan bug regressed.  This is the "
            f"sleep-300-survives-SIGTERM scenario from Physikal's Apr 2026 "
            f"report.  See tools/environments/base.py _wait_for_process "
            f"except-block.\n{_process_group_snapshot(pgid)}"
        )
    finally:
        try:
            env.cleanup()
        except Exception:
            pass
