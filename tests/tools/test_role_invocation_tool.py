"""Tests for the invoke_role tool."""

from __future__ import annotations

import json
from pathlib import Path

from model_tools import get_all_tool_names, get_toolset_for_tool
from tools.role_invocation_tool import INVOKE_ROLE_SCHEMA, check_invoke_role_requirements, invoke_role

REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "src"
    / "data"
    / "hermesOrgChart.registry.yaml"
)


def test_schema_and_registration():
    assert INVOKE_ROLE_SCHEMA["name"] == "invoke_role"
    assert "role" in INVOKE_ROLE_SCHEMA["parameters"]["required"]
    assert check_invoke_role_requirements() is True
    assert "invoke_role" in get_all_tool_names()
    assert get_toolset_for_tool("invoke_role") == "delegation"


def test_invoke_role_writes_bundle_and_reports_metadata(tmp_path):
    result = json.loads(
        invoke_role(
            role="Discovery / Content Inventory Specialist",
            plan_id="Role Team Runtime",
            summary="Create the next runtime slice",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
            packet_content="Task packet body",
            output_content="Role output body",
            evidence_content="Evidence body",
        )
    )

    assert result["success"] is True
    assert result["canonical_role"] == "Planner"
    assert result["execution_mode"] == "delegated_subagent"
    assert result["policy_default_execution_mode"] == "persistent_role_instance"
    assert result["role_session_id"].startswith("role-role-team-runtime-planner-")

    packet_path = Path(result["artifact_paths"]["packet"])
    output_path = Path(result["artifact_paths"]["output"])
    evidence_path = Path(result["artifact_paths"]["evidence"])
    assert packet_path.is_file()
    assert output_path.is_file()
    assert evidence_path.is_file()

    bundle_root = tmp_path / "_plans" / "role-team-runtime"
    manifest = json.loads((bundle_root / "01-manifest.json").read_text(encoding="utf-8"))
    assert manifest["plan_id"] == "role-team-runtime"
    assert manifest["role_sessions"]
    assert manifest["role_sessions"][0]["role"] == "Planner"
    assert manifest["role_sessions"][0]["execution_mode"] == "delegated_subagent"

    role_plan = json.loads((bundle_root / "02-role-execution-plan.json").read_text(encoding="utf-8"))
    assert role_plan["roles"]
    assert role_plan["roles"][0]["role_slug"] == "planner"
    assert role_plan["roles"][0]["planned_execution_mode"] == "delegated_subagent"

    utilization = json.loads((bundle_root / "04-role-utilization-report.json").read_text(encoding="utf-8"))
    assert utilization["roles"]
    assert utilization["roles"][0]["canonical_role"] == "Planner"
    assert utilization["roles"][0]["execution_mode"] == "delegated_subagent"


def test_invoke_role_records_parent_session_metadata(tmp_path):
    result = json.loads(
        invoke_role(
            role="Planner",
            plan_id="Role Team Runtime",
            summary="Record parent session metadata",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
            session_id="parent-session-1",
        )
    )

    assert result["success"] is True
    bundle_root = tmp_path / "_plans" / "role-team-runtime"
    manifest = json.loads((bundle_root / "01-manifest.json").read_text(encoding="utf-8"))
    assert manifest["lead"]["session_id"] == "parent-session-1"
    assert manifest["role_sessions"][0]["parent_session_id"] == "parent-session-1"


def test_invoke_role_ingests_structured_findings_from_role_output(tmp_path):
    output_content = """
Technical review found blockers.

```json
{
  "findings": [
    {
      "finding_id": "TV-001",
      "title": "Regression coverage missing",
      "description": "The implementation lacks a regression test for persistent role resume.",
      "severity": "high"
    }
  ]
}
```
""".strip()

    result = json.loads(
        invoke_role(
            role="Technical Validator",
            plan_id="Role Team Runtime",
            summary="Review persistent role runtime",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
            output_content=output_content,
        )
    )

    assert result["success"] is True
    assert result["findings_ingested"]["count"] == 1
    ledger = json.loads(
        (tmp_path / "_plans" / "role-team-runtime" / "03-findings-ledger.json").read_text(encoding="utf-8")
    )
    assert ledger["summary"]["open_count"] == 1
    assert ledger["summary"]["pending_lead_review_count"] == 1
    finding = ledger["findings"][0]
    assert finding["finding_id"] == "TV-001"
    assert finding["raised_by_role"] == "Technical Validator"
    assert finding["severity"] == "high"
    assert finding["source_artifact"] == result["artifact_paths"]["output_relative"]
    assert finding["lead_review"]["disposition"] == "pending"


def test_invoke_role_rejects_unsupported_mode(tmp_path):
    result = json.loads(
        invoke_role(
            role="Planner",
            plan_id="Role Team Runtime",
            summary="Try an unsupported mode",
            execution_mode="scheduled_role_run",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )
    )

    assert "error" in result
    assert "scheduled_role_run" in result["error"]
    assert "not yet implemented" in result["error"].lower()


def test_invoke_role_rejects_persistent_mode_without_session_db(tmp_path):
    result = json.loads(
        invoke_role(
            role="Planner",
            plan_id="Role Team Runtime",
            summary="Persistent mode must be backed by SessionDB",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )
    )

    assert "error" in result
    assert "requires a SessionDB-backed session_db" in result["error"]


def test_invoke_role_rejects_invalid_status(tmp_path):
    result = json.loads(
        invoke_role(
            role="Planner",
            plan_id="Role Team Runtime",
            summary="Reject invalid status",
            execution_mode="delegated_subagent",
            status="definitely-not-valid",
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )
    )

    assert "error" in result
    assert "Status 'definitely-not-valid' is not supported" in result["error"]
