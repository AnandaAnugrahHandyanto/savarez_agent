import json
from unittest.mock import patch

import tools.skills_tool as skills_tool


def _make_bmad_project(tmp_path):
    project = tmp_path / "app"
    skill_dir = project / "_bmad" / "core" / "bmad-help"
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: bmad-help
description: Help choose workflows.
---

# Help
""",
        encoding="utf-8",
    )
    (ref_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    return project


def test_skills_list_includes_active_bmad_project_skill_even_without_local_skills(tmp_path, monkeypatch):
    project = _make_bmad_project(tmp_path)
    empty_hermes_skills = tmp_path / "empty-hermes-skills"
    monkeypatch.chdir(project)

    with patch.object(skills_tool, "SKILLS_DIR", empty_hermes_skills):
        result = json.loads(skills_tool.skills_list())

    names = [skill["name"] for skill in result["skills"]]
    assert "bmad:bmad-help" in names


def test_skill_view_reads_bmad_project_skill_resource(tmp_path, monkeypatch):
    project = _make_bmad_project(tmp_path)
    monkeypatch.chdir(project)

    skill_result = json.loads(skills_tool.skill_view("bmad:bmad-help"))
    ref_result = json.loads(skills_tool.skill_view("bmad:bmad-help", "references/guide.md"))

    assert skill_result["success"] is True
    assert skill_result["name"] == "bmad:bmad-help"
    assert "Help choose workflows" in skill_result["content"]
    assert ref_result["success"] is True
    assert "# Guide" in ref_result["content"]


def test_skill_view_bmad_main_content_includes_project_scope_banner(tmp_path, monkeypatch):
    project = _make_bmad_project(tmp_path)
    monkeypatch.chdir(project)

    result = json.loads(skills_tool.skill_view("bmad:bmad-help"))

    assert result["success"] is True
    assert "project-provided BMAD skill" in result["content"]
    assert "task only" in result["content"]
