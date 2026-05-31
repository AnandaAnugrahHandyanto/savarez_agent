from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hermes_cli import control_db as cp
from hermes_cli.control_worker import ControlDispatchWorker, run_agent_dispatch, run_deterministic_dispatch


def _payload(root: Path, parent: str | None = None):
    return {
        "schema": "statute_dispatch_v1",
        "silo": "statute",
        "repo_root": str(root),
        "allowed_paths": [str(root)],
        "task_type": "generic",
        "task_permissions": ["read", "test"],
        "parent_dispatch_id": parent,
        "instructions": "work",
        "constraints": {"no_live_db_mutation": True, "no_push": True},
    }


def test_control_worker_claims_records_artifact_and_completes(tmp_path):
    root = tmp_path / ".hermes"
    repo = tmp_path / "repo"
    repo.mkdir()
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=True)
        pm = "statutepm:bootstrap"
        did = cp.create_dispatch_from_instance(conn, sender_instance_id=pm, receiver_profile="statute-worker", payload=_payload(repo, parent="disp_parent"))
    finally:
        conn.close()

    result = run_deterministic_dispatch(root=root, profile_id="statute-worker", instance_id="statute-worker:test", dispatch_id=did)
    assert result["lease_epoch"] == 1
    conn = cp.connect(root=root)
    try:
        row = conn.execute("SELECT status FROM cp_dispatches WHERE dispatch_id=?", (did,)).fetchone()
        assert row["status"] == "completed"
        assert cp.get_latest_dispatch_result(conn, did)["result"]["status"] == "completed"
        artifacts = cp.list_artifacts(conn, did)
        assert artifacts
        artifact_path = Path(artifacts[0]["path"])
        assert artifact_path.exists()
        artifact = json.loads(artifact_path.read_text())
        assert artifact["dispatch_id"] == did
        assert artifact["status"] == "completed"
        inst = conn.execute("SELECT status, lease_expires_at_ms FROM cp_profile_instances WHERE instance_id='statute-worker:test'").fetchone()
        assert inst["status"] == "offline"
        assert inst["lease_expires_at_ms"] is not None
    finally:
        conn.close()


def test_claim_next_returns_none_without_work(tmp_path):
    worker = ControlDispatchWorker("statute-worker", "statute-worker:test", tmp_path / ".hermes")
    worker.heartbeat_once()
    assert worker.claim_next() is None


def test_agent_worker_builds_prompt_runs_subprocess_and_records_result(tmp_path):
    root = tmp_path / ".hermes"
    repo = tmp_path / "repo"
    repo.mkdir()
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=True)
        did = cp.create_dispatch_from_instance(conn, sender_instance_id="statutepm:bootstrap", receiver_profile="statute-worker", payload=_payload(repo, parent="disp_parent"))
    finally:
        conn.close()

    calls = {}

    def fake_runner(cmd, *, env, input_text, timeout_s, cwd):
        calls["cmd"] = cmd
        calls["env"] = env
        calls["input_text"] = input_text
        calls["timeout_s"] = timeout_s
        calls["cwd"] = cwd
        result = {
            "schema": "control_result_v1",
            "status": "completed",
            "summary": "agent completed",
            "artifacts": [],
            "tests": [{"command": "fake", "exit_code": 0}],
            "blockers": [],
        }
        return {"returncode": 0, "stdout": "CONTROL_RESULT_JSON:" + json.dumps(result), "stderr": ""}

    result = run_agent_dispatch(root=root, profile_id="statute-worker", instance_id="statute-worker:agent", dispatch_id=did, runner=fake_runner, timeout_s=5)
    assert result["result"]["summary"] == "agent completed"
    assert "statute_dispatch_v1" in calls["input_text"]
    assert calls["env"]["HERMES_CONTROL_DISPATCH_ID"] == did
    assert calls["env"]["HERMES_CONTROL_LEASE_EPOCH"] == "1"
    assert calls["cmd"][-2:] == ["--query", "-"]
    assert "--ignore-rules" not in calls["cmd"]
    assert "--yolo" not in calls["cmd"]
    assert "--resume" not in calls["cmd"]

    conn = cp.connect(root=root)
    try:
        row = conn.execute("SELECT status FROM cp_dispatches WHERE dispatch_id=?", (did,)).fetchone()
        assert row["status"] == "completed"
        latest = cp.get_latest_dispatch_result(conn, did)["result"]
        assert latest["status"] == "completed"
        inst = conn.execute("SELECT status FROM cp_profile_instances WHERE instance_id='statute-worker:agent'").fetchone()
        assert inst["status"] == "offline"
    finally:
        conn.close()


def test_agent_worker_fails_malformed_success_output(tmp_path):
    root = tmp_path / ".hermes"
    repo = tmp_path / "repo"
    repo.mkdir()
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=True)
        did = cp.create_dispatch_from_instance(conn, sender_instance_id="statutepm:bootstrap", receiver_profile="statute-worker", payload=_payload(repo, parent="disp_parent"))
    finally:
        conn.close()

    def fake_runner(cmd, *, env, input_text, timeout_s, cwd):
        return {"returncode": 0, "stdout": "looks fine", "stderr": ""}

    result = run_agent_dispatch(root=root, profile_id="statute-worker", instance_id="statute-worker:agent-bad", dispatch_id=did, runner=fake_runner, timeout_s=5)
    assert result["result"]["status"] == "failed"
    assert result["result"]["blockers"][0]["kind"] == "runtime_error"
