"""Regression coverage for the bundled Hermes goal-forge sidecar skill."""

import json
from pathlib import Path

from tools import skills_tool
from tools.skill_manager_tool import _validate_frontmatter


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "autonomous-ai-agents" / "hermes-goal-forge-sidecar"
SKILL_MD = SKILL_DIR / "SKILL.md"
TEMPLATE = SKILL_DIR / "templates" / "goal-package.md"
SIDECAR_TEMPLATE = SKILL_DIR / "templates" / "sidecar-review-prompt.md"


def _skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def test_hermes_goal_forge_sidecar_skill_frontmatter_is_valid():
    content = _skill_text()

    assert _validate_frontmatter(content) is None
    assert "name: hermes-goal-forge-sidecar" in content
    assert "description:" in content
    assert "Use when adapting goal-forge" in content


def test_hermes_goal_forge_sidecar_skill_is_discoverable_with_templates(monkeypatch, tmp_path):
    local_skills = tmp_path / "skills"
    local_skills.mkdir()
    bundled_skills = REPO_ROOT / "skills"

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", local_skills)
    monkeypatch.setattr(
        "agent.skill_utils.get_external_skills_dirs",
        lambda: [bundled_skills],
    )

    listed = json.loads(skills_tool.skills_list("autonomous-ai-agents"))
    assert listed["success"] is True
    assert any(skill["name"] == "hermes-goal-forge-sidecar" for skill in listed["skills"])

    viewed = json.loads(skills_tool.skill_view("hermes-goal-forge-sidecar"))
    assert viewed["success"] is True
    assert viewed["path"].endswith("hermes-goal-forge-sidecar/SKILL.md")
    assert sorted(viewed["linked_files"]["templates"]) == [
        "templates/goal-package.md",
        "templates/sidecar-review-prompt.md",
    ]


def test_hermes_goal_forge_sidecar_documents_runtime_contracts():
    content = _skill_text()
    goal_template = TEMPLATE.read_text(encoding="utf-8")
    sidecar_template = SIDECAR_TEMPLATE.read_text(encoding="utf-8")

    required_skill_phrases = [
        "Hermes-native adaptation of goal-forge",
        "main runner",
        "sidecar reviewer",
        "delegate_task",
        "GOAL.md",
        "PLAN.md",
        "ATTEMPTS.md",
        "NOTES.md",
        "CONTROL.md",
        "scorecard",
        "fast feedback loop",
        "sidecar_apply_cadence",
        "Latest Human Nudge",
        "Do not let the sidecar modify the repository",
        "Sidecar findings are advice, not success evidence",
        "tests_run",
        "accepted_commits",
    ]
    for phrase in required_skill_phrases:
        assert phrase in content

    for phrase in [
        "<goal>",
        "<scorecard>",
        "<feedback_loop>",
        "<working_memory>",
        "<human_control_surface>",
        "<verification_loop>",
        "CONTROL.md",
    ]:
        assert phrase in goal_template

    for phrase in [
        "read-only sidecar reviewer",
        "Do not edit files",
        "logs, diffs, test output, artifacts",
        "continue | pause | redirect | reject",
        "concise steering directive",
    ]:
        assert phrase in sidecar_template
