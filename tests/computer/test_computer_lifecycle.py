"""Lifecycle tests for the Computer runtime watcher + reconciliation.

These exercise the gap between ``start_computer_run`` flipping a run to
``running`` and the run finishing — the watcher must reconcile the run's
status on child exit, and ``ComputerStore.reconcile_running_runs`` must
clean up obviously stale ``running`` records on later reads.
"""

from __future__ import annotations

import shutil
import threading
import time


# Real short-lived helpers we hand to ``start_computer_run`` so we exercise
# the production subprocess.Popen path without mocking it. ``/usr/bin/true``
# returns 0; ``/usr/bin/false`` returns 1; both ignore their argv tail.
TRUE_BIN = shutil.which("true") or "/usr/bin/true"
FALSE_BIN = shutil.which("false") or "/usr/bin/false"


def _wait_for(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ── Watcher: completed ────────────────────────────────────────────────────────


def test_watcher_marks_run_completed_when_child_exits_zero(tmp_path):
    from computer.runtime import ComputerStore, start_computer_run, wait_for_watcher

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="watcher-completed", features=["runtime"])

    assert start_computer_run(run["id"], store=store, hermes_executable=TRUE_BIN) is True

    # Wait for the watcher to observe the child exit.
    assert wait_for_watcher(run["id"], timeout=5.0)

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "completed", reloaded
    background = reloaded.get("background") or {}
    assert background.get("pid")
    assert background.get("binary") == TRUE_BIN
    assert background.get("stdout_log")
    assert background.get("stderr_log")
    assert background.get("exit_code") == 0

    events = [event["type"] for event in store.list_events(run["id"])]
    assert "computer.background.launched" in events
    assert "computer.background.completed" in events


# ── Watcher: failed ───────────────────────────────────────────────────────────


def test_watcher_marks_run_failed_when_child_exits_nonzero(tmp_path):
    from computer.runtime import ComputerStore, start_computer_run, wait_for_watcher

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="watcher-failed", features=["runtime"])

    assert start_computer_run(run["id"], store=store, hermes_executable=FALSE_BIN) is True
    assert wait_for_watcher(run["id"], timeout=5.0)

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "failed", reloaded
    background = reloaded.get("background") or {}
    assert background.get("exit_code") not in (None, 0)
    assert "exit" in (reloaded.get("error") or "").lower()

    events = [event["type"] for event in store.list_events(run["id"])]
    assert "computer.background.failed" in events


# ── Watcher: does not overwrite cancelled ─────────────────────────────────────


def test_watcher_does_not_overwrite_cancelled_run(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore, start_computer_run, wait_for_watcher

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="watcher-cancelled", features=["runtime"])

    # Use ``sleep`` so the child stays alive long enough for us to cancel
    # before the watcher observes its exit.
    sleep_bin = shutil.which("sleep") or "/bin/sleep"

    # The runtime currently hardcodes argv as [binary, "chat", "-q", prompt].
    # ``sleep`` will treat "chat" / "-q" / prompt as invalid duration and
    # exit nonzero almost immediately, which would let the watcher race the
    # cancel and we'd get a flaky test. To keep this deterministic and
    # cancel-first, monkeypatch subprocess.Popen with a fake long-lived
    # process whose returncode the test controls.
    import subprocess as _subprocess

    class _FakeProc:
        def __init__(self):
            self.pid = 999_999
            self._done = threading.Event()
            self.returncode = None

        def wait(self, timeout=None):
            self._done.wait(timeout)
            return self.returncode

        def poll(self):
            return self.returncode

        def finish(self, code=0):
            self.returncode = code
            self._done.set()

    fake = _FakeProc()

    def _fake_popen(*args, **kwargs):
        for fh in (kwargs.get("stdout"), kwargs.get("stderr")):
            try:
                if fh and hasattr(fh, "close"):
                    pass  # leave open; runtime/watcher must close them
            except Exception:
                pass
        return fake

    monkeypatch.setattr(_subprocess, "Popen", _fake_popen)

    assert start_computer_run(run["id"], store=store, hermes_executable=sleep_bin) is True
    assert store.get_run(run["id"])["status"] == "running"

    # Cancel BEFORE the fake child exits.
    store.update_run(run["id"], status="cancelled", error="user cancelled")
    # Now let the fake child finish with success — the watcher must NOT
    # flip ``cancelled`` back to ``completed``.
    fake.finish(0)

    assert wait_for_watcher(run["id"], timeout=5.0)

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "cancelled", reloaded
    # The watcher is still allowed to record exit_code into background
    # metadata, but the lifecycle status must stay cancelled.
    background = reloaded.get("background") or {}
    assert background.get("exit_code") == 0


# ── Reconcile: stale running ──────────────────────────────────────────────────


def test_reconcile_running_runs_marks_stale_running_as_failed(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="stale-running", features=["runtime"])

    # Persist a run that *claims* to be running with a pid that no longer
    # exists, as if hermes was killed before its watcher could reconcile.
    store.update_run(
        run["id"],
        status="running",
        background={
            "pid": 424242,
            "binary": "/fake/hermes",
            "stdout_log": str(tmp_path / "out.log"),
            "stderr_log": str(tmp_path / "err.log"),
        },
    )

    # Force the runtime's "is pid alive?" probe to return False so we don't
    # depend on whether pid 424242 really happens to exist on this host.
    import computer.runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "_is_pid_alive", lambda pid: False)

    changed = store.reconcile_running_runs()
    assert run["id"] in changed

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "failed", reloaded
    assert reloaded.get("error")
    events = [event["type"] for event in store.list_events(run["id"])]
    assert "computer.background.reconciled_stale" in events


def test_reconcile_running_runs_leaves_live_process_alone(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="live-running", features=["runtime"])
    store.update_run(
        run["id"],
        status="running",
        background={"pid": 12345, "binary": "/fake/hermes"},
    )

    import computer.runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "_is_pid_alive", lambda pid: True)

    changed = store.reconcile_running_runs()
    assert run["id"] not in changed

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "running"


def test_reconcile_running_runs_ignores_non_running_states(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore

    store = ComputerStore(base_dir=tmp_path / "computer")
    queued = store.create_run(goal="queued-run", features=["runtime"])
    done = store.create_run(goal="done-run", features=["runtime"])
    store.update_run(done["id"], status="completed")

    import computer.runtime as runtime_mod

    # Even if the probe says "dead", non-running states must not be touched.
    monkeypatch.setattr(runtime_mod, "_is_pid_alive", lambda pid: False)
    changed = store.reconcile_running_runs()
    assert queued["id"] not in changed
    assert done["id"] not in changed
    assert store.get_run(queued["id"])["status"] == "queued"
    assert store.get_run(done["id"])["status"] == "completed"
