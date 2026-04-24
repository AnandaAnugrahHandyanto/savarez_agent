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
    assert "writing-plans" in utilization["roles"][0]["required_skills"]
    assert utilization["roles"][0]["skill_compliance"] == "verified"
    assert utilization["roles"][0]["skill_policy_source"] == "hermesOrgChart.registry.yaml"
    assert "writing-plans" in utilization["roles"][0]["loaded_required_skills"]
    assert not utilization["roles"][0]["missing_required_skills"]
    packet_text = packet_path.read_text(encoding="utf-8")
    assert "## Skill policy" in packet_text
    assert "Skill compliance: `verified`" in packet_text
    assert "writing-plans" in packet_text
    assert result["skill_policy"]["required"] == utilization["roles"][0]["required_skills"]
    assert result["skill_compliance"] == "verified"
    assert "writing-plans" in result["loaded_required_skills"]
    assert not result["missing_required_skills"]


def test_invoke_role_loads_required_skill_from_workspace_legacy_codex_skill(tmp_path):
    skill_dir = tmp_path / "_docs" / "codex-skills" / "workspace-only-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: workspace-only-skill\ndescription: Workspace-only skill for tests.\n---\n\n"
        "# Workspace Only Skill\n\nFollow the workspace-specific procedure.\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - workspace-only-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Workspace Skills",
            summary="Load workspace skill content",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "verified"
    assert result["loaded_required_skills"] == ["workspace-only-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "## Loaded required skill content" in packet_text
    assert "Follow the workspace-specific procedure." in packet_text
    utilization = json.loads(
        (tmp_path / "_plans" / "workspace-skills" / "04-role-utilization-report.json").read_text(encoding="utf-8")
    )
    assert utilization["roles"][0]["skill_compliance"] == "verified"
    assert utilization["roles"][0]["loaded_required_skills"] == ["workspace-only-skill"]


def test_invoke_role_loads_required_skill_from_workspace_external_agents_skill(tmp_path):
    skill_dir = tmp_path / ".agents" / "skills" / "external-only-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: external-only-skill\ndescription: External workspace skill for tests.\n---\n\n"
        "# External Only Skill\n\nFollow the external workspace procedure.\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - external-only-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="External Workspace Skills",
            summary="Load external workspace skill content",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "verified"
    assert result["loaded_required_skills"] == ["external-only-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "Follow the external workspace procedure." in packet_text


def test_invoke_role_does_not_load_required_skill_from_parent_workspace(tmp_path):
    parent_skill_dir = tmp_path / "_docs" / "codex-skills" / "parent-only-skill"
    parent_skill_dir.mkdir(parents=True)
    (parent_skill_dir / "SKILL.md").write_text(
        "---\nname: parent-only-skill\n---\n\nPARENT SCOPE CONTENT MUST NOT LOAD.\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry_path = workspace / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - parent-only-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Parent Workspace Skills",
            summary="Do not load parent workspace skill content",
            execution_mode="delegated_subagent",
            workspace_root=workspace,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "partial"
    assert result["missing_required_skills"] == ["parent-only-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "PARENT SCOPE CONTENT MUST NOT LOAD" not in packet_text


def test_invoke_role_does_not_load_workspace_skill_through_symlinked_skill_root(tmp_path):
    external_root = tmp_path / "external-skill-root"
    external_skill_dir = external_root / "symlinked-skill"
    external_skill_dir.mkdir(parents=True)
    (external_skill_dir / "SKILL.md").write_text(
        "---\nname: symlinked-skill\n---\n\nSYMLINKED EXTERNAL CONTENT MUST NOT LOAD.\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    docs_root = workspace / "_docs"
    docs_root.mkdir(parents=True)
    (docs_root / "codex-skills").symlink_to(external_root, target_is_directory=True)
    registry_path = workspace / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - symlinked-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Symlinked Workspace Skills",
            summary="Do not load symlinked external skill content",
            execution_mode="delegated_subagent",
            workspace_root=workspace,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "partial"
    assert result["missing_required_skills"] == ["symlinked-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "SYMLINKED EXTERNAL CONTENT MUST NOT LOAD" not in packet_text


def test_invoke_role_reports_partial_when_required_skill_content_exceeds_aggregate_cap(tmp_path):
    docs_root = tmp_path / "_docs" / "codex-skills"
    first = docs_root / "first-large-skill"
    second = docs_root / "second-large-skill"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    large_body = "x" * 60_000
    (first / "SKILL.md").write_text("---\nname: first-large-skill\n---\n\n" + large_body, encoding="utf-8")
    (second / "SKILL.md").write_text("---\nname: second-large-skill\n---\n\n" + large_body, encoding="utf-8")
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - first-large-skill
      - second-large-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Aggregate Skill Cap",
            summary="Respect aggregate skill packet cap",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "partial"
    assert result["loaded_required_skills"] == ["first-large-skill"]
    assert result["missing_required_skills"] == ["second-large-skill"]


def test_invoke_role_declares_but_does_not_load_recommended_or_triggered_skill_content(tmp_path):
    docs_root = tmp_path / "_docs" / "codex-skills"
    required = docs_root / "required-skill"
    recommended = docs_root / "recommended-skill"
    triggered = docs_root / "triggered-skill"
    required.mkdir(parents=True)
    recommended.mkdir(parents=True)
    triggered.mkdir(parents=True)
    (required / "SKILL.md").write_text("---\nname: required-skill\n---\n\nREQUIRED CONTENT SHOULD LOAD.\n", encoding="utf-8")
    (recommended / "SKILL.md").write_text("---\nname: recommended-skill\n---\n\nRECOMMENDED CONTENT MUST NOT LOAD.\n", encoding="utf-8")
    (triggered / "SKILL.md").write_text("---\nname: triggered-skill\n---\n\nTRIGGERED CONTENT MUST NOT LOAD.\n", encoding="utf-8")
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - required-skill
    recommended:
      - recommended-skill
    triggered:
      - skill: triggered-skill
        when: test trigger condition
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Recommended Triggered Not Loaded",
            summary="Only required content loads",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "verified"
    assert result["loaded_required_skills"] == ["required-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "REQUIRED CONTENT SHOULD LOAD." in packet_text
    assert "recommended-skill" in packet_text
    assert "triggered-skill" in packet_text
    assert "RECOMMENDED CONTENT MUST NOT LOAD." not in packet_text
    assert "TRIGGERED CONTENT MUST NOT LOAD." not in packet_text


def test_invoke_role_appends_loaded_skill_content_when_custom_packet_has_same_heading(tmp_path):
    skill_dir = tmp_path / "_docs" / "codex-skills" / "custom-packet-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: custom-packet-skill\n---\n\nCUSTOM PACKET SKILL CONTENT.\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - custom-packet-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Custom Packet Skill Heading",
            summary="Load even when custom packet contains heading",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
            packet_content="Task packet\n\n## Loaded required skill content\n\nCaller-provided placeholder.",
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "verified"
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "Caller-provided placeholder." in packet_text
    assert "CUSTOM PACKET SKILL CONTENT." in packet_text


def test_invoke_role_rejects_unsafe_or_oversized_workspace_skill_content(tmp_path):
    outside = tmp_path / "outside-skill" / "SKILL.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("# Outside\n\nShould not be loaded.\n", encoding="utf-8")
    oversized_dir = tmp_path / "_docs" / "codex-skills" / "oversized-skill"
    oversized_dir.mkdir(parents=True)
    (oversized_dir / "SKILL.md").write_text("x" * 100_001, encoding="utf-8")
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - ../outside-skill
      - oversized-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Unsafe Skills",
            summary="Do not load unsafe skill content",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "partial"
    assert result["missing_required_skills"] == ["../outside-skill", "oversized-skill"]
    packet_text = Path(result["artifact_paths"]["packet"]).read_text(encoding="utf-8")
    assert "Should not be loaded" not in packet_text
    assert "x" * 1000 not in packet_text


def test_invoke_role_reports_partial_skill_compliance_when_required_skill_missing(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
lead_role:
  title: Lead / PM
  position: Lead
  mission: Lead mission
  responsibilities:
    - Lead work
  activation: Always
  reportsTo: User
  model: Latest GPT (auto)
  toolFocus: []
  invokeFor: []
  runtimePolicy:
    default_execution_mode: delegated_subagent
    allowed_execution_modes:
      - delegated_subagent
  skills:
    required:
      - definitely-missing-role-skill
    recommended: []
    triggered: []
role_aliases: {}
org_sections: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = json.loads(
        invoke_role(
            role="Lead / PM",
            plan_id="Missing Skills",
            summary="Report missing required skill",
            execution_mode="delegated_subagent",
            workspace_root=tmp_path,
            registry_path=registry_path,
        )
    )

    assert result["success"] is True
    assert result["skill_compliance"] == "partial"
    assert result["missing_required_skills"] == ["definitely-missing-role-skill"]
    utilization = json.loads(
        (tmp_path / "_plans" / "missing-skills" / "04-role-utilization-report.json").read_text(encoding="utf-8")
    )
    assert utilization["roles"][0]["skill_compliance"] == "partial"
    assert utilization["roles"][0]["missing_required_skills"] == ["definitely-missing-role-skill"]


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
