"""Tests for the unified Hermes governed runtime snapshot."""

from __future__ import annotations

from pathlib import Path

from gateway.governed_runtime_snapshot import build_governed_runtime_snapshot


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_governed_runtime_snapshot_aggregates_wave_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
model:
  provider: openai-codex
  default: gpt-5.4
fallback_providers:
  - provider: google
    model: gemini-2.0-flash
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_operator_mission_surface",
        lambda: {
            "schema": "hermes.operator_mission_surface.v1",
            "headline": "Gateway healthy",
            "recommended_actions": [],
            "gateway": {"state": "running"},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_operator_triage_surface",
        lambda: {
            "schema": "hermes.operator_triage_surface.v1",
            "severity": "info",
            "issue_count": 0,
            "issues": [],
            "summary": "No operator action required",
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_continuity_queue_snapshot",
        lambda: {
            "schema": "hermes.continuity_queue_snapshot.v1",
            "queue": {"resumable": [], "blocked": []},
            "totals": {"blocked": 0},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_routing_governance_snapshot",
        lambda **_: {
            "schema": "hermes.session_topology_routing_snapshot.v1",
            "parity_validation": {"tasks_without_any_policy_candidate": []},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_release_evidence_bundle",
        lambda **_: {"release_id": "rel_runtime_snapshot", "stages": []},
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.evaluate_release_evidence_ladder",
        lambda **_: {"verdict": "pass", "gate_results": []},
    )

    snapshot = build_governed_runtime_snapshot(
        repo_root=REPO_ROOT,
        config_path=config_path,
        release_id="rel_runtime_snapshot",
    )

    assert snapshot["schema"] == "hermes.governed_runtime_snapshot.v1"
    assert snapshot["overall_status"] == "healthy"
    assert snapshot["summary"]["operator_issue_count"] == 0
    assert snapshot["summary"]["release_block_count"] == 0
    assert snapshot["summary"]["routing_policy_gap_count"] == 0
    assert snapshot["summary"]["blocked_queue_count"] == 0
    assert snapshot["snapshot_path"].endswith("governed_runtime/latest_snapshot.json")


def test_build_governed_runtime_snapshot_degrades_when_release_or_queue_has_issues(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config_path = tmp_path / "config.yaml"
    config_path.write_text("model:\n  provider: openai-codex\n  default: gpt-5.4\n", encoding="utf-8")

    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_operator_mission_surface",
        lambda: {
            "schema": "hermes.operator_mission_surface.v1",
            "headline": "Gateway needs operator attention",
            "recommended_actions": ["Inspect gateway runtime artifact validity"],
            "gateway": {"state": "running"},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_operator_triage_surface",
        lambda: {
            "schema": "hermes.operator_triage_surface.v1",
            "severity": "warning",
            "issue_count": 1,
            "issues": [{"summary": "Gateway restart has been requested"}],
            "summary": "Operator action required",
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_continuity_queue_snapshot",
        lambda: {
            "schema": "hermes.continuity_queue_snapshot.v1",
            "queue": {"resumable": [{"task_id": "task_a"}], "blocked": [{"task_id": "task_b"}]},
            "totals": {"blocked": 1},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_routing_governance_snapshot",
        lambda **_: {
            "schema": "hermes.session_topology_routing_snapshot.v1",
            "parity_validation": {"tasks_without_any_policy_candidate": ["research"]},
        },
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.build_release_evidence_bundle",
        lambda **_: {"release_id": "rel_runtime_snapshot", "stages": []},
    )
    monkeypatch.setattr(
        "gateway.governed_runtime_snapshot.evaluate_release_evidence_ladder",
        lambda **_: {
            "verdict": "block",
            "gate_results": [{"gate_id": "stage_coverage", "status": "block"}],
        },
    )

    snapshot = build_governed_runtime_snapshot(
        repo_root=REPO_ROOT,
        config_path=config_path,
        release_id="rel_runtime_snapshot",
    )

    assert snapshot["overall_status"] == "degraded"
    assert snapshot["summary"]["operator_issue_count"] == 1
    assert snapshot["summary"]["release_block_count"] == 1
    assert snapshot["summary"]["routing_policy_gap_count"] == 1
    assert snapshot["summary"]["blocked_queue_count"] == 1
    assert any("Resolve release evidence ladder blocks" in item for item in snapshot["recommended_actions"])
    assert any("Unblock continuity queue tasks" in item for item in snapshot["recommended_actions"])
