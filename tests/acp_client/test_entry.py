"""Tests for the acp_client CLI entrypoints.

These exercise the Kanban runner wrapper without launching a real ACP backend.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from acp_client import entry
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(kb.Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.mark.asyncio
async def test_run_kanban_task_blocks_with_diagnostic_on_launch_failure(
    kanban_home, tmp_path, monkeypatch
):
    """ACP launch/handshake errors must not leave a task claimed forever."""

    with kb.connect_closing() as conn:
        task_id = kb.create_task(conn, title="acp launch failure", assignee="gond")
        claimed = kb.claim_task(conn, task_id)
        assert claimed is not None

    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", str(claimed.current_run_id))

    import acp_client.kanban_runner as runner

    def fake_build_launch_plan(*, workspace, backend, env, strict):
        assert strict is True
        return SimpleNamespace(backend=backend)

    async def fake_run_acp_lane(*args, **kwargs):
        raise RuntimeError("initialize timed out")

    monkeypatch.setattr(runner, "build_launch_plan", fake_build_launch_plan)
    monkeypatch.setattr(runner, "run_acp_lane", fake_run_acp_lane)

    rc = await entry._run_kanban_task(
        task_id, workspace=str(tmp_path), backend="claude"
    )

    assert rc == 1
    with kb.connect_closing() as conn:
        task = kb.get_task(conn, task_id)
        assert task is not None
        assert task.status == "blocked"
        assert task.claim_lock is None
        row = conn.execute(
            "SELECT outcome, summary FROM task_runs WHERE id = ?",
            (claimed.current_run_id,),
        ).fetchone()
        assert row["outcome"] == "blocked"
        assert "ACP lane failed to launch backend 'claude'" in row["summary"]
        assert "initialize timed out" in row["summary"]