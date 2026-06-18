"""Unit tests for VDGP (Verifiable Decision Gate Propagation).

Tests validate_gate_verdict, propagate_gate_verdict, propagate_all_gate_verdicts,
and the kanban_complete facade in hermes_cli.kanban_vdgp against the REAL
kanban_db schema (task_runs for metadata, task_events + task_comments tables,
_append_event helper).

Key: the reviewed task must be blocked via block_task() (which emits a
"blocked" event making it sticky) so recompute_ready inside complete_task
doesn't auto-promote it before VDGP gets a chance to propagate.
"""
from __future__ import annotations

import json

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli.kanban_vdgp import (
    GateVerdictError,
    validate_gate_verdict,
    propagate_gate_verdict,
    propagate_all_gate_verdicts,
)


# ---------------------------------------------------------------------------
# Fixture: isolated kanban DB
# ---------------------------------------------------------------------------

@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(kb.Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_blocked_reviewed_task(conn, task_id, assignee="apollo"):
    """Create a reviewed task and block it with a sticky block event.

    Uses block_task() so the block is sticky — recompute_ready won't
    auto-promote it when the gate task completes.
    """
    real_id = kb.create_task(
        conn, title=f"Reviewed {task_id}", assignee=assignee,
        initial_status="running",
    )
    # Override id to desired task_id
    conn.execute("UPDATE tasks SET id = ? WHERE id = ?", (task_id, real_id))
    conn.commit()
    # Block it with sticky block event
    assert kb.block_task(conn, task_id, reason="Awaiting quality gate") is True


def _create_and_complete_gate(conn, gate_id, reviewed_task, verdict, reasons=None):
    """Create a gate task and complete it with gate_verdict metadata.

    The gate_verdict ends up on the task_runs row (where metadata lives).
    """
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


# ---------------------------------------------------------------------------
# validate_gate_verdict (G4: fail-loud)
# ---------------------------------------------------------------------------

class TestValidateGateVerdict:
    def test_go_verdict_valid(self):
        validate_gate_verdict({
            "gate_verdict": {"verdict": "GO", "reviewed_task": "t_abc"}
        })

    def test_nogo_verdict_with_reasons_valid(self):
        validate_gate_verdict({
            "gate_verdict": {
                "verdict": "NO-GO",
                "reviewed_task": "t_abc",
                "reasons": ["Missing tests", "Security concern"],
            }
        })

    def test_missing_gate_verdict_key(self):
        with pytest.raises(GateVerdictError, match="Missing"):
            validate_gate_verdict({})

    def test_gate_verdict_not_dict(self):
        with pytest.raises(GateVerdictError, match="must be a dictionary"):
            validate_gate_verdict({"gate_verdict": "GO"})

    def test_invalid_verdict_value(self):
        with pytest.raises(GateVerdictError, match="Invalid verdict"):
            validate_gate_verdict({
                "gate_verdict": {"verdict": "MAYBE", "reviewed_task": "t_abc"}
            })

    def test_missing_reviewed_task(self):
        with pytest.raises(GateVerdictError, match="Missing 'reviewed_task'"):
            validate_gate_verdict({
                "gate_verdict": {"verdict": "GO"}
            })

    def test_nogo_without_reasons_rejected(self):
        """NO-GO without any reasons is invalid (G4)."""
        with pytest.raises(GateVerdictError, match="at least one reason"):
            validate_gate_verdict({
                "gate_verdict": {"verdict": "NO-GO", "reviewed_task": "t_abc"}
            })

    def test_nogo_with_empty_reasons_list_rejected(self):
        with pytest.raises(GateVerdictError, match="at least one reason"):
            validate_gate_verdict({
                "gate_verdict": {
                    "verdict": "NO-GO",
                    "reviewed_task": "t_abc",
                    "reasons": [],
                }
            })


# ---------------------------------------------------------------------------
# propagate_gate_verdict
# ---------------------------------------------------------------------------

class TestPropagateGateVerdict:
    def test_go_unblocks_reviewed_task(self, kanban_home):
        """GO verdict auto-unblocks the reviewed task (G3)."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_reviewed")
            _create_and_complete_gate(conn, "t_gate", "t_reviewed", "GO")
            # Verify the reviewed task is still blocked after gate completion
            # (sticky block prevents recompute_ready from auto-promoting)
            task = kb.get_task(conn, "t_reviewed")
            assert task.status == "blocked", (
                f"Expected blocked, got {task.status} — sticky block not working?"
            )
            result = propagate_gate_verdict(
                conn, "t_gate",
                {"verdict": "GO", "reviewed_task": "t_reviewed"},
            )
            assert result is True
            task = kb.get_task(conn, "t_reviewed")
            assert task.status == "ready"

    def test_nogo_unblocks_and_comments(self, kanban_home):
        """NO-GO verdict unblocks to ready AND posts reasons as a comment (G3)."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_reviewed2")
            _create_and_complete_gate(
                conn, "t_nogate", "t_reviewed2", "NO-GO",
                reasons=["Insufficient test coverage", "Missing error handling"],
            )
            result = propagate_gate_verdict(
                conn, "t_nogate",
                {
                    "verdict": "NO-GO",
                    "reviewed_task": "t_reviewed2",
                    "reasons": ["Insufficient test coverage", "Missing error handling"],
                },
            )
            assert result is True
            task = kb.get_task(conn, "t_reviewed2")
            assert task.status == "ready"
            comments = kb.list_comments(conn, "t_reviewed2")
            assert len(comments) >= 1
            assert "NO-GO" in comments[-1].body
            assert "Insufficient test coverage" in comments[-1].body

    def test_idempotency_no_double_event(self, kanban_home):
        """Second propagation should be skipped (idempotent)."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_rev_idem")
            _create_and_complete_gate(conn, "t_gate_idem", "t_rev_idem", "GO")
            verdict_data = {"verdict": "GO", "reviewed_task": "t_rev_idem"}
            assert propagate_gate_verdict(conn, "t_gate_idem", verdict_data) is True
            assert propagate_gate_verdict(conn, "t_gate_idem", verdict_data) is False
            events = conn.execute(
                "SELECT COUNT(*) FROM task_events WHERE task_id = ? AND kind = 'gate_go'",
                ("t_gate_idem",),
            ).fetchone()
            assert events[0] == 1

    def test_already_moved_on_skip(self, kanban_home):
        """If the reviewed task is not 'blocked', propagation is skipped."""
        with kb.connect() as conn:
            # Create reviewed task in 'running' (not blocked)
            real_id = kb.create_task(
                conn, title="Already running", assignee="apollo",
                initial_status="running",
            )
            conn.execute(
                "UPDATE tasks SET id = 't_notblocked' WHERE id = ?",
                (real_id,),
            )
            conn.commit()
            _create_and_complete_gate(conn, "t_gate_skip", "t_notblocked", "GO")
            result = propagate_gate_verdict(
                conn, "t_gate_skip",
                {"verdict": "GO", "reviewed_task": "t_notblocked"},
            )
            assert result is False

    def test_nonexistent_reviewed_task_skip(self, kanban_home):
        """If the reviewed task doesn't exist, propagation is skipped."""
        with kb.connect() as conn:
            _create_and_complete_gate(conn, "t_gate_ghost", "t_nonexistent", "GO")
            result = propagate_gate_verdict(
                conn, "t_gate_ghost",
                {"verdict": "GO", "reviewed_task": "t_nonexistent"},
            )
            assert result is False

    def test_non_gate_passthrough(self, kanban_home):
        """A task without gate_verdict metadata should not be propagated."""
        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="Regular task", assignee="apollo")
            kb.complete_task(conn, task_id, summary="done")
            count = propagate_all_gate_verdicts(conn)
            assert count == 0


# ---------------------------------------------------------------------------
# propagate_all_gate_verdicts (tick sweep)
# ---------------------------------------------------------------------------

class TestPropagateAllGateVerdicts:
    def test_tick_propagates_pending_verdicts(self, kanban_home):
        """Tick sweep picks up done gate tasks and propagates their verdicts."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_rev_tick")
            _create_and_complete_gate(conn, "t_gate_tick", "t_rev_tick", "GO")
            count = propagate_all_gate_verdicts(conn)
            assert count == 1
            task = kb.get_task(conn, "t_rev_tick")
            assert task.status == "ready"

    def test_tick_counts_multiple_verdicts(self, kanban_home):
        """Tick sweep processes all pending gate tasks."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_r_multi1")
            _create_blocked_reviewed_task(conn, "t_r_multi2")
            _create_and_complete_gate(conn, "t_g_multi1", "t_r_multi1", "GO")
            _create_and_complete_gate(
                conn, "t_g_multi2", "t_r_multi2", "NO-GO",
                reasons=["Needs work"],
            )
            count = propagate_all_gate_verdicts(conn)
            assert count == 2

    def test_tick_skips_already_propagated(self, kanban_home):
        """Second tick should find no new verdicts to propagate."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_rev_reprop")
            _create_and_complete_gate(conn, "t_gate_reprop", "t_rev_reprop", "GO")
            assert propagate_all_gate_verdicts(conn) == 1
            assert propagate_all_gate_verdicts(conn) == 0

    def test_tick_skips_invalid_verdict_gracefully(self, kanban_home):
        """Invalid verdict in run metadata should be logged but not crash the sweep."""
        with kb.connect() as conn:
            _create_blocked_reviewed_task(conn, "t_rev_bad")
            # Create a gate task and complete it normally, then inject
            # invalid gate_verdict metadata directly into task_runs
            real_id = kb.create_task(conn, title="Bad gate", assignee="athena")
            conn.execute(
                "UPDATE tasks SET id = 't_badgate' WHERE id = ?",
                (real_id,),
            )
            conn.commit()
            kb.complete_task(conn, "t_badgate", summary="Bad gate run")
            # Now inject bad metadata into the most recent run
            bad_meta = json.dumps({
                "gate_verdict": {"verdict": "NO-GO", "reviewed_task": "t_rev_bad"}
                # Missing 'reasons' — invalid per G4
            })
            conn.execute(
                "UPDATE task_runs SET metadata = ? WHERE task_id = ? AND outcome = 'completed'",
                (bad_meta, "t_badgate"),
            )
            conn.commit()
            # Should not raise, returns 0 (invalid verdict skipped)
            count = propagate_all_gate_verdicts(conn)
            assert count == 0


# ---------------------------------------------------------------------------
# kanban_complete facade
# ---------------------------------------------------------------------------

class TestKanbanCompleteFacade:
    def test_facade_delegates_to_complete_task(self, kanban_home):
        """kanban_complete in vdgp module is a thin facade over kanban_db.complete_task."""
        from hermes_cli.kanban_vdgp import kanban_complete as vdgp_complete

        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="Test task", assignee="apollo")
            result = vdgp_complete(conn, task_id, summary="done", metadata={"key": "val"})
            assert result is True
            task = kb.get_task(conn, task_id)
            assert task.status == "done"

    def test_facade_validates_gate_verdict_on_complete(self, kanban_home):
        """Facade rejects completion with invalid gate_verdict (G4)."""
        from hermes_cli.kanban_vdgp import kanban_complete as vdgp_complete

        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="Gate task", assignee="athena")
            with pytest.raises(GateVerdictError):
                vdgp_complete(conn, task_id, metadata={
                    "gate_verdict": {"verdict": "NO-GO", "reviewed_task": "t_x"}
                    # Missing reasons — should be rejected
                })

    def test_facade_allows_valid_gate_verdict_on_complete(self, kanban_home):
        """Facade allows completion with valid gate_verdict."""
        from hermes_cli.kanban_vdgp import kanban_complete as vdgp_complete

        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="Gate task", assignee="athena")
            result = vdgp_complete(conn, task_id, metadata={
                "gate_verdict": {
                    "verdict": "GO",
                    "reviewed_task": "t_reviewed",
                }
            })
            assert result is True


# ---------------------------------------------------------------------------
# DispatchResult.gate_propagations field
# ---------------------------------------------------------------------------

class TestDispatchResultField:
    def test_gate_propagations_default_zero(self):
        dr = kb.DispatchResult()
        assert dr.gate_propagations == 0

    def test_gate_propagations_settable(self):
        dr = kb.DispatchResult()
        dr.gate_propagations = 5
        assert dr.gate_propagations == 5
