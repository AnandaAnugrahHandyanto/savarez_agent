"""E2E tests for VDGP integration in the dispatch loop.

Tests that dispatch_once correctly invokes propagate_all_gate_verdicts
and surfaces the count in DispatchResult.gate_propagations against a
real temp HERMES_HOME database (no mocks on the DB layer).
"""
from __future__ import annotations

import json

import pytest

from hermes_cli import kanban_db as kb


# ---------------------------------------------------------------------------
# Fixture: isolated kanban DB with all_assignees_spawnable
# ---------------------------------------------------------------------------

@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    from pathlib import Path
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.fixture
def all_assignees_spawnable(monkeypatch):
    """Pretend every assignee maps to a real Hermes profile."""
    from hermes_cli import profiles
    monkeypatch.setattr(profiles, "profile_exists", lambda name: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_and_complete_gate(conn, gate_id, reviewed_task, verdict, reasons=None):
    """Create a gate task, complete it with gate_verdict metadata on task_runs."""
    real_id = kb.create_task(
        conn, title=f"Gate {gate_id}", assignee="athena",
        initial_status="running",
    )
    conn.execute("UPDATE tasks SET id = ? WHERE id = ?", (gate_id, real_id))
    conn.commit()

    vdgp_meta = {"verdict": verdict, "reviewed_task": reviewed_task}
    if reasons:
        vdgp_meta["reasons"] = reasons
    metadata = {"gate_verdict": vdgp_meta}
    kb.complete_task(conn, gate_id, summary=f"Gate {verdict}", metadata=metadata)


def _create_blocked_task(conn, task_id, assignee="apollo"):
    """Create a task and block it with a sticky block event.

    Uses block_task() so the block is sticky — recompute_ready won't
    auto-promote it when the gate task completes.
    """
    real_id = kb.create_task(
        conn, title=f"Reviewed {task_id}", assignee=assignee,
        initial_status="running",
    )
    conn.execute("UPDATE tasks SET id = ? WHERE id = ?", (task_id, real_id))
    conn.commit()
    assert kb.block_task(conn, task_id, reason="Awaiting quality gate") is True


# ---------------------------------------------------------------------------
# dispatch_once VDGP integration
# ---------------------------------------------------------------------------

class TestDispatchOnceVDGP:
    def test_dispatch_propagates_go_verdict(self, kanban_home, all_assignees_spawnable):
        """dispatch_once picks up a done gate task and propagates GO to the reviewed task."""
        with kb.connect() as conn:
            _create_blocked_task(conn, "t_feature")
            _create_and_complete_gate(conn, "t_qagate", "t_feature", "GO")

            # Run dispatch with a no-op spawn stub (we only care about VDGP)
            result = kb.dispatch_once(conn, spawn_fn=lambda task, ws: None)

        # VDGP propagation count should be 1
        assert result.gate_propagations == 1
        # After VDGP unblocks to ready, dispatch spawns the task in the same
        # tick, transitioning it to running. The spawned list confirms VDGP
        # successfully unblocked it and dispatch picked it up.
        spawned_ids = [tid for tid, _, _ in result.spawned]
        assert "t_feature" in spawned_ids

    def test_dispatch_propagates_nogo_verdict(self, kanban_home, all_assignees_spawnable):
        """dispatch_once propagates NO-GO — unblocks + adds comment."""
        with kb.connect() as conn:
            _create_blocked_task(conn, "t_feature2")
            _create_and_complete_gate(
                conn, "t_revgate", "t_feature2", "NO-GO",
                reasons=["Needs more unit tests"],
            )

            result = kb.dispatch_once(conn, spawn_fn=lambda task, ws: None)

        assert result.gate_propagations == 1
        # Same as GO: unblock → ready → spawn → running in one tick.
        spawned_ids = [tid for tid, _, _ in result.spawned]
        assert "t_feature2" in spawned_ids
        # Comment with NO-GO reasons should be present
        with kb.connect() as conn:
            comments = kb.list_comments(conn, "t_feature2")
            assert len(comments) >= 1
            assert "NO-GO" in comments[-1].body

    def test_dispatch_zero_propagations_when_no_gates(self, kanban_home, all_assignees_spawnable):
        """dispatch_once returns gate_propagations=0 when there are no gate tasks."""
        with kb.connect() as conn:
            # Just regular tasks, no gate_verdict
            kb.create_task(conn, title="Normal task", assignee="apollo")
            result = kb.dispatch_once(conn, spawn_fn=lambda task, ws: None)

        assert result.gate_propagations == 0

    def test_dispatch_does_not_repropagate(self, kanban_home, all_assignees_spawnable):
        """Second dispatch tick should not re-propagate already-processed verdicts."""
        with kb.connect() as conn:
            _create_blocked_task(conn, "t_r3")
            _create_and_complete_gate(conn, "t_g3", "t_r3", "GO")

            # First tick: propagate
            result1 = kb.dispatch_once(conn, spawn_fn=lambda task, ws: None)
            assert result1.gate_propagations == 1

            # Second tick: already processed
            result2 = kb.dispatch_once(conn, spawn_fn=lambda task, ws: None)
            assert result2.gate_propagations == 0
