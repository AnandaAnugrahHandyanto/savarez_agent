"""Tests for tools/skill_manager_tool.py write-hygiene checks."""

import tools.skill_manager_tool as skill_manager


def _skill_content(body: str) -> str:
    return (
        "---\n"
        "name: demo-skill\n"
        "description: demo\n"
        "---\n\n"
        f"{body}\n"
    )


def _seed_skill(tmp_path, monkeypatch, body: str) -> None:
    monkeypatch.setattr(skill_manager, "SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(skill_manager, "_security_scan_skill", lambda _path: None)
    skill_manager.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skill_dir = skill_manager.SKILLS_DIR / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(_skill_content(body), encoding="utf-8")
    monkeypatch.setattr(skill_manager, "_find_skill", lambda _name: {"path": skill_dir})


class TestCheckDateStamps:
    def test_blocks_changelog_style_date_stamps(self):
        assert skill_manager._check_date_stamps("Updated 2026-05-10")
        assert skill_manager._check_date_stamps("# Added 2026-05")
        assert skill_manager._check_date_stamps("<!-- Session 2026-05-10 -->")

    def test_allows_legitimate_dates_in_examples(self):
        assert skill_manager._check_date_stamps("Use ISO format: 2026-05-10T12:00:00Z") is None
        assert skill_manager._check_date_stamps("pip install package==2024-05-10") is None
        assert skill_manager._check_date_stamps("Use date like 2026-05-10 in examples") is None


class TestCreateSkill:
    def test_create_blocks_date_stamps(self, tmp_path, monkeypatch):
        monkeypatch.setattr(skill_manager, "SKILLS_DIR", tmp_path / "skills")
        monkeypatch.setattr(skill_manager, "_security_scan_skill", lambda _path: None)
        monkeypatch.setattr(skill_manager, "_find_skill", lambda _name: None)
        skill_manager.SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        result = skill_manager._create_skill(
            "demo-skill",
            _skill_content("Updated 2026-05-10\n\n## Rules\nKeep it short."),
        )

        assert result["success"] is False
        assert "date stamps" in result["error"]


class TestEditSkill:
    def test_edit_blocks_duplicate_headings(self, tmp_path, monkeypatch):
        _seed_skill(tmp_path, monkeypatch, "## Rules\nKeep it short.")

        result = skill_manager._edit_skill(
            "demo-skill",
            _skill_content("## Rules\nA\n\n## Rules\nB"),
        )

        assert result["success"] is False
        assert "Duplicate heading 'rules'" in result["error"]


class TestPatchSkill:
    def test_patch_allows_clean_edits_on_legacy_date_stamped_file(self, tmp_path, monkeypatch):
        _seed_skill(tmp_path, monkeypatch, "Updated 2026-05-10\n\n## Rules\nKeep it short.\n\nmarker")

        result = skill_manager._patch_skill("demo-skill", "marker", "marker changed")

        assert result["success"] is True

    def test_patch_allows_clean_edits_on_legacy_duplicate_heading_file(self, tmp_path, monkeypatch):
        _seed_skill(tmp_path, monkeypatch, "## Rules\nA\n\n## Rules\nB\n\nmarker")

        result = skill_manager._patch_skill("demo-skill", "marker", "marker changed")

        assert result["success"] is True

    def test_patch_blocks_new_date_stamp(self, tmp_path, monkeypatch):
        _seed_skill(tmp_path, monkeypatch, "## Rules\nKeep it short.\n\nmarker")

        result = skill_manager._patch_skill("demo-skill", "marker", "Updated 2026-05-10")

        assert result["success"] is False
        assert "date stamps" in result["error"]

    def test_patch_blocks_new_duplicate_heading(self, tmp_path, monkeypatch):
        _seed_skill(tmp_path, monkeypatch, "## Rules\nKeep it short.\n\nmarker")

        result = skill_manager._patch_skill(
            "demo-skill",
            "marker",
            "## Rules\nA second rules block",
        )

        assert result["success"] is False
        assert "already exists" in result["error"]
