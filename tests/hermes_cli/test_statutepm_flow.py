from __future__ import annotations

import json
from pathlib import Path

from hermes_cli import control_db as cp
from hermes_cli.control import _sample_payload
from hermes_cli.control_worker import run_deterministic_dispatch
from hermes_cli.statutepm_flow import StatutePMFlow


def test_statutepm_idle_registers_fresh_instance_then_offlines_it(tmp_path):
    root = tmp_path / ".hermes"
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=False)
    finally:
        conn.close()

    flow = StatutePMFlow(root=root, pm_instance_id="statutepm:wave-test", poll_interval_s=0, child_timeout_s=1)
    assert flow.run_once() is None

    conn = cp.connect(root=root)
    try:
        row = conn.execute("SELECT profile_id, status FROM cp_profile_instances WHERE instance_id=?", ("statutepm:wave-test",)).fetchone()
        assert row is not None
        assert row["profile_id"] == "statutepm"
        assert row["status"] == "offline"
    finally:
        conn.close()


def test_statutepm_active_run_uses_idempotent_child_and_offlines_pm(tmp_path):
    root = tmp_path / ".hermes"
    repo = tmp_path / "repo"
    repo.mkdir()
    conn = cp.connect(root=root)
    try:
        boot = cp.bootstrap_statutepm_policies(conn, seed_instances=True)
        parent = cp.create_dispatch_from_instance(
            conn,
            sender_instance_id=boot["instances"]["default"],
            receiver_profile="statutepm",
            payload=_sample_payload(repo),
            idempotency_key="parent-wave-1",
        )
    finally:
        conn.close()

    spawned = []

    def fake_spawn(child_id: str, payload: dict, child_root: Path | None, parent_id: str) -> int:
        spawned.append(child_id)
        run_deterministic_dispatch(root=child_root, profile_id="statute-worker", instance_id="statute-worker:test", dispatch_id=child_id)
        return 42

    flow = StatutePMFlow(root=root, pm_instance_id="statutepm:wave-1", spawn_child=fake_spawn, poll_interval_s=0, child_timeout_s=2)
    outcome = flow.run_once()
    assert outcome and outcome["status"] == "completed"
    assert len(spawned) == 1

    conn = cp.connect(root=root)
    try:
        pm_row = conn.execute("SELECT status FROM cp_profile_instances WHERE instance_id=?", ("statutepm:wave-1",)).fetchone()
        assert pm_row["status"] == "offline"
        child_rows = conn.execute("SELECT idempotency_key, parent_dispatch_id FROM cp_dispatches WHERE receiver_profile='statute-worker'").fetchall()
        assert len(child_rows) == 1
        assert child_rows[0]["parent_dispatch_id"] == parent
        assert child_rows[0]["idempotency_key"] == f"pm-child:{parent}:worker:0:0"
    finally:
        conn.close()


def test_statutepm_rejects_child_success_without_valid_result_contract(tmp_path):
    root = tmp_path / ".hermes"
    repo = tmp_path / "repo"
    repo.mkdir()
    conn = cp.connect(root=root)
    try:
        boot = cp.bootstrap_statutepm_policies(conn, seed_instances=True)
        parent = cp.create_dispatch_from_instance(conn, sender_instance_id=boot["instances"]["default"], receiver_profile="statutepm", payload=_sample_payload(repo))
    finally:
        conn.close()

    def bad_spawn(child_id: str, payload: dict, child_root: Path | None, parent_id: str) -> int:
        worker = cp.connect(root=child_root)
        try:
            cp.register_instance(worker, "statute-worker", instance_id="statute-worker:bad")
            ok, epoch = cp.claim_dispatch_by_id(worker, dispatch_id=child_id, instance_id="statute-worker:bad")
            assert ok and epoch is not None
            cp.advance_dispatch(worker, child_id, instance_id="statute-worker:bad", lease_epoch=epoch, status="running")
            cp.record_result(worker, dispatch_id=child_id, instance_id="statute-worker:bad", lease_epoch=epoch, result={"status": "completed", "summary": "missing schema"})
            cp.advance_dispatch(worker, child_id, instance_id="statute-worker:bad", lease_epoch=epoch, status="completed")
        finally:
            worker.close()
        return 99

    outcome = StatutePMFlow(root=root, pm_instance_id="statutepm:bad-child", spawn_child=bad_spawn, poll_interval_s=0, child_timeout_s=2).run_once()
    assert outcome and outcome["status"] == "failed"

    conn = cp.connect(root=root)
    try:
        latest = cp.get_latest_dispatch_result(conn, parent)["result"]
        assert latest["status"] == "action_required"
        assert latest["blockers"]
    finally:
        conn.close()
