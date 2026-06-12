from __future__ import annotations

from hermes_cli.workpack import create_or_update_workpack, safe_slug


def test_safe_slug_keeps_name_short_and_filesystem_safe():
    assert safe_slug("Supergoal: Cron/Rate Limit Cleanup!!!") == "supergoal-cron-rate-limit-cleanup"
    assert safe_slug("../../etc/passwd") == "etc-passwd"
    assert len(safe_slug("x" * 120)) <= 64


def test_create_or_update_workpack_creates_skeleton(tmp_path):
    home = tmp_path / "home"
    path = create_or_update_workpack("Trust Sweep PR", "Ship trust sweep", hermes_home=home)

    assert path == home / "workpacks" / "trust-sweep-pr"
    assert (path / "ROADMAP.md").is_file()
    assert (path / "STATE.md").is_file()
    assert (path / "phases").is_dir()
    assert (path / "evidence").is_dir()
    assert (path / "handoff").is_dir()
    assert "Ship trust sweep" in (path / "ROADMAP.md").read_text(encoding="utf-8")


def test_create_or_update_workpack_preserves_existing_files(tmp_path):
    home = tmp_path / "home"
    path = create_or_update_workpack("same", "first", hermes_home=home)
    roadmap = path / "ROADMAP.md"
    roadmap.write_text("custom roadmap", encoding="utf-8")

    again = create_or_update_workpack("same", "second", hermes_home=home)

    assert again == path
    assert roadmap.read_text(encoding="utf-8") == "custom roadmap"
