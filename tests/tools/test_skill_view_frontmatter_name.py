"""Regression tests for skill_view resolving skills by frontmatter name.

Local skills may live in category directories whose leaf directory differs from
frontmatter ``name``. ``skills_list`` reports the declared name, so
``skill_view(<listed name>)`` must resolve that same skill instead of depending
on the filesystem directory name.
"""
from __future__ import annotations

import json
from pathlib import Path


def _write_skill(skills_dir: Path, rel: str, frontmatter_name: str, body: str = "Body.") -> Path:
    skill_dir = skills_dir / rel
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {frontmatter_name}\ndescription: test skill\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_md


def test_skill_view_resolves_listed_frontmatter_name_when_directory_differs(
    tmp_path: Path, monkeypatch
) -> None:
    """``skills_list`` name must be directly loadable via ``skill_view``."""
    from tools import skills_tool

    skills_dir = tmp_path / "skills"
    _write_skill(
        skills_dir,
        "spctrn/google-workspace",
        "spctrn-google-workspace",
        "Use gog for Google Workspace.",
    )
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(
        "agent.skill_utils.get_external_skills_dirs", lambda: []
    )
    monkeypatch.setattr(skills_tool, "_get_disabled_skill_names", lambda: set())

    listed = json.loads(skills_tool.skills_list(category="spctrn"))
    assert [skill["name"] for skill in listed["skills"]] == ["spctrn-google-workspace"]

    result = json.loads(skills_tool.skill_view("spctrn-google-workspace", preprocess=False))

    assert result["success"] is True
    assert result["name"] == "spctrn-google-workspace"
    assert result["path"] == "spctrn/google-workspace/SKILL.md"
    assert "Use gog for Google Workspace." in result["content"]
