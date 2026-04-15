"""Regression tests for skill path resolution in skill commands."""

import json
from pathlib import Path
from unittest.mock import patch

from agent.skill_commands import _load_skill_payload


def _skill_view_payload(*, name: str, path: str, content: str = "# Skill\n") -> str:
    return json.dumps(
        {
            "success": True,
            "name": name,
            "path": path,
            "content": content,
            "raw_content": content,
        }
    )


def test_load_skill_payload_builtin_keeps_skills_dir_parent(tmp_path):
    skills_dir = tmp_path / ".hermes" / "skills"
    builtin_dir = skills_dir / "team" / "myskill"
    builtin_dir.mkdir(parents=True)
    builtin_md = builtin_dir / "SKILL.md"

    with patch("tools.skills_tool.SKILLS_DIR", skills_dir), patch(
        "tools.skills_tool.skill_view",
        return_value=_skill_view_payload(name="myskill", path="team/myskill/SKILL.md"),
    ) as skill_view_mock:
        result = _load_skill_payload(str(builtin_md))

    assert result is not None
    loaded_skill, skill_dir, skill_name = result
    assert skill_view_mock.call_args.args[0] == "team/myskill/SKILL.md"
    assert loaded_skill["path"] == "team/myskill/SKILL.md"
    assert skill_name == "myskill"
    assert skill_dir == builtin_dir


def test_load_skill_payload_builtin_via_symlinked_skills_dir(tmp_path):
    real_skills_dir = tmp_path / "real-skills"
    real_builtin_dir = real_skills_dir / "team" / "myskill"
    real_builtin_dir.mkdir(parents=True)
    builtin_md = real_builtin_dir / "SKILL.md"
    symlinked_skills_dir = tmp_path / ".hermes" / "skills"
    symlinked_skills_dir.parent.mkdir(parents=True)
    symlinked_skills_dir.symlink_to(real_skills_dir, target_is_directory=True)

    with patch("tools.skills_tool.SKILLS_DIR", symlinked_skills_dir), patch(
        "tools.skills_tool.skill_view",
        return_value=_skill_view_payload(name="myskill", path="team/myskill/SKILL.md"),
    ):
        result = _load_skill_payload(str(builtin_md))

    assert result is not None
    _, skill_dir, _ = result
    assert skill_dir == symlinked_skills_dir / "team" / "myskill"


def test_load_skill_payload_external_absolute_path_uses_real_parent(tmp_path):
    skills_dir = tmp_path / ".hermes" / "skills"
    skills_dir.mkdir(parents=True)
    external_dir = Path("/tmp/external-skills/myteam/myskill")
    external_md = external_dir / "SKILL.md"

    with patch("tools.skills_tool.SKILLS_DIR", skills_dir), patch(
        "tools.skills_tool.skill_view",
        return_value=_skill_view_payload(name="myskill", path=str(external_md)),
    ) as skill_view_mock:
        result = _load_skill_payload(str(external_md))

    assert result is not None
    loaded_skill, skill_dir, skill_name = result
    assert skill_view_mock.call_args.args[0] == str(external_md)
    assert loaded_skill["path"] == str(external_md)
    assert skill_name == "myskill"
    assert skill_dir == external_dir.resolve()


def test_load_skill_payload_external_substring_not_inside_skills_dir(tmp_path):
    skills_dir = tmp_path / ".hermes" / "skills"
    skills_dir.mkdir(parents=True)
    external_dir = Path("/opt/hermes-skills/team/myskill")
    external_md = external_dir / "SKILL.md"

    with patch("tools.skills_tool.SKILLS_DIR", skills_dir), patch(
        "tools.skills_tool.skill_view",
        return_value=_skill_view_payload(name="myskill", path="team/myskill/SKILL.md"),
    ) as skill_view_mock:
        result = _load_skill_payload(str(external_md))

    assert result is not None
    loaded_skill, skill_dir, skill_name = result
    assert skill_view_mock.call_args.args[0] == str(external_md)
    assert loaded_skill["path"] == "team/myskill/SKILL.md"
    assert skill_name == "myskill"
    assert skill_dir == external_dir.resolve()
