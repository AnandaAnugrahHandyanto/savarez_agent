"""Tests for tools/skill_manager_tool.py — skill creation, editing, and deletion."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tools.skill_manager_tool import (
    _validate_name,
    _validate_category,
    _validate_frontmatter,
    _validate_file_path,
    _validate_skill_quality,
    _extract_referenced_files,
    _find_skill,
    _resolve_skill_dir,
    _create_skill,
    _edit_skill,
    _patch_skill,
    _delete_skill,
    _write_file,
    _remove_file,
    skill_manage,
    VALID_NAME_RE,
    ALLOWED_SUBDIRS,
    MAX_NAME_LENGTH,
)


@contextmanager
def _skill_dir(tmp_path):
    """Patch both SKILLS_DIR and get_all_skills_dirs so _find_skill searches
    only the temp directory — not the real ~/.hermes/skills/."""
    with patch("tools.skill_manager_tool.SKILLS_DIR", tmp_path), \
         patch("agent.skill_utils.get_all_skills_dirs", return_value=[tmp_path]):
        yield


VALID_SKILL_CONTENT = """\
---
name: test-skill
description: A test skill for unit testing.
---

# Test Skill

Step 1: Do the thing.
"""

VALID_SKILL_CONTENT_2 = """\
---
name: test-skill
description: Updated description.
---

# Test Skill v2

Step 1: Do the new thing.
"""


# ---------------------------------------------------------------------------
# _validate_name
# ---------------------------------------------------------------------------


class TestValidateName:
    def test_valid_names(self):
        assert _validate_name("my-skill") is None
        assert _validate_name("skill123") is None
        assert _validate_name("my_skill.v2") is None
        assert _validate_name("a") is None

    def test_empty_name(self):
        assert _validate_name("") == "Skill name is required."

    def test_too_long(self):
        err = _validate_name("a" * (MAX_NAME_LENGTH + 1))
        assert err == f"Skill name exceeds {MAX_NAME_LENGTH} characters."

    def test_uppercase_rejected(self):
        err = _validate_name("MySkill")
        assert "Invalid skill name 'MySkill'" in err

    def test_starts_with_hyphen_rejected(self):
        err = _validate_name("-invalid")
        assert "Invalid skill name '-invalid'" in err

    def test_special_chars_rejected(self):
        err = _validate_name("skill/name")
        assert "Invalid skill name 'skill/name'" in err
        err = _validate_name("skill name")
        assert "Invalid skill name 'skill name'" in err
        err = _validate_name("skill@name")
        assert "Invalid skill name 'skill@name'" in err


class TestValidateCategory:
    def test_valid_categories(self):
        assert _validate_category(None) is None
        assert _validate_category("") is None
        assert _validate_category("devops") is None
        assert _validate_category("mlops-v2") is None

    def test_path_traversal_rejected(self):
        err = _validate_category("../escape")
        assert "Invalid category '../escape'" in err

    def test_absolute_path_rejected(self):
        err = _validate_category("/tmp/escape")
        assert "Invalid category '/tmp/escape'" in err


# ---------------------------------------------------------------------------
# _validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_content(self):
        assert _validate_frontmatter(VALID_SKILL_CONTENT) is None

    def test_empty_content(self):
        assert _validate_frontmatter("") == "Content cannot be empty."
        assert _validate_frontmatter("   ") == "Content cannot be empty."

    def test_no_frontmatter(self):
        err = _validate_frontmatter("# Just a heading\nSome content.\n")
        assert err == "SKILL.md must start with YAML frontmatter (---). See existing skills for format."

    def test_unclosed_frontmatter(self):
        content = "---\nname: test\ndescription: desc\nBody content.\n"
        assert _validate_frontmatter(content) == "SKILL.md frontmatter is not closed. Ensure you have a closing '---' line."

    def test_missing_name_field(self):
        content = "---\ndescription: desc\n---\n\nBody.\n"
        assert _validate_frontmatter(content) == "Frontmatter must include 'name' field."

    def test_missing_description_field(self):
        content = "---\nname: test\n---\n\nBody.\n"
        assert _validate_frontmatter(content) == "Frontmatter must include 'description' field."

    def test_no_body_after_frontmatter(self):
        content = "---\nname: test\ndescription: desc\n---\n"
        assert _validate_frontmatter(content) == "SKILL.md must have content after the frontmatter (instructions, procedures, etc.)."

    def test_invalid_yaml(self):
        content = "---\n: invalid: yaml: {{{\n---\n\nBody.\n"
        assert "YAML frontmatter parse error" in _validate_frontmatter(content)


# ---------------------------------------------------------------------------
# _validate_file_path — path traversal prevention
# ---------------------------------------------------------------------------


class TestValidateFilePath:
    def test_valid_paths(self):
        assert _validate_file_path("references/api.md") is None
        assert _validate_file_path("templates/config.yaml") is None
        assert _validate_file_path("scripts/train.py") is None
        assert _validate_file_path("assets/image.png") is None

    def test_empty_path(self):
        assert _validate_file_path("") == "file_path is required."

    def test_path_traversal_blocked(self):
        err = _validate_file_path("references/../../../etc/passwd")
        assert err == "Path traversal ('..') is not allowed."

    def test_disallowed_subdirectory(self):
        err = _validate_file_path("secret/hidden.txt")
        assert "File must be under one of:" in err
        assert "'secret/hidden.txt'" in err

    def test_directory_only_rejected(self):
        err = _validate_file_path("references")
        assert "Provide a file path, not just a directory" in err
        assert "'references/myfile.md'" in err

    def test_root_level_file_rejected(self):
        err = _validate_file_path("malicious.py")
        assert "File must be under one of:" in err
        assert "'malicious.py'" in err


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


class TestCreateSkill:
    def test_create_skill(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", VALID_SKILL_CONTENT)
        assert result["success"] is True
        assert (tmp_path / "my-skill" / "SKILL.md").exists()

    def test_create_with_category(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", VALID_SKILL_CONTENT, category="devops")
        assert result["success"] is True
        assert (tmp_path / "devops" / "my-skill" / "SKILL.md").exists()
        assert result["category"] == "devops"

    def test_create_duplicate_blocked(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _create_skill("my-skill", VALID_SKILL_CONTENT)
        assert result["success"] is False
        assert "already exists" in result["error"]

    def test_create_invalid_name(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _create_skill("Invalid Name!", VALID_SKILL_CONTENT)
        assert result["success"] is False

    def test_create_invalid_content(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", "no frontmatter here")
        assert result["success"] is False

    def test_create_rejects_category_traversal(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        with patch("tools.skill_manager_tool.SKILLS_DIR", skills_dir), \
             patch("agent.skill_utils.get_all_skills_dirs", return_value=[skills_dir]):
            result = _create_skill("my-skill", VALID_SKILL_CONTENT, category="../escape")

        assert result["success"] is False
        assert "Invalid category '../escape'" in result["error"]
        assert not (tmp_path / "escape").exists()

    def test_create_rejects_absolute_category(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        outside = tmp_path / "outside"

        with patch("tools.skill_manager_tool.SKILLS_DIR", skills_dir), \
             patch("agent.skill_utils.get_all_skills_dirs", return_value=[skills_dir]):
            result = _create_skill("my-skill", VALID_SKILL_CONTENT, category=str(outside))

        assert result["success"] is False
        assert f"Invalid category '{outside}'" in result["error"]
        assert not (outside / "my-skill" / "SKILL.md").exists()


class TestEditSkill:
    def test_edit_existing_skill(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _edit_skill("my-skill", VALID_SKILL_CONTENT_2)
        assert result["success"] is True
        content = (tmp_path / "my-skill" / "SKILL.md").read_text()
        assert "Updated description" in content

    def test_edit_nonexistent_skill(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _edit_skill("nonexistent", VALID_SKILL_CONTENT)
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_edit_invalid_content_rejected(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _edit_skill("my-skill", "no frontmatter")
        assert result["success"] is False
        # Original content should be preserved
        content = (tmp_path / "my-skill" / "SKILL.md").read_text()
        assert "A test skill" in content


class TestPatchSkill:
    def test_patch_unique_match(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _patch_skill("my-skill", "Do the thing.", "Do the new thing.")
        assert result["success"] is True
        content = (tmp_path / "my-skill" / "SKILL.md").read_text()
        assert "Do the new thing." in content

    def test_patch_nonexistent_string(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _patch_skill("my-skill", "this text does not exist", "replacement")
        assert result["success"] is False
        assert "not found" in result["error"].lower() or "could not find" in result["error"].lower()

    def test_patch_ambiguous_match_rejected(self, tmp_path):
        content = """\
---
name: test-skill
description: A test skill.
---

# Test

word word
"""
        with _skill_dir(tmp_path):
            _create_skill("my-skill", content)
            result = _patch_skill("my-skill", "word", "replaced")
        assert result["success"] is False
        assert "match" in result["error"].lower()

    def test_patch_replace_all(self, tmp_path):
        content = """\
---
name: test-skill
description: A test skill.
---

# Test

word word
"""
        with _skill_dir(tmp_path):
            _create_skill("my-skill", content)
            result = _patch_skill("my-skill", "word", "replaced", replace_all=True)
        assert result["success"] is True

    def test_patch_supporting_file(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            _write_file("my-skill", "references/api.md", "old text here")
            result = _patch_skill("my-skill", "old text", "new text", file_path="references/api.md")
        assert result["success"] is True

    def test_patch_skill_not_found(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _patch_skill("nonexistent", "old", "new")
        assert result["success"] is False


class TestDeleteSkill:
    def test_delete_existing(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _delete_skill("my-skill")
        assert result["success"] is True
        assert not (tmp_path / "my-skill").exists()

    def test_delete_nonexistent(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _delete_skill("nonexistent")
        assert result["success"] is False

    def test_delete_cleans_empty_category_dir(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT, category="devops")
            _delete_skill("my-skill")
        assert not (tmp_path / "devops").exists()


# ---------------------------------------------------------------------------
# write_file / remove_file
# ---------------------------------------------------------------------------


class TestWriteFile:
    def test_write_reference_file(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _write_file("my-skill", "references/api.md", "# API\nEndpoint docs.")
        assert result["success"] is True
        assert (tmp_path / "my-skill" / "references" / "api.md").exists()

    def test_write_to_nonexistent_skill(self, tmp_path):
        with _skill_dir(tmp_path):
            result = _write_file("nonexistent", "references/doc.md", "content")
        assert result["success"] is False

    def test_write_to_disallowed_path(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _write_file("my-skill", "secret/evil.py", "malicious")
        assert result["success"] is False


class TestRemoveFile:
    def test_remove_existing_file(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            _write_file("my-skill", "references/api.md", "content")
            result = _remove_file("my-skill", "references/api.md")
        assert result["success"] is True
        assert not (tmp_path / "my-skill" / "references" / "api.md").exists()

    def test_remove_nonexistent_file(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _remove_file("my-skill", "references/nope.md")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# skill_manage dispatcher
# ---------------------------------------------------------------------------


class TestSkillManageDispatcher:
    def test_unknown_action(self, tmp_path):
        with _skill_dir(tmp_path):
            raw = skill_manage(action="explode", name="test")
        result = json.loads(raw)
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_create_without_content(self, tmp_path):
        with _skill_dir(tmp_path):
            raw = skill_manage(action="create", name="test")
        result = json.loads(raw)
        assert result["success"] is False
        assert "content" in result["error"].lower()

    def test_patch_without_old_string(self, tmp_path):
        with _skill_dir(tmp_path):
            raw = skill_manage(action="patch", name="test")
        result = json.loads(raw)
        assert result["success"] is False

    def test_full_create_via_dispatcher(self, tmp_path):
        with _skill_dir(tmp_path):
            raw = skill_manage(action="create", name="test-skill", content=VALID_SKILL_CONTENT)
        result = json.loads(raw)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Quality validation (issue #416)
# ---------------------------------------------------------------------------


class TestExtractReferencedFiles:
    """Regex-level tests for the file-reference extractor."""

    def test_empty_content(self):
        assert _extract_referenced_files("") == []
        assert _extract_referenced_files(None) == []

    def test_finds_bare_reference(self):
        content = "See references/api.md for details."
        assert _extract_referenced_files(content) == ["references/api.md"]

    def test_finds_all_four_subdirs(self):
        content = (
            "Use references/api.md, templates/config.yaml, "
            "scripts/setup.sh, and assets/diagram.png."
        )
        refs = _extract_referenced_files(content)
        assert "references/api.md" in refs
        assert "templates/config.yaml" in refs
        assert "scripts/setup.sh" in refs
        assert "assets/diagram.png" in refs

    def test_markdown_link(self):
        content = "See the [API guide](references/api.md) here."
        assert _extract_referenced_files(content) == ["references/api.md"]

    def test_code_span(self):
        content = "Run `scripts/validate.py` to check."
        assert _extract_referenced_files(content) == ["scripts/validate.py"]

    def test_fenced_code_block(self):
        content = "```\npython scripts/run.py\n```"
        assert _extract_referenced_files(content) == ["scripts/run.py"]

    def test_ignores_partial_match_inside_identifier(self):
        # "my_references/foo" should not match "references/foo"
        content = "The variable my_references/foo.md is unused."
        assert _extract_referenced_files(content) == []

    def test_ignores_path_prefix_match(self):
        # "a/references/foo.md" should not match "references/foo.md"
        # because the preceding slash fails the lookbehind.
        content = "Path is /home/references/foo.md"
        assert _extract_referenced_files(content) == []

    def test_requires_extension(self):
        # Bare directory mentions should not match.
        content = "Put stuff in references/ and templates/."
        assert _extract_referenced_files(content) == []

    def test_skips_glob_patterns(self):
        content = "Run scripts/*.py to test."
        assert _extract_referenced_files(content) == []

    def test_strips_trailing_punctuation(self):
        content = "See references/api.md, templates/config.yaml."
        refs = _extract_referenced_files(content)
        assert "references/api.md" in refs
        assert "templates/config.yaml" in refs

    def test_deduplicates(self):
        content = (
            "First mention: references/api.md\n"
            "Second mention: references/api.md"
        )
        assert _extract_referenced_files(content) == ["references/api.md"]


class TestValidateSkillQuality:
    """Tests for the non-blocking quality validator."""

    def _make_skill(self, tmp_path, name="my-skill", body="Step 1: Do it."):
        """Create a minimal valid skill dir at tmp_path / name."""
        skill_dir = tmp_path / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = f"---\nname: {name}\ndescription: Test skill.\n---\n\n# {name}\n\n{body}\n"
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return skill_dir, content

    def test_clean_skill_no_warnings(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        assert _validate_skill_quality(skill_dir, content=content, expected_name="my-skill") == []

    def test_missing_skill_dir_returns_empty(self, tmp_path):
        # Non-existent directory should not crash — just return []
        assert _validate_skill_quality(tmp_path / "does-not-exist") == []

    def test_detects_python_syntax_error(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        bad_py = scripts_dir / "broken.py"
        bad_py.write_text("def broken(:\n    pass\n", encoding="utf-8")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert any("Python syntax error" in w for w in warnings)
        assert any("broken.py" in w for w in warnings)

    def test_valid_python_no_warning(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "ok.py").write_text(
            "def ok():\n    return 42\n", encoding="utf-8"
        )
        warnings = _validate_skill_quality(skill_dir, content=content)
        assert not any("syntax error" in w for w in warnings)

    def test_skips_hidden_and_pycache_dirs(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        # Create a broken .py inside a __pycache__ dir — should be skipped
        pycache = skill_dir / "scripts" / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "garbage.py").write_text("this is (not python", encoding="utf-8")
        # And one inside a hidden .venv — also skipped
        hidden = skill_dir / ".venv"
        hidden.mkdir()
        (hidden / "also-garbage.py").write_text("also not python (", encoding="utf-8")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert not any("syntax error" in w for w in warnings)

    def test_detects_broken_symlink(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        broken = skill_dir / "assets" / "missing.png"
        broken.parent.mkdir()
        broken.symlink_to(tmp_path / "nonexistent-target.png")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert any("Broken symlink" in w for w in warnings)
        assert any("missing.png" in w for w in warnings)

    def test_valid_symlink_no_warning(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path)
        # Create a real target inside the skill dir, then symlink to it
        target = skill_dir / "assets" / "real.png"
        target.parent.mkdir()
        target.write_bytes(b"fake png data")
        link = skill_dir / "assets" / "link.png"
        link.symlink_to(target)

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert not any("Broken symlink" in w for w in warnings)

    def test_detects_missing_single_reference(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "See references/api.md for details.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert any(
            "Referenced file missing: references/api.md" in w for w in warnings
        )

    def test_detects_multiple_missing_references(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "See references/api.md and templates/config.yaml.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        warnings = _validate_skill_quality(skill_dir, content=content)
        # Combined multi-ref message
        combined = [w for w in warnings if "Referenced files missing (2)" in w]
        assert combined
        assert "references/api.md" in combined[0]
        assert "templates/config.yaml" in combined[0]

    def test_existing_reference_no_warning(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "api.md").write_text("# API", encoding="utf-8")
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "See references/api.md for details.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert not any("Referenced file missing" in w for w in warnings)
        assert not any("Referenced files missing" in w for w in warnings)

    def test_name_mismatch_warning(self, tmp_path):
        skill_dir = tmp_path / "wrong-dir"
        skill_dir.mkdir()
        content = (
            "---\nname: actual-name\ndescription: Test.\n---\n\nBody.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        warnings = _validate_skill_quality(
            skill_dir, content=content, expected_name="wrong-dir"
        )
        assert any(
            "Frontmatter name 'actual-name' does not match" in w for w in warnings
        )

    def test_name_match_no_warning(self, tmp_path):
        skill_dir, content = self._make_skill(tmp_path, name="my-skill")
        warnings = _validate_skill_quality(
            skill_dir, content=content, expected_name="my-skill"
        )
        assert not any("does not match" in w for w in warnings)

    def test_multiple_issues_accumulated(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "See references/api.md.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        # Add a broken .py
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "broken.py").write_text("def (:\n", encoding="utf-8")
        # Add a broken symlink
        link = skill_dir / "assets" / "missing.png"
        link.parent.mkdir()
        link.symlink_to(tmp_path / "nope.png")

        warnings = _validate_skill_quality(skill_dir, content=content)
        assert len(warnings) >= 3
        assert any("Broken symlink" in w for w in warnings)
        assert any("syntax error" in w for w in warnings)
        assert any("Referenced file missing" in w for w in warnings)

    def test_reads_skill_md_when_content_omitted(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "See references/api.md.\n"
        )
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        # No content argument — should read from disk
        warnings = _validate_skill_quality(skill_dir)
        assert any("Referenced file missing" in w for w in warnings)


class TestQualityWarningsIntegration:
    """Tests that warnings flow into skill_manage results without blocking."""

    def test_create_clean_skill_no_warnings_key(self, tmp_path):
        # Use content whose frontmatter name matches the skill name
        # so the name-mismatch check stays silent.
        clean_content = (
            "---\nname: my-skill\ndescription: Clean test skill.\n---\n\n"
            "# My Skill\n\nStep 1: Do the thing.\n"
        )
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", clean_content)
        assert result["success"] is True
        assert "warnings" not in result

    def test_create_with_missing_reference_warns_but_succeeds(self, tmp_path):
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "# My Skill\n\nSee references/missing.md for details.\n"
        )
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", content)

        # Still succeeds — warnings are non-blocking
        assert result["success"] is True
        assert (tmp_path / "my-skill" / "SKILL.md").exists()
        assert "warnings" in result
        assert any("references/missing.md" in w for w in result["warnings"])

    def test_edit_surfaces_warnings(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            bad_content = (
                "---\nname: my-skill\ndescription: Updated.\n---\n\n"
                "# Updated\n\nSee scripts/missing.py for details.\n"
            )
            result = _edit_skill("my-skill", bad_content)

        assert result["success"] is True
        assert "warnings" in result
        assert any("scripts/missing.py" in w for w in result["warnings"])

    def test_patch_surfaces_warnings(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _patch_skill(
                "my-skill",
                "Do the thing.",
                "Do the thing. See templates/nope.yaml.",
            )

        assert result["success"] is True
        assert "warnings" in result
        assert any("templates/nope.yaml" in w for w in result["warnings"])

    def test_write_file_resolves_warning(self, tmp_path):
        """Adding the missing reference file should clear the warning."""
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "# Skill\n\nSee references/api.md for details.\n"
        )
        with _skill_dir(tmp_path):
            create_result = _create_skill("my-skill", content)
            assert "warnings" in create_result  # missing reference

            write_result = _write_file(
                "my-skill", "references/api.md", "# API Reference\n\nContent here.\n"
            )

        assert write_result["success"] is True
        # Warning should be resolved now — references/api.md exists
        assert "warnings" not in write_result or not any(
            "references/api.md" in w for w in write_result.get("warnings", [])
        )

    def test_python_syntax_warning_via_write_file(self, tmp_path):
        with _skill_dir(tmp_path):
            _create_skill("my-skill", VALID_SKILL_CONTENT)
            result = _write_file(
                "my-skill",
                "scripts/broken.py",
                "def broken(:\n    pass\n",  # syntax error
            )

        assert result["success"] is True  # non-blocking
        assert "warnings" in result
        assert any("syntax error" in w for w in result["warnings"])
        assert any("broken.py" in w for w in result["warnings"])

    def test_name_mismatch_warning_via_create(self, tmp_path):
        # Frontmatter name doesn't match the skill name parameter
        content = (
            "---\nname: different-name\ndescription: Test.\n---\n\n"
            "# Test\n\nBody.\n"
        )
        with _skill_dir(tmp_path):
            result = _create_skill("my-skill", content)

        assert result["success"] is True
        assert "warnings" in result
        assert any(
            "does not match" in w and "different-name" in w
            for w in result["warnings"]
        )

    def test_warnings_serialize_via_dispatcher(self, tmp_path):
        """End-to-end: skill_manage JSON output contains warnings array."""
        content = (
            "---\nname: my-skill\ndescription: Test.\n---\n\n"
            "# My Skill\n\nSee references/missing.md for details.\n"
        )
        with _skill_dir(tmp_path):
            raw = skill_manage(action="create", name="my-skill", content=content)
        result = json.loads(raw)
        assert result["success"] is True
        assert "warnings" in result
        assert isinstance(result["warnings"], list)
        assert len(result["warnings"]) >= 1
