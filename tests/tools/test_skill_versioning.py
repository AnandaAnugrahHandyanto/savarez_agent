"""Tests for tools/skill_versioning.py — skill version history and rollback."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.skill_versioning import (
    get_version,
    list_versions,
    revert_skill,
    save_version,
)

_VALID_SKILL_V1 = """\
---
name: test-skill
description: A test skill.
---

# Test Skill v1

Step 1: Do the thing.
"""

_VALID_SKILL_V2 = """\
---
name: test-skill
description: Updated description.
---

# Test Skill v2

Step 1: Do the new thing.
"""


@contextmanager
def _skill_env(tmp_path):
    """Isolate skills directory and wire up _find_skill to look inside it."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    with patch("tools.skill_manager_tool.SKILLS_DIR", skills_dir), \
         patch("agent.skill_utils.get_all_skills_dirs", return_value=[skills_dir]), \
         patch("tools.skill_versioning.save_version.MAX_VERSIONS_DEFAULT", 5):
        yield skills_dir


def _create_skill_on_disk(skills_dir: Path, name: str = "test-skill",
                          content: str = _VALID_SKILL_V1,
                          category: str = "") -> Path:
    """Create a skill directory and SKILL.md for testing."""
    if category:
        skill_dir = skills_dir / category / name
    else:
        skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


# ── save_version ──────────────────────────────────────────────────────────


class TestSaveVersion:
    """Test version snapshot creation."""

    def test_save_initial_version(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            assert save_version("test-skill") is True

            # Verify version directory
            vdir = skills_dir / ".history" / "test-skill" / "1"
            assert (vdir / "SKILL.md").exists()
            assert (vdir / "SKILL.md").read_text(encoding="utf-8") == _VALID_SKILL_V1

            # Verify meta.json
            meta = json.loads((skills_dir / ".history" / "test-skill" / "meta.json").read_text())
            assert len(meta["versions"]) == 1
            assert meta["versions"][0]["v"] == 1
            assert meta["versions"][0]["action"] == "create"

    def test_save_multiple_versions(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            save_version("test-skill")  # v1

            # Update content and save again
            skill_md = skills_dir / "test-skill" / "SKILL.md"
            skill_md.write_text(_VALID_SKILL_V2, encoding="utf-8")
            assert save_version("test-skill") is True  # v2

            meta = json.loads((skills_dir / ".history" / "test-skill" / "meta.json").read_text())
            assert len(meta["versions"]) == 2
            assert meta["versions"][0]["v"] == 1
            assert meta["versions"][1]["v"] == 2
            assert meta["versions"][1]["action"] == "edit"

    def test_save_missing_skill_returns_false(self, tmp_path):
        with _skill_env(tmp_path):
            assert save_version("nonexistent") is False

    def test_save_skill_without_skilLmd_returns_false(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            # Create directory but no SKILL.md
            (skills_dir / "empty-skill").mkdir()
            assert save_version("empty-skill") is False

    def test_prune_old_versions(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            for i in range(7):  # max is 5, so we push past it
                save_version("test-skill")
                # Rotate content slightly each time so each version is unique
                skill_md = skills_dir / "test-skill" / "SKILL.md"
                current = skill_md.read_text(encoding="utf-8")
                skill_md.write_text(current.replace(f"v1", f"v{i+2}"), encoding="utf-8")

            meta = json.loads((skills_dir / ".history" / "test-skill" / "meta.json").read_text())
            # Should only have 5 versions (the newest ones)
            assert len(meta["versions"]) == 5
            # Oldest version should be v3 (since v1 and v2 were pruned)
            assert meta["versions"][0]["v"] == 3
            assert meta["versions"][-1]["v"] == 7


# ── list_versions ─────────────────────────────────────────────────────────


class TestListVersions:
    """Test listing version history."""

    def test_list_versions(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            save_version("test-skill")
            # Second version
            skill_md = skills_dir / "test-skill" / "SKILL.md"
            skill_md.write_text(_VALID_SKILL_V2, encoding="utf-8")
            save_version("test-skill")

            versions = list_versions("test-skill")
            assert len(versions) == 2
            # Newest first
            assert versions[0]["v"] == 2
            assert versions[1]["v"] == 1

    def test_list_versions_empty(self, tmp_path):
        with _skill_env(tmp_path):
            assert list_versions("nonexistent") == []


# ── get_version ───────────────────────────────────────────────────────────


class TestGetVersion:
    """Test retrieving a specific version's content."""

    def test_get_version(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            save_version("test-skill")

            content = get_version("test-skill", 1)
            assert content == _VALID_SKILL_V1

    def test_get_nonexistent_version(self, tmp_path):
        with _skill_env(tmp_path):
            assert get_version("test-skill", 99) is None


# ── revert_skill ──────────────────────────────────────────────────────────


class TestRevertSkill:
    """Test reverting a skill to a previous version."""

    def test_revert_to_version(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            save_version("test-skill")  # v1

            skill_md = skills_dir / "test-skill" / "SKILL.md"
            skill_md.write_text(_VALID_SKILL_V2, encoding="utf-8")
            save_version("test-skill")  # v2

            # Mock security scan to pass
            with patch("tools.skill_versioning.save_version._security_scan_skill",
                       return_value=None if False else None):
                with patch("tools.skill_manager_tool._security_scan_skill",
                           return_value=None):
                    result = revert_skill("test-skill", 1)

            assert result.get("success") is True
            assert result.get("to_version") == 1

            # Live SKILL.md should now contain v1 content
            live = skill_md.read_text(encoding="utf-8")
            assert live == _VALID_SKILL_V1

    def test_revert_to_nonexistent_version(self, tmp_path):
        with _skill_env(tmp_path) as skills_dir:
            _create_skill_on_disk(skills_dir)
            save_version("test-skill")

            result = revert_skill("test-skill", 99)
            assert result.get("success") is False
            assert "not found" in result.get("error", "")

    def test_revert_nonexistent_skill(self, tmp_path):
        with _skill_env(tmp_path):
            result = revert_skill("ghost", 1)
            assert result.get("success") is False
            assert "not found" in result.get("error", "")


# ── Integration: save on create/edit/patch via skill_manager hooks ────────


class TestManagerToolHooks:
    """Verify that skill_manager_tool hooks create version history."""

    @contextmanager
    def _manager_env(self, tmp_path):
        """Patches all the paths skill_manager_tool and skill_versioning need."""
        from tools import skill_manager_tool as smt
        from tools import skill_versioning as sv
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        with patch.object(smt, "SKILLS_DIR", skills_dir), \
             patch.object(sv, "save_version._history_dir",
                          lambda n: skills_dir / ".history" / n) if False else \
             patch("agent.skill_utils.get_all_skills_dirs", return_value=[skills_dir]), \
             patch("tools.skill_manager_tool._security_scan_skill", return_value=None), \
             patch("tools.skill_versioning.save_version._max_versions",
                   return_value=10):
            yield skills_dir

    def _create_skill_via_manager(self, skills_dir: Path):
        """Use skill_manage to create a skill (triggers save_version hook)."""
        from tools.skill_manager_tool import _create_skill
        return _create_skill("test-skill", _VALID_SKILL_V1)

    def _edit_skill_via_manager(self, skills_dir: Path):
        from tools.skill_manager_tool import _edit_skill
        return _edit_skill("test-skill", _VALID_SKILL_V2)

    def test_create_triggers_version(self, tmp_path):
        with self._manager_env(tmp_path) as skills_dir:
            result = self._create_skill_via_manager(skills_dir)
            assert result.get("success") is True

            # Version history should exist
            meta_path = skills_dir / ".history" / "test-skill" / "meta.json"
            assert meta_path.exists(), f"meta.json not found at {meta_path}"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            assert len(meta["versions"]) == 1
            assert meta["versions"][0]["v"] == 1

    def test_edit_triggers_new_version(self, tmp_path):
        with self._manager_env(tmp_path) as skills_dir:
            self._create_skill_via_manager(skills_dir)
            result = self._edit_skill_via_manager(skills_dir)
            assert result.get("success") is True

            meta_path = skills_dir / ".history" / "test-skill" / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            assert len(meta["versions"]) == 2
            # v1 = create, v2 = edit
            assert meta["versions"][0]["action"] == "create"
            assert meta["versions"][1]["action"] == "edit"

    def test_edit_saves_old_content(self, tmp_path):
        """Edit should save the OLD content as a version before overwriting."""
        with self._manager_env(tmp_path) as skills_dir:
            self._create_skill_via_manager(skills_dir)
            self._edit_skill_via_manager(skills_dir)

            # Version 1 should contain the original V1 content
            v1 = get_version("test-skill", 1)
            assert v1 == _VALID_SKILL_V1

            # Live file should be V2
            live = (skills_dir / "test-skill" / "SKILL.md").read_text(encoding="utf-8")
            assert live == _VALID_SKILL_V2
