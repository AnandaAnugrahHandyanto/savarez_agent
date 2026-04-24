from __future__ import annotations

import json
from pathlib import Path


REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "src"
    / "data"
    / "hermesOrgChart.registry.yaml"
)


def _finding(ledger: dict, finding_id: str) -> dict:
    return next(item for item in ledger["findings"] if item["finding_id"] == finding_id)


def test_validator_finding_requires_lead_review_before_developer_packet(tmp_path):
    from agent.plan_bundle import (
        completion_gate_status,
        ensure_plan_bundle,
        read_manifest,
        record_finding,
    )

    plan_id = "Lead Findings Loop"
    ensure_plan_bundle(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)

    ledger = record_finding(
        plan_id,
        finding_id="TV-001",
        raised_by_role="Technical Validator",
        title="Regression coverage missing",
        description="The implementation lacks a regression test for the validator path.",
        source_artifact="roles/technical-validator/outputs/review.md",
        workspace_root=tmp_path,
        registry_path=REGISTRY_PATH,
    )

    finding = _finding(ledger, "TV-001")
    assert finding["status"] == "open"
    assert finding["lead_review"]["disposition"] == "pending"
    assert finding["assigned_to_role"] is None
    assert finding["remediation_packet_path"] is None
    assert ledger["summary"]["open_count"] == 1
    assert ledger["summary"]["pending_lead_review_count"] == 1

    manifest = read_manifest(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert manifest["recovery"]["open_findings_count"] == 1

    gate = completion_gate_status(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert gate["can_complete"] is False
    assert any(blocker["type"] == "pending_lead_review" for blocker in gate["blockers"])


def test_accepted_finding_creates_developer_packet_and_blocks_until_revalidated_closed(tmp_path):
    from agent.plan_bundle import (
        close_finding,
        completion_gate_status,
        ensure_plan_bundle,
        lead_review_finding,
        mark_finding_pending_revalidation,
        record_finding,
    )

    plan_id = "Lead Findings Loop"
    paths = ensure_plan_bundle(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    workspace = tmp_path.resolve()

    record_finding(
        plan_id,
        finding_id="TV-001",
        raised_by_role="Technical Validator",
        title="Regression coverage missing",
        description="The implementation lacks a regression test for the validator path.",
        source_artifact="roles/technical-validator/outputs/review.md",
        workspace_root=workspace,
        registry_path=REGISTRY_PATH,
    )

    ledger = lead_review_finding(
        plan_id,
        finding_id="TV-001",
        disposition="accepted",
        lead_session_id="lead-session-1",
        assigned_to_role="Developer",
        remediation_instructions="Add the missing regression test and re-run the validator slice.",
        revalidation_roles_required=["Technical Validator"],
        workspace_root=workspace,
        registry_path=REGISTRY_PATH,
    )

    finding = _finding(ledger, "TV-001")
    assert finding["status"] == "in_fix"
    assert finding["lead_review"]["disposition"] == "accepted"
    assert finding["assigned_to_role"] == "Developer"
    assert finding["assigned_to_role_slug"] == "developer"
    assert finding["revalidation_roles_required"] == ["Technical Validator"]
    assert finding["remediation_packet_path"].endswith("roles/developer/packets/remediation-TV-001.md")
    assert ledger["summary"]["open_count"] == 1
    assert ledger["summary"]["send_back_count"] == 1

    packet_path = workspace / finding["remediation_packet_path"]
    assert packet_path.is_file()
    packet_text = packet_path.read_text(encoding="utf-8")
    assert "Lead-reviewed remediation packet" in packet_text
    assert "Technical Validator" in packet_text
    assert "Add the missing regression test" in packet_text

    assert completion_gate_status(plan_id, workspace_root=workspace, registry_path=REGISTRY_PATH)["can_complete"] is False

    ledger = mark_finding_pending_revalidation(
        plan_id,
        finding_id="TV-001",
        developer_session_id="developer-session-1",
        remediation_artifacts=["roles/developer/outputs/fix.md"],
        workspace_root=workspace,
        registry_path=REGISTRY_PATH,
    )
    finding = _finding(ledger, "TV-001")
    assert finding["status"] == "pending_revalidation"
    assert ledger["summary"]["pending_revalidation_count"] == 1
    assert completion_gate_status(plan_id, workspace_root=workspace, registry_path=REGISTRY_PATH)["can_complete"] is False

    ledger = close_finding(
        plan_id,
        finding_id="TV-001",
        closed_by_role="Technical Validator",
        closure_artifacts=["roles/technical-validator/outputs/revalidation.md"],
        workspace_root=workspace,
        registry_path=REGISTRY_PATH,
    )
    finding = _finding(ledger, "TV-001")
    assert finding["status"] == "closed"
    assert finding["closed_by_role"] == "Technical Validator"
    assert ledger["summary"]["open_count"] == 0
    assert ledger["summary"]["pending_revalidation_count"] == 0
    assert ledger["summary"]["closed_count"] == 1
    assert completion_gate_status(plan_id, workspace_root=workspace, registry_path=REGISTRY_PATH)["can_complete"] is True

    stored_ledger = json.loads(paths["findings_ledger"].read_text(encoding="utf-8"))
    assert _finding(stored_ledger, "TV-001")["status"] == "closed"


def test_completion_gate_requires_required_roles_or_explicit_waivers(tmp_path):
    from agent.plan_bundle import bundle_paths, completion_gate_status, ensure_plan_bundle

    plan_id = "Lead Findings Loop"
    paths = ensure_plan_bundle(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)

    paths["role_execution_plan"].write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": "lead-findings-loop",
                "roles": [
                    {"role_slug": "planner", "role": "Planner", "required": True},
                    {"role_slug": "technical-validator", "role": "Technical Validator", "required": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    paths["role_utilization_report"].write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": "lead-findings-loop",
                "roles": [
                    {"role_slug": "planner", "role": "Planner", "status": "completed"},
                ],
            }
        ),
        encoding="utf-8",
    )

    gate = completion_gate_status(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert gate["can_complete"] is False
    assert any(
        blocker["type"] == "required_role_missing" and blocker["role_slug"] == "technical-validator"
        for blocker in gate["blockers"]
    )

    paths = bundle_paths(plan_id, workspace_root=tmp_path)
    paths["role_execution_plan"].write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": "lead-findings-loop",
                "roles": [
                    {"role_slug": "planner", "role": "Planner", "required": True},
                    {
                        "role_slug": "technical-validator",
                        "role": "Technical Validator",
                        "required": True,
                        "waived": True,
                        "waiver_reason": "Docs-only slice; validator not required.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    gate = completion_gate_status(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert gate["can_complete"] is True
    assert gate["waived_required_roles"] == ["technical-validator"]
