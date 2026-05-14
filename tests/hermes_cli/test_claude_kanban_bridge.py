"""Tests for scripts/claude_kanban_bridge.py.

All tests mock the subprocess boundary — the real `claude` CLI is never invoked.
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with a fresh kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from hermes_cli import kanban_db as kb
    kb.init_db()
    return home


@pytest.fixture
def ready_task(kanban_home):
    """Return a task-id for a ready task assigned to claude-code-bridge."""
    from hermes_cli import kanban_db as kb
    with kb.connect() as conn:
        tid = kb.create_task(
            conn,
            title="Run integration smoke tests",
            body="Execute the smoke test suite and report failures.",
            assignee="claude-code-bridge",
        )
    return tid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_bridge(task_id, board=None, argv=None, monkeypatch=None):
    """Import and call the bridge's main() function in-process."""
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "claude_kanban_bridge",
        "scripts/claude_kanban_bridge.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    extra = []
    if board:
        extra = ["--board", board]
    return mod.main(["--task", task_id] + extra)


# ---------------------------------------------------------------------------
# test_bridge_completes_task_on_claude_success
# ---------------------------------------------------------------------------


def test_bridge_completes_task_on_claude_success(
    kanban_home, ready_task, monkeypatch
):
    """Mock claude returning exit 0 with a summary; task must end in 'done'."""
    from hermes_cli import kanban_db as kb

    fake_output = "Smoke tests passed: 42 tests, 0 failures. All green."

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = fake_output
    fake_result.stderr = ""

    with patch("subprocess.run", return_value=fake_result) as mock_run,          patch("shutil.which", return_value="/usr/local/bin/claude"):
        rc = _run_bridge(ready_task)

    assert rc == 0, f"Expected exit 0, got {rc}"
    mock_run.assert_called_once()

    # Verify the task transitioned to 'done' with the right summary/metadata.
    with kb.connect() as conn:
        task = kb.get_task(conn, ready_task)
        assert task.status == "done", f"Expected done, got {task.status}"
        summary = kb.latest_summary(conn, ready_task)
        assert summary == fake_output.strip(), f"Summary mismatch: {summary!r}"

        # Check metadata stored on the run.
        from hermes_cli.kanban_db import list_runs
        runs = list_runs(conn, ready_task)
        # complete_task creates a run with outcome='completed' (not 'done')
        done_run = next((r for r in runs if r.outcome in ("done", "completed")), None)
        assert done_run is not None, "No completed run found"
        meta = done_run.metadata or {}
        assert meta.get("executor") == "claude-cli-bridge"
        assert meta.get("claude_exit_code") == 0


# ---------------------------------------------------------------------------
# test_bridge_blocks_task_on_claude_failure
# ---------------------------------------------------------------------------


def test_bridge_blocks_task_on_claude_failure(
    kanban_home, ready_task, monkeypatch
):
    """Mock claude returning exit 1; task must end in 'blocked' with bridge-error reason."""
    from hermes_cli import kanban_db as kb

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = ""
    fake_result.stderr = "Error: some internal claude error"

    with patch("subprocess.run", return_value=fake_result),          patch("shutil.which", return_value="/usr/local/bin/claude"):
        rc = _run_bridge(ready_task)

    assert rc != 0, f"Expected non-zero exit, got {rc}"

    with kb.connect() as conn:
        task = kb.get_task(conn, ready_task)
        assert task.status == "blocked", f"Expected blocked, got {task.status}"
        # Verify the run records a bridge-error reason.
        from hermes_cli.kanban_db import list_runs
        runs = list_runs(conn, ready_task)
        blocked_run = next(
            (r for r in runs if r.outcome == "blocked"), None
        )
        assert blocked_run is not None, "No 'blocked' run found"
        assert blocked_run.summary is not None
        assert "bridge-error" in blocked_run.summary
        assert "exit code" in blocked_run.summary.lower() or "returncode" in blocked_run.summary.lower() or "1" in blocked_run.summary


# ---------------------------------------------------------------------------
# test_bridge_blocks_task_on_subprocess_timeout
# ---------------------------------------------------------------------------


def test_bridge_blocks_task_on_subprocess_timeout(
    kanban_home, ready_task, monkeypatch
):
    """Mock subprocess.run raising TimeoutExpired; task must end in 'blocked'."""
    from hermes_cli import kanban_db as kb

    def _raise_timeout(*args, **kwargs):
        exc = subprocess.TimeoutExpired(cmd="claude", timeout=600)
        exc.stdout = None
        exc.stderr = b"partial output before timeout"
        raise exc

    with patch("subprocess.run", side_effect=_raise_timeout),          patch("shutil.which", return_value="/usr/local/bin/claude"):
        rc = _run_bridge(ready_task)

    assert rc != 0, f"Expected non-zero exit, got {rc}"

    with kb.connect() as conn:
        task = kb.get_task(conn, ready_task)
        assert task.status == "blocked", f"Expected blocked, got {task.status}"
        from hermes_cli.kanban_db import list_runs
        runs = list_runs(conn, ready_task)
        blocked_run = next(
            (r for r in runs if r.outcome == "blocked"), None
        )
        assert blocked_run is not None
        assert "bridge-error" in (blocked_run.summary or "")
        assert "timed out" in (blocked_run.summary or "").lower()
