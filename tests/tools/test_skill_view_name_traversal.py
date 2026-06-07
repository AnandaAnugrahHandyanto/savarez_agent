"""Tests for path traversal prevention via skill_view name parameter.

Regression tests for issue #38643: skill_view name parameter allowed
reading arbitrary files via path traversal (e.g., name="../.env").
"""

import json
import pytest
from unittest.mock import patch

from tools.skills_tool import skill_view


@pytest.fixture()
def fake_skills(tmp_path):
    """Create a fake skills directory with one skill and a sensitive file outside."""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "test-skill"
    skill_dir.mkdir(parents=True)

    # Create SKILL.md
    (skill_dir / "SKILL.md").write_text("# Test Skill\nA test skill.")

    # Create a sensitive file outside skills dir (simulating ~/.hermes/.env)
    (tmp_path / ".env").write_text("SECRET_API_KEY=leaked-secret")

    # Create a sensitive skill file outside skills dir
    (tmp_path / "outside-skill-file.md").write_text("# Outside Skill\nSensitive content here")

    with patch("tools.skills_tool.SKILLS_DIR", skills_dir):
        yield {"skills_dir": skills_dir, "skill_dir": skill_dir, "tmp_path": tmp_path}


class TestSkillNameTraversalBlocked:
    """Verify the skill name parameter cannot be exploited for path traversal."""

    def test_dotdot_in_skill_name_blocked(self, fake_skills):
        """A skill name with .. should be rejected."""
        result = json.loads(skill_view("../outside-skill-file"))
        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "relative" in result["error"].lower()

    def test_dotdot_nested_in_skill_name_blocked(self, fake_skills):
        """Nested .. in skill name should be rejected."""
        result = json.loads(skill_view("test-skill/../../outside-skill-file"))
        assert result["success"] is False
        assert "traversal" in result["error"].lower() or "relative" in result["error"].lower()

    def test_absolute_path_skill_name_blocked(self, fake_skills):
        """An absolute path as skill name should be rejected."""
        tmp_path = fake_skills["tmp_path"]
        absolute_path = str(tmp_path / "outside-skill-file.md")
        result = json.loads(skill_view(absolute_path))
        assert result["success"] is False
        assert "relative" in result["error"].lower()

    def test_legit_skill_name_still_works(self, fake_skills):
        """A normal skill name must still work after name validation."""
        result = json.loads(skill_view("test-skill"))
        assert result["success"] is True
        assert "Test Skill" in result.get("content", "")

    def test_categorized_skill_name_works(self, fake_skills):
        """Categorized names like category/skill-name should still work."""
        skills_dir = fake_skills["skills_dir"]
        # Create a categorized skill
        cat_dir = skills_dir / "category" / "categorized-skill"
        cat_dir.mkdir(parents=True)
        (cat_dir / "SKILL.md").write_text("# Categorized Skill")

        # This should work
        result = json.loads(skill_view("category/categorized-skill"))
        assert result["success"] is True
        assert "Categorized Skill" in result.get("content", "")

    def test_dotdot_with_file_path_blocked(self, fake_skills):
        """Even with legitimate skill name, .. in file_path should be blocked."""
        result = json.loads(skill_view("test-skill", file_path="../../.env"))
        assert result["success"] is False
        assert "traversal" in result["error"].lower()

    def test_sensitive_content_never_leaked(self, fake_skills):
        """Even if validation fails, sensitive content must not be leaked."""
        result = json.loads(skill_view("../.env"))
        result_str = json.dumps(result)
        assert "SECRET_API_KEY" not in result_str
        assert "leaked-secret" not in result_str
