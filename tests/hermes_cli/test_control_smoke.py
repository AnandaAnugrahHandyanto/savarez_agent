from __future__ import annotations

from pathlib import Path

from hermes_cli import control_db as cp
from hermes_cli.control import _readiness, _run_statutepm_live_smoke, _run_statutepm_smoke
from hermes_cli.control_runtime import resolve_control_target
from hermes_cli.control_worker import run_deterministic_dispatch


def test_control_smoke_statutepm_isolated_root(tmp_path):
    result = _run_statutepm_smoke(tmp_path / ".hermes", (tmp_path / ".hermes" / "control-plane" / "control.db").resolve())
    assert result["ok"] is True
    assert result["spawned"]


def test_readiness_temp_root_reports_implementation_ready(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda name: name == "statute-worker")
    monkeypatch.setattr("hermes_cli.control.worker_spawnability_status", lambda *_args, **_kwargs: {"status": "dry_run_ok", "command": [], "returncode": 0, "stderr": ""})
    monkeypatch.setattr("hermes_cli.control.help_parse_status", lambda *_args, **_kwargs: {"ok": True, "returncode": 0, "stderr": "", "command": []})
    target = resolve_control_target(root=tmp_path / ".hermes")
    result = _readiness(type("Args", (), {"live_check": False})(), target)
    assert result["implementation_ready"] is True
    assert result["live_ready"] is False
    assert result["profile_mapping"] == {"statutepm": "nj-statutes-pm"}
    assert result["agent_worker_ready"] is True


def test_live_smoke_helper_verifies_temp_root_without_real_subprocess(tmp_path):
    root = tmp_path / ".hermes"
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=True)
    finally:
        conn.close()
    target = resolve_control_target(root=root)

    def fake_spawn(child_id, payload, child_root, parent_id):
        run_deterministic_dispatch(root=child_root, profile_id="statute-worker", instance_id="statute-worker:smoke", dispatch_id=child_id)
        return 7

    result = _run_statutepm_live_smoke(
        target,
        smoke_tag="unit-smoke",
        idempotency_key="unit-smoke-v1",
        deterministic=True,
        spawn_child=fake_spawn,
    )
    assert result["ok"] is True
    assert result["verification"]["child_result_exists"] is True
    assert result["verification"]["artifacts_contained"] is True
    assert result["verification"]["artifact_files_exist"] is True


def test_readiness_live_check_reports_lease_health_from_isolated_home(tmp_path, monkeypatch):
    root = tmp_path / ".hermes"
    conn = cp.connect(root=root)
    try:
        cp.bootstrap_statutepm_policies(conn, seed_instances=True)
    finally:
        conn.close()
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda name: name in {"default", "nj-statutes-pm", "statute-worker"})
    monkeypatch.setattr("hermes_cli.control.worker_spawnability_status", lambda *_args, **_kwargs: {"status": "dry_run_ok", "command": [], "returncode": 0, "stderr": ""})
    monkeypatch.setattr("hermes_cli.control.help_parse_status", lambda *_args, **_kwargs: {"ok": True, "returncode": 0, "stderr": "", "command": []})
    target = resolve_control_target(live=True)
    result = _readiness(type("Args", (), {"live_check": True})(), target)
    assert result["live_ready"] is True
    assert result["deterministic_operational_ready"] is True
    assert result["cutover_state"] in {"already_control_db", "safe_to_cutover_deterministic"}
    assert result["seeded_instance_leases"]["default:bootstrap"]["live"] is True
    assert result["runtime_profiles"]["nj-statutes-pm"] == "present"
