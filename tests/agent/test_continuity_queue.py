from __future__ import annotations

from agent.continuity_queue import build_snapshot, claim_task, enqueue_task, read_state, transition_task


def test_claim_task_blocks_on_dependency_and_unlocks_when_dependency_done(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    enqueue_task(task_id="task_a", title="Prepare evidence", role_required="operator")
    enqueue_task(task_id="task_b", title="Publish evidence", role_required="operator", dependencies=["task_a"])

    blocked = claim_task(task_id="task_b", actor_id="yan", actor_role="operator")
    assert blocked["state"] == "BLOCKED"
    assert "dependency_blocked" in blocked["blocked_reason"]

    claim_task(task_id="task_a", actor_id="yan", actor_role="operator")
    transition_task(task_id="task_a", to_state="DONE", actor_id="yan", actor_role="operator")
    claimed = claim_task(task_id="task_b", actor_id="yan", actor_role="operator")
    assert claimed["state"] == "RUNNING"


def test_claim_task_enforces_file_lock_conflicts(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    enqueue_task(task_id="task_a", title="Mutate one file", role_required="executor", file_targets=["docs/ops/plan.md"])
    enqueue_task(task_id="task_b", title="Mutate same file", role_required="executor", file_targets=["docs/ops/plan.md"])

    running = claim_task(task_id="task_a", actor_id="yan", actor_role="executor")
    assert running["state"] == "RUNNING"

    blocked = claim_task(task_id="task_b", actor_id="yan", actor_role="executor")
    assert blocked["state"] == "BLOCKED"
    assert "file_lock_conflict" in blocked["blocked_reason"]


def test_transition_task_emits_handoff_packet_and_releases_lock_on_done(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    enqueue_task(task_id="task_a", title="Review routing snapshot", role_required="validator", file_targets=["memory/routing.md"])

    claim_task(task_id="task_a", actor_id="yan", actor_role="validator")
    reviewed = transition_task(
        task_id="task_a",
        to_state="REVIEW",
        actor_id="yan",
        actor_role="validator",
        evidence_refs=["memory/evidence.json"],
        artifact_refs=["memory/routing.md"],
        next_role="librarian",
    )
    assert reviewed["state"] == "REVIEW"
    state = read_state()
    assert state["handoff_packets"][0]["to_role"] == "librarian"
    assert state["locks"]["memory/routing.md"]["state"] == "ACTIVE"

    done = transition_task(task_id="task_a", to_state="DONE", actor_id="yan", actor_role="librarian")
    assert done["state"] == "DONE"
    state = read_state()
    assert state["locks"]["memory/routing.md"]["state"] == "RELEASED"


def test_build_snapshot_projects_ready_running_blocked_and_resumable(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    enqueue_task(task_id="task_ready", title="Ready now", role_required="operator")
    enqueue_task(task_id="task_run", title="In flight", role_required="operator")
    enqueue_task(task_id="task_blocked", title="Blocked by dep", role_required="operator", dependencies=["missing_dep"])

    claim_task(task_id="task_run", actor_id="yan", actor_role="operator")
    claim_task(task_id="task_blocked", actor_id="yan", actor_role="operator")

    snapshot = build_snapshot()

    assert snapshot["schema"] == "hermes.continuity_queue_snapshot.v1"
    assert [item["task_id"] for item in snapshot["queue"]["ready"]] == ["task_ready"]
    assert [item["task_id"] for item in snapshot["queue"]["running"]] == ["task_run"]
    assert [item["task_id"] for item in snapshot["queue"]["blocked"]] == ["task_blocked"]
    assert [item["task_id"] for item in snapshot["queue"]["resumable"]] == ["task_run"]
    assert snapshot["snapshot_path"].endswith("latest_snapshot.json")
