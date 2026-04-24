from __future__ import annotations

from pathlib import Path

from agent.role_runtime import load_org_chart_registry, resolve_role, role_system_prompt
from web.scripts.generate_org_chart_data import generate_typescript_module


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "web" / "src" / "data" / "hermesOrgChart.registry.yaml"


def _all_roles(registry: dict):
    lead = registry.get("lead_role")
    if isinstance(lead, dict):
        yield lead
    for section in registry.get("org_sections") or []:
        for role in section.get("roles") or []:
            if isinstance(role, dict):
                yield role


def test_org_chart_roles_declare_skill_policy():
    registry = load_org_chart_registry(REGISTRY_PATH)

    roles = list(_all_roles(registry))

    assert len(roles) == 12
    for role in roles:
        skills = role.get("skills")
        assert isinstance(skills, dict), f"{role.get('title')} missing skills policy"
        assert isinstance(skills.get("required"), list), f"{role.get('title')} missing required skills"
        assert skills.get("required"), f"{role.get('title')} should have at least one required skill"
        assert isinstance(skills.get("recommended", []), list), f"{role.get('title')} recommended skills must be a list"
        assert isinstance(skills.get("triggered", []), list), f"{role.get('title')} triggered skills must be a list"

    developer = resolve_role("Developer", registry=registry)
    assert "test-driven-development" in developer.payload["skills"]["required"]
    assert any(
        item.get("skill") == "change-graphql-contract"
        for item in developer.payload["skills"]["triggered"]
    )

    release_manager = resolve_role("Release Manager", registry=registry)
    triggered_release_skills = {
        item.get("skill") for item in release_manager.payload["skills"]["triggered"]
    }
    assert "run-beta-ota-release" in triggered_release_skills
    assert "run-production-native-release" in triggered_release_skills


def test_role_system_prompt_includes_skill_policy():
    role = resolve_role("Technical Validator", path=REGISTRY_PATH)

    prompt = role_system_prompt(role)

    assert "Skill policy:" in prompt
    assert "pre-commit-qc" in prompt
    assert "run-required-validation" in prompt
    assert "change-graphql-contract" in prompt


def test_generated_org_chart_types_include_role_skills():
    module = generate_typescript_module(REGISTRY_PATH)

    assert "export interface RoleSkillTrigger" in module
    assert "export interface RoleSkillPolicy" in module
    assert "skills: RoleSkillPolicy;" in module
    assert "test-driven-development" in module
    assert "run-production-native-release" in module
