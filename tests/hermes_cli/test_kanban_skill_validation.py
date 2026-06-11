"""Tests for kanban create --skill validation against installed skills."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _validate_skill_names
# ---------------------------------------------------------------------------


class TestValidateSkillNames:
    """Unit tests for the _validate_skill_names helper."""

    def test_empty_list_returns_empty(self):
        from hermes_cli.kanban import _validate_skill_names

        assert _validate_skill_names([]) == []

    def test_none_returns_empty(self):
        """When called with an empty-ish value from the caller."""
        from hermes_cli.kanban import _validate_skill_names

        # The caller passes `[] or []` so this path shouldn't happen,
        # but the guard should be safe anyway.
        assert _validate_skill_names([]) == []

    def test_known_skill_passes(self, tmp_path: Path):
        """A skill with a matching SKILL.md directory is accepted."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n")

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[tmp_path],
        ):
            from hermes_cli.kanban import _validate_skill_names

            assert _validate_skill_names(["my-skill"]) == []

    def test_unknown_skill_rejected(self, tmp_path: Path):
        """A skill name that doesn't match any installed skill is rejected."""
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: real-skill\n---\n")

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[tmp_path],
        ):
            from hermes_cli.kanban import _validate_skill_names

            unknown = _validate_skill_names(["nonexistent-skill"])
            assert unknown == ["nonexistent-skill"]

    def test_mixed_known_and_unknown(self, tmp_path: Path):
        """Only unknown skills are returned; known ones are filtered out."""
        for name in ("alpha", "gamma"):
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[tmp_path],
        ):
            from hermes_cli.kanban import _validate_skill_names

            unknown = _validate_skill_names(["alpha", "beta", "gamma"])
            assert unknown == ["beta"]

    def test_nested_category_dirs(self, tmp_path: Path):
        """Skills in category subdirectories are discovered."""
        cat_dir = tmp_path / "devops" / "my-tool"
        cat_dir.mkdir(parents=True)
        (cat_dir / "SKILL.md").write_text("---\nname: my-tool\n---\n")

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[tmp_path],
        ):
            from hermes_cli.kanban import _validate_skill_names

            assert _validate_skill_names(["my-tool"]) == []

    def test_import_failure_graceful_skip(self):
        """When agent.skill_utils can't be imported, skip validation."""
        with patch.dict("sys.modules", {"agent.skill_utils": None}):
            from hermes_cli.kanban import _validate_skill_names

            # Should not raise; returns empty (no unknowns reported)
            assert _validate_skill_names(["anything"]) == []

    def test_nonexistent_skills_dir(self, tmp_path: Path):
        """A skills directory that doesn't exist is silently skipped."""
        missing = tmp_path / "does-not-exist"

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[missing],
        ):
            from hermes_cli.kanban import _validate_skill_names

            # No skills found → everything is "unknown"
            unknown = _validate_skill_names(["some-skill"])
            assert unknown == ["some-skill"]


# ---------------------------------------------------------------------------
# _cmd_create integration
# ---------------------------------------------------------------------------


class TestCmdCreateSkillValidation:
    """Integration tests: _cmd_create rejects unknown skills before DB."""

    def _make_args(self, skills=None, **overrides):
        """Build a minimal argparse.Namespace for _cmd_create."""
        defaults = dict(
            title="test task",
            body=None,
            assignee=None,
            created_by=None,
            workspace=None,
            branch=None,
            max_runtime=None,
            max_retries=None,
            triage=False,
            idempotency_key=None,
            goal_mode=False,
            goal_max_turns=None,
            initial_status="running",
            parent=None,
            tenant=None,
            priority=0,
            json=False,
            skills=skills or [],
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_create_rejects_unknown_skill(self, tmp_path: Path, capsys):
        """_cmd_create exits 2 when --skill names an uninstalled skill."""
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: real-skill\n---\n")

        with patch(
            "agent.skill_utils.get_all_skills_dirs",
            return_value=[tmp_path],
        ):
            from hermes_cli.kanban import _cmd_create

            args = self._make_args(skills=["nonexistent"])
            rc = _cmd_create(args)
            assert rc == 2
            err = capsys.readouterr().err
            assert "unknown skill(s): nonexistent" in err
            assert "hermes skills install" in err

    def test_create_accepts_known_skill(self, tmp_path: Path):
        """_cmd_create proceeds normally when skills are valid."""
        skill_dir = tmp_path / "valid-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: valid-skill\n---\n")

        with (
            patch(
                "agent.skill_utils.get_all_skills_dirs",
                return_value=[tmp_path],
            ),
            patch("hermes_cli.kanban.kb") as mock_kb,
            patch("hermes_cli.kanban._parse_workspace_flag", return_value=("dir", None)),
            patch("hermes_cli.kanban._parse_branch_flag", return_value=None),
            patch("hermes_cli.kanban._profile_author", return_value="test"),
        ):
            # Mock the context manager and create_task
            mock_conn = mock_kb.connect_closing.return_value.__enter__.return_value
            mock_kb.create_task.return_value = type(
                "Task", (), {"status": "running", "assignee": "worker"}
            )()

            from hermes_cli.kanban import _cmd_create

            args = self._make_args(skills=["valid-skill"])
            # Need to also mock get_task for the post-create display
            mock_kb.get_task.return_value = type(
                "Task",
                (),
                {"status": "running", "assignee": "worker"},
            )()
            rc = _cmd_create(args)
            assert rc == 0

    def test_create_no_skills_skips_validation(self):
        """When no --skill is passed, validation is skipped entirely."""
        with (
            patch("hermes_cli.kanban.kb") as mock_kb,
            patch("hermes_cli.kanban._parse_workspace_flag", return_value=("dir", None)),
            patch("hermes_cli.kanban._parse_branch_flag", return_value=None),
            patch("hermes_cli.kanban._profile_author", return_value="test"),
        ):
            mock_kb.get_task.return_value = type(
                "Task",
                (),
                {"status": "running", "assignee": "worker"},
            )()

            from hermes_cli.kanban import _cmd_create

            args = self._make_args(skills=[])
            rc = _cmd_create(args)
            assert rc == 0
