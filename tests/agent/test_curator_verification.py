"""Tests for the curator's on-disk verification helper.

The curator's LLM consolidation pass directs a subagent to copy each
sibling skill's content into ``<umbrella>/references/<topic>.md``.
The model's textual report sometimes claims success even when the
subagent dropped one or more copy steps, leaving silent dead links in
the new umbrella SKILL.md. ``_verify_consolidation_integrity`` audits
these claims against the filesystem after the fact (issue #44760).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def curator_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "skills").mkdir()
    (home / "skills" / ".archive").mkdir()
    (home / "logs").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    import importlib
    import hermes_constants
    importlib.reload(hermes_constants)
    from agent import curator
    importlib.reload(curator)
    from tools import skill_usage
    importlib.reload(skill_usage)
    yield {"home": home, "curator": curator}


def _seed_archived_skill(home: Path, name: str, refs: list[str]) -> None:
    """Write an archived SKILL.md that declares the given references/."""
    arch = home / "skills" / ".archive" / name
    arch.mkdir(parents=True, exist_ok=True)
    body = f"# {name}\n\nSee:\n"
    for ref in refs:
        body += f"- [{ref}]({ref})\n"
    (arch / "SKILL.md").write_text(body, encoding="utf-8")
    (arch / "references").mkdir(exist_ok=True)
    for ref in refs:
        target = arch / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x" * 400, encoding="utf-8")


def _seed_umbrella_ref(home: Path, umbrella: str, ref: str, size: int = 400) -> None:
    target = home / "skills" / umbrella / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x" * size, encoding="utf-8")


def test_verification_clean_run(curator_env):
    home = curator_env["home"]
    curator = curator_env["curator"]

    _seed_archived_skill(home, "alpha", ["references/a.md", "references/b.md"])
    (home / "skills" / "umbrella").mkdir()
    _seed_umbrella_ref(home, "umbrella", "references/a.md")
    _seed_umbrella_ref(home, "umbrella", "references/b.md")

    result = curator._verify_consolidation_integrity(
        consolidated=[{"name": "alpha", "into": "umbrella"}],
        pruned=[],
        skills_root=home / "skills",
        archive_root=home / "skills" / ".archive",
    )
    assert result["ok"] is True
    assert result["consolidations_checked"] == 1
    assert result["missing_refs"] == []
    assert result["missing_archives"] == []
    assert result["prunings_without_archive"] == []


def test_verification_detects_missing_ref_file(curator_env):
    home = curator_env["home"]
    curator = curator_env["curator"]

    _seed_archived_skill(
        home,
        "alpha",
        ["references/a.md", "references/b.md", "references/c.md"],
    )
    (home / "skills" / "umbrella").mkdir()
    _seed_umbrella_ref(home, "umbrella", "references/a.md")
    _seed_umbrella_ref(home, "umbrella", "references/b.md")
    # references/c.md was never copied — silent dead link

    result = curator._verify_consolidation_integrity(
        consolidated=[{"name": "alpha", "into": "umbrella"}],
        pruned=[],
        skills_root=home / "skills",
        archive_root=home / "skills" / ".archive",
    )
    assert result["ok"] is False
    assert len(result["missing_refs"]) == 1
    miss = result["missing_refs"][0]
    assert miss["from"] == "alpha"
    assert miss["into"] == "umbrella"
    assert miss["ref"] == "references/c.md"
    assert miss["reason"] == "absent"


def test_verification_detects_too_small_ref_file(curator_env):
    home = curator_env["home"]
    curator = curator_env["curator"]

    _seed_archived_skill(home, "alpha", ["references/a.md"])
    (home / "skills" / "umbrella").mkdir()
    _seed_umbrella_ref(home, "umbrella", "references/a.md", size=50)

    result = curator._verify_consolidation_integrity(
        consolidated=[{"name": "alpha", "into": "umbrella"}],
        pruned=[],
        skills_root=home / "skills",
        archive_root=home / "skills" / ".archive",
    )
    assert result["ok"] is False
    assert len(result["missing_refs"]) == 1
    assert result["missing_refs"][0]["reason"] == "too_small"


def test_verification_detects_missing_archive_for_consolidation(curator_env):
    home = curator_env["home"]
    curator = curator_env["curator"]

    result = curator._verify_consolidation_integrity(
        consolidated=[{"name": "ghost", "into": "umbrella"}],
        pruned=[],
        skills_root=home / "skills",
        archive_root=home / "skills" / ".archive",
    )
    assert result["ok"] is False
    assert result["missing_archives"] == [{"from": "ghost", "into": "umbrella"}]


def test_verification_detects_pruning_without_archive(curator_env):
    home = curator_env["home"]
    curator = curator_env["curator"]

    result = curator._verify_consolidation_integrity(
        consolidated=[],
        pruned=[{"name": "ghost-pruned"}],
        skills_root=home / "skills",
        archive_root=home / "skills" / ".archive",
    )
    assert result["ok"] is False
    assert result["prunings_without_archive"] == [
        {"name": "ghost-pruned", "archive_missing": True}
    ]


def test_verification_renders_section_when_findings(curator_env):
    curator = curator_env["curator"]
    payload = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 1.0,
        "counts": {},
        "auto_transitions": {},
        "verification": {
            "consolidations_checked": 1,
            "prunings_checked": 1,
            "missing_refs": [
                {"from": "alpha", "into": "umbrella",
                 "ref": "references/c.md", "reason": "absent"},
            ],
            "missing_archives": [],
            "prunings_without_archive": [
                {"name": "ghost", "archive_missing": True},
            ],
            "prunings_with_empty_refs": [],
            "ok": False,
        },
    }
    md = curator._render_report_markdown(payload)
    assert "## Verification" in md
    assert "Missing references" in md
    assert "`alpha`" in md
    assert "`umbrella`" in md
    assert "references/c.md" in md
    assert "absent" in md
    assert "Prunings without recoverable archive" in md
    assert "`ghost`" in md


def test_verification_skips_section_when_clean(curator_env):
    curator = curator_env["curator"]
    payload = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 1.0,
        "counts": {},
        "auto_transitions": {},
        "verification": {
            "consolidations_checked": 0,
            "prunings_checked": 0,
            "missing_refs": [],
            "missing_archives": [],
            "prunings_without_archive": [],
            "prunings_with_empty_refs": [],
            "ok": True,
        },
    }
    md = curator._render_report_markdown(payload)
    assert "## Verification" not in md
