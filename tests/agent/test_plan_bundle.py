from pathlib import Path

import pytest


REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "src"
    / "data"
    / "hermesOrgChart.registry.yaml"
)


def test_role_runtime_loads_role_policy_and_aliases():
    from agent.role_runtime import (
        DEFAULT_EXECUTION_MODE,
        EXECUTION_MODES,
        PLAN_PHASES,
        list_role_definitions,
        resolve_role,
    )

    assert DEFAULT_EXECUTION_MODE == "persistent_role_instance"
    assert "delegated_subagent" in EXECUTION_MODES
    assert "lead_review" in PLAN_PHASES

    definitions = list_role_definitions(path=REGISTRY_PATH)
    assert definitions

    lead = next(role for role in definitions if role.title == "Lead / PM")
    assert lead.policy.default_execution_mode == "persistent_role_instance"
    assert lead.policy.allowed_execution_modes == ("persistent_role_instance",)
    assert lead.policy.requires_independent_session is True

    planner = resolve_role("Discovery / Content Inventory Specialist", path=REGISTRY_PATH)
    assert planner.title == "Planner"
    assert planner.policy.requires_artifact_handoff is True
    assert planner.policy.worktree_strategy == "shared"


def test_plan_bundle_creates_artifacts_and_role_directories(tmp_path):
    from agent.plan_bundle import ensure_plan_bundle, read_manifest, role_paths

    plan_id = "Role Team Runtime"
    paths = ensure_plan_bundle(
        plan_id,
        workspace_root=tmp_path,
        title="Role Team Runtime",
        lead_session_id="sess_lead_123",
        registry_path=REGISTRY_PATH,
    )

    assert paths["bundle_root"] == tmp_path / "_plans" / "role-team-runtime"
    assert paths["plan"].is_file()
    assert paths["manifest"].is_file()
    assert paths["role_execution_plan"].is_file()
    assert paths["findings_ledger"].is_file()
    assert paths["role_utilization_report"].is_file()
    assert paths["summary"].is_file()

    manifest = read_manifest(plan_id, workspace_root=tmp_path)
    assert manifest["plan_id"] == "role-team-runtime"
    assert manifest["lead"]["session_id"] == "sess_lead_123"
    assert manifest["artifacts"]["role_utilization_report"].endswith("04-role-utilization-report.json")

    planner_paths = role_paths(plan_id, "planner", workspace_root=tmp_path)
    assert planner_paths["packets"].is_dir()
    assert planner_paths["outputs"].is_dir()
    assert planner_paths["evidence"].is_dir()

    steward_paths = role_paths(plan_id, "gitlab-artifact-steward", workspace_root=tmp_path)
    assert steward_paths["packets"].is_dir()


def test_generate_org_chart_data_writes_runtime_policy_types(tmp_path):
    from web.scripts.generate_org_chart_data import write_generated_module

    output_path = tmp_path / "hermesOrgChart.generated.ts"
    write_generated_module(REGISTRY_PATH, output_path)

    rendered = output_path.read_text(encoding="utf-8")
    assert "export interface RuntimePolicy" in rendered
    assert 'default_execution_mode: "persistent_role_instance"' in rendered
    assert "export const LEAD_ROLE: OrgRole =" in rendered
    assert "export const ORG_SECTIONS: OrgSection[] =" in rendered
    assert "export const DEFAULT_OPEN_SECTIONS" in rendered


def test_update_manifest_deep_merges_nested_objects(tmp_path):
    from agent.plan_bundle import ensure_plan_bundle, read_manifest, update_manifest

    plan_id = "Role Team Runtime"
    ensure_plan_bundle(plan_id, workspace_root=tmp_path, lead_session_id="sess_lead_123", registry_path=REGISTRY_PATH)

    updated = update_manifest(
        plan_id,
        {
            "lead": {"session_id": "sess_lead_999"},
            "user_approval": {"status": "approved"},
        },
        workspace_root=tmp_path,
        registry_path=REGISTRY_PATH,
    )

    assert updated["lead"]["role"] == "Lead / PM"
    assert updated["lead"]["session_id"] == "sess_lead_999"
    assert updated["lead"]["execution_mode"] == "persistent_role_instance"
    assert updated["user_approval"]["required"] is True
    assert updated["user_approval"]["status"] == "approved"

    manifest = read_manifest(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert manifest["lead"]["role_slug"] == "lead-pm"
    assert manifest["user_approval"]["status"] == "approved"


def test_write_role_artifacts_reject_path_traversal(tmp_path):
    from agent.plan_bundle import ensure_plan_bundle, write_role_output, write_role_packet

    ensure_plan_bundle("Role Team Runtime", workspace_root=tmp_path, registry_path=REGISTRY_PATH)

    with pytest.raises(ValueError):
        write_role_packet("Role Team Runtime", "planner", "../escape.md", "bad", workspace_root=tmp_path)

    with pytest.raises(ValueError):
        write_role_output("Role Team Runtime", "planner", "/tmp/escape.md", "bad", workspace_root=tmp_path)


def test_read_manifest_recovers_from_invalid_json(tmp_path):
    from agent.plan_bundle import bundle_paths, ensure_plan_bundle, read_manifest

    plan_id = "Role Team Runtime"
    ensure_plan_bundle(plan_id, workspace_root=tmp_path, lead_session_id="sess_lead_123", registry_path=REGISTRY_PATH)
    paths = bundle_paths(plan_id, workspace_root=tmp_path)
    paths["manifest"].write_text("{not-json", encoding="utf-8")

    manifest = read_manifest(plan_id, workspace_root=tmp_path, registry_path=REGISTRY_PATH)
    assert manifest["plan_id"] == "role-team-runtime"
    assert manifest["lead"]["role"] == "Lead / PM"
    assert manifest["artifacts"]["role_execution_plan"].endswith("02-role-execution-plan.json")


def test_generate_org_chart_data_quotes_non_identifier_alias_keys(tmp_path):
    from web.scripts.generate_org_chart_data import write_generated_module

    custom_registry = tmp_path / "custom.registry.yaml"
    custom_registry.write_text(
        REGISTRY_PATH.read_text(encoding="utf-8") + "\nrole_aliases:\n  'Lead / PM':\n    - Executive lead alias\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "hermesOrgChart.generated.ts"
    write_generated_module(custom_registry, output_path)

    rendered = output_path.read_text(encoding="utf-8")
    assert '"Lead / PM": [' in rendered


def test_update_manifest_rejects_invalid_nested_patch_types(tmp_path):
    from agent.plan_bundle import ensure_plan_bundle, update_manifest

    ensure_plan_bundle("Role Team Runtime", workspace_root=tmp_path, registry_path=REGISTRY_PATH)

    with pytest.raises(ValueError):
        update_manifest(
            "Role Team Runtime",
            {"lead": None},
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )

    with pytest.raises(ValueError):
        update_manifest(
            "Role Team Runtime",
            {"status": {"bad": "shape"}},
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )

    with pytest.raises(ValueError):
        update_manifest(
            "Role Team Runtime",
            {"lead": {"session_id": ["bad", "type"]}},
            workspace_root=tmp_path,
            registry_path=REGISTRY_PATH,
        )


def test_write_role_artifacts_require_known_role_slug(tmp_path):
    from agent.plan_bundle import ensure_plan_bundle, write_role_packet

    ensure_plan_bundle("Role Team Runtime", workspace_root=tmp_path, registry_path=REGISTRY_PATH)

    with pytest.raises(ValueError):
        write_role_packet(
            "Role Team Runtime",
            "not-a-real-role",
            "packet.md",
            "content",
            workspace_root=tmp_path,
        )
