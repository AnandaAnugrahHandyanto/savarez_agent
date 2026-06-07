from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def test_context_control_state_reads_existing_pilot_reports(tmp_path, monkeypatch):
    pilot = tmp_path / "context-ci-pilot-001"
    phase = pilot / "reports/pilot-001/phase-c"
    live = pilot / ".hermes/context-control-plane/pilot-001/live-window"
    switch = pilot / ".hermes/context-control-plane/pilot-001/switch/switch-1"
    baseline = pilot / ".hermes/context-control-plane/pilot-001/baseline/run-1"

    write_json(phase / "eval-report.json", {
        "eval_0": {"passed": True},
        "visible_tasks": {"visible-a": {"passed": True}, "visible-b": {"passed": True}},
        "hidden_variants": {"aggregate": {"passed": 12, "count": 12, "pass_rate": 1.0}},
        "task_pass_rate": 1.0,
        "task_pass_rate_per_token": 0.005,
        "candidate_vs_baseline": {"token_delta": -13, "token_delta_pct": -6.2},
        "verification_budget": {"passed": False},
    })
    write_json(phase / "diff-packet.json", {
        "managed_scope": {"blocks": 8, "sources": 8},
        "findings": {"stale": [], "duplicates": [], "conflicts": [], "scope_leakage": [], "precedence_conflicts": []},
        "proposals": [{"id": "chief-os-pilot-001", "project": "Chief OS", "summary": "remove stale tokens", "safety_critical_blocks": ["safety.menu-ca-research-only"], "token_delta": -13, "pass_rate_impact": "held", "confidence": 0.92}],
        "diff": [{"block_id": "safety.menu-ca-research-only", "removed": [], "added": ["No Menu.ca implementation changes unless explicitly requested"], "reason": "preserve safety"}],
    })
    (phase / "summary.md").write_text("# Summary\nEval 0 pass")
    (phase / "evidence-summary.md").write_text("# Evidence\nCandidate held pass-rate")
    write_json(live / "live-window.json", {"started_at_utc": "2026-06-07T15:55:00+00:00", "target_end_utc": "2099-01-01T00:00:00+00:00", "rollback_command": "rollback.sh"})
    (live / "override-log.jsonl").write_text(json.dumps({"event": "live_window_started"}) + "\n" + json.dumps({"event": "user_correction", "override": True, "safety_relevant": False}) + "\n")
    write_json(switch / "switch-log.json", {"switch_id": "switch-1", "rollback_command": "rollback.sh", "safety_verified": True})
    write_json(baseline / "token-counts.json", {"active_context_tokens_estimate": 209})

    monkeypatch.setenv("HERMES_CONTEXT_CONTROL_ROOT", str(pilot))
    from hermes_cli.context_control import build_context_control_state

    state = build_context_control_state()

    assert state["status"]["eval_0"] == "pass"
    assert state["status"]["live_overlay"] == "active"
    assert state["status"]["rollback"] == "hot"
    assert state["status"]["managed_scope"] == "8 blocks / 8 sources"
    assert state["metrics"]["tokens_saved"]["value"] == 13
    assert state["metrics"]["override_rate"]["value"] == "1/1"
    assert state["proposals"][0]["approve_enabled"] is True
    assert state["proposals"][0]["requires_per_block_approval"] is True
    assert state["projects"][0]["name"] == "Menu Finance"


def test_context_control_reject_records_reason_without_deleting(tmp_path, monkeypatch):
    pilot = tmp_path / "context-ci-pilot-001"
    monkeypatch.setenv("HERMES_CONTEXT_CONTROL_ROOT", str(pilot))
    from hermes_cli.context_control import record_rejection

    result = record_rejection("chief-os-pilot-001", "not enough evidence", rejected_by="Jordan")

    assert result["status"] == "recorded"
    log = pilot / ".hermes/context-control-plane/pilot-001/live-window/rejections.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0]["proposal_id"] == "chief-os-pilot-001"
    assert rows[0]["reason"] == "not enough evidence"
    assert rows[0]["deleted"] is False


def test_context_control_open_file_target_is_guarded_to_pilot_root(tmp_path, monkeypatch):
    pilot = tmp_path / "context-ci-pilot-001"
    source = pilot / "reports/pilot-001/phase-c/diff-packet.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}")
    monkeypatch.setenv("HERMES_CONTEXT_CONTROL_ROOT", str(pilot))
    from hermes_cli.context_control import resolve_open_file_target

    assert resolve_open_file_target("reports/pilot-001/phase-c/diff-packet.json") == source

    outside = tmp_path / "outside.txt"
    outside.write_text("nope")
    try:
        resolve_open_file_target(str(outside))
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("outside paths must be rejected")
