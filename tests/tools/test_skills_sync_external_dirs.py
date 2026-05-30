"""Regression tests for #28126 — sync_skills shadowing external_dirs.

These tests pin the behaviour described in the issue:

    When a non-default profile's config.yaml has
    ``skills.external_dirs: ["~/.hermes/skills"]`` (delegating to the
    default profile), sync_skills used to copy every bundled skill into
    ``<profile_home>/skills/`` anyway.  The skill loader then saw two
    same-name candidates (one local, one external) and refused to resolve
    on collision, crashing every worker that auto-loaded the skill with
    a bare ``Error: Unknown skill(s): X``.

The fix:

  1. ``sync_skills()`` consults ``skills.external_dirs`` from the active
     profile's config.yaml.  For any bundled skill already provided by an
     external dir, sync skips the local write and records the entry in
     ``shadowed_by_external``.
  2. A stale shadow (byte-identical to bundled, manifest origin matches)
     left by an earlier buggy sync is best-effort cleaned up.
  3. ``format_missing_skills_error`` produces a multi-line diagnostic
     that lists on-disk candidates and the rejection reason so worker
     crashes surface the underlying cause instead of a bare exit 1.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from agent import skill_utils
from agent.skill_commands import (
    diagnose_missing_skill,
    format_missing_skills_error,
)
from tools.skills_sync import (
    _dir_hash,
    sync_skills,
    _external_skill_index,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def two_profile_layout(tmp_path, monkeypatch):
    """Build the exact layout #28126 describes.

    Layout::

        tmp/
        ├── default_home/.hermes/skills/devops/clair-qa-two-stage/SKILL.md
        ├── profile_home/.hermes/
        │   ├── config.yaml      # external_dirs: [default_home/.hermes/skills]
        │   └── skills/          # <-- where sync_skills writes (the bug)
        └── bundled_repo/skills/devops/clair-qa-two-stage/SKILL.md
                                 └── flat-bundle/SKILL.md   (NOT in default)
    """
    default_home = tmp_path / "default_home" / ".hermes"
    profile_home = tmp_path / "profile_home" / ".hermes"
    bundled = tmp_path / "bundled_repo" / "skills"
    default_skills = default_home / "skills"

    # ── Default-home skills tree (the canonical external source) ──
    canonical = default_skills / "devops" / "clair-qa-two-stage"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: clair-qa-two-stage\ndescription: CLAIR review skill\n---\n\n"
        "Body of the canonical skill.\n",
        encoding="utf-8",
    )

    # ── Bundled repo (what sync_skills wants to copy) ──
    bundled_clair = bundled / "devops" / "clair-qa-two-stage"
    bundled_clair.mkdir(parents=True)
    (bundled_clair / "SKILL.md").write_text(
        "---\nname: clair-qa-two-stage\ndescription: Bundled CLAIR stub\n---\n\n"
        "Stub body.\n",
        encoding="utf-8",
    )
    # A bundled skill that is NOT in the external — should still be copied.
    bundled_flat = bundled / "flat-bundle"
    bundled_flat.mkdir(parents=True)
    (bundled_flat / "SKILL.md").write_text(
        "---\nname: flat-bundle\ndescription: Not in external\n---\n\nBody.\n",
        encoding="utf-8",
    )

    # ── Profile home delegates to default_home via external_dirs ──
    profile_home.mkdir(parents=True)
    config = profile_home / "config.yaml"
    config.write_text(
        "skills:\n"
        f"  external_dirs:\n"
        f"    - {default_skills}\n",
        encoding="utf-8",
    )
    profile_skills = profile_home / "skills"
    # Note: do NOT pre-create the skills dir — sync_skills creates it.

    # Point hermes_home and home() at the profile.
    monkeypatch.setenv("HERMES_HOME", str(profile_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "profile_home")
    skill_utils._external_dirs_cache_clear()

    yield {
        "default_home": default_home,
        "default_skills": default_skills,
        "profile_home": profile_home,
        "profile_skills": profile_skills,
        "bundled": bundled,
        "canonical_skill_dir": canonical,
        "bundled_clair_dir": bundled_clair,
        "bundled_flat_dir": bundled_flat,
    }

    skill_utils._external_dirs_cache_clear()


def _patch_sync(bundled, skills_dir, manifest_file):
    stack = ExitStack()
    stack.enter_context(patch("tools.skills_sync._get_bundled_dir", return_value=bundled))
    stack.enter_context(
        patch(
            "tools.skills_sync._get_optional_dir",
            return_value=bundled.parent / "optional-skills",
        )
    )
    stack.enter_context(patch("tools.skills_sync.SKILLS_DIR", skills_dir))
    stack.enter_context(patch("tools.skills_sync.MANIFEST_FILE", manifest_file))
    return stack


# ── External skill index ──────────────────────────────────────────────────


class TestExternalSkillIndex:
    def test_indexes_external_dir_skills_by_frontmatter_name(self, two_profile_layout):
        idx = _external_skill_index()
        assert "clair-qa-two-stage" in idx
        assert idx["clair-qa-two-stage"] == two_profile_layout["canonical_skill_dir"]

    def test_empty_when_no_external_dirs_configured(self, tmp_path, monkeypatch):
        home = tmp_path / ".hermes"
        home.mkdir()
        # No skills section at all
        (home / "config.yaml").write_text("agent: {}\n", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        skill_utils._external_dirs_cache_clear()
        try:
            assert _external_skill_index() == {}
        finally:
            skill_utils._external_dirs_cache_clear()


# ── The core regression ──────────────────────────────────────────────────


class TestSyncRespectsExternalDirs:
    def test_skips_writing_when_skill_is_provided_by_external_dir(self, two_profile_layout):
        """Core fix: clair-qa-two-stage exists in external_dirs, so
        sync_skills must NOT write it into profile_skills/ — that would
        create the same-name collision that crashes worker agents (#28126).
        """
        skills_dir = two_profile_layout["profile_skills"]
        manifest_file = skills_dir / ".bundled_manifest"

        with _patch_sync(two_profile_layout["bundled"], skills_dir, manifest_file):
            result = sync_skills(quiet=True)

        # The bundled clair skill must NOT have been written.
        assert not (skills_dir / "devops" / "clair-qa-two-stage" / "SKILL.md").exists(), (
            "sync_skills shadowed the external_dir skill — this is the #28126 bug."
        )
        # Sync should report what was shadowed.
        shadowed_names = {entry["name"] for entry in result["shadowed_by_external"]}
        assert "clair-qa-two-stage" in shadowed_names
        # But the bundle-only skill IS still copied.
        assert (skills_dir / "flat-bundle" / "SKILL.md").exists()
        assert "flat-bundle" in result["copied"]
        # And clair is not in copied/updated.
        assert "clair-qa-two-stage" not in result["copied"]
        assert "clair-qa-two-stage" not in result.get("updated", [])

    def test_no_collision_so_loader_resolves_external_unambiguously(self, two_profile_layout):
        """After sync, the loader must see exactly one candidate for
        clair-qa-two-stage (the external one) — not the two-candidate
        collision that produced 'Unknown skill(s)' crashes.
        """
        skills_dir = two_profile_layout["profile_skills"]
        manifest_file = skills_dir / ".bundled_manifest"

        with _patch_sync(two_profile_layout["bundled"], skills_dir, manifest_file):
            sync_skills(quiet=True)

        # Simulate the loader's collision detection: collect all SKILL.md
        # files matching by directory-name across local + external dirs.
        candidates = []
        for root in (skills_dir, two_profile_layout["default_skills"]):
            if not root.exists():
                continue
            for smd in root.rglob("SKILL.md"):
                if smd.parent.name == "clair-qa-two-stage":
                    candidates.append(smd.resolve())

        # Exactly one — the external one.
        assert len(candidates) == 1, f"Expected 1 candidate, got {candidates}"
        assert candidates[0] == (
            two_profile_layout["canonical_skill_dir"] / "SKILL.md"
        ).resolve()

    def test_cleans_up_stale_shadow_left_by_prior_buggy_sync(self, two_profile_layout):
        """If a previous (buggy) sync wrote the shadow already AND the
        user hasn't touched it AND the bundled hash still matches, the
        fixed sync_skills should clean the shadow up rather than leave
        the collision in place.
        """
        skills_dir = two_profile_layout["profile_skills"]
        manifest_file = skills_dir / ".bundled_manifest"
        bundled_clair = two_profile_layout["bundled_clair_dir"]

        # Simulate the bug: prior sync left a byte-identical copy of the
        # bundled clair in profile_skills/, recorded in the manifest.
        shadow = skills_dir / "devops" / "clair-qa-two-stage"
        shadow.mkdir(parents=True)
        (shadow / "SKILL.md").write_text(
            (bundled_clair / "SKILL.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        bundled_hash = _dir_hash(bundled_clair)
        manifest_file.write_text(f"clair-qa-two-stage:{bundled_hash}\n", encoding="utf-8")

        with _patch_sync(two_profile_layout["bundled"], skills_dir, manifest_file):
            result = sync_skills(quiet=True)

        assert not shadow.exists(), "Stale shadow should have been cleaned up."
        assert any(
            e["name"] == "clair-qa-two-stage" for e in result["shadowed_by_external"]
        )

    def test_user_modified_shadow_is_preserved(self, two_profile_layout):
        """If the on-disk shadow has been customised by the user, do NOT
        delete it — surface it via shadowed_by_external so the user can
        decide.  Only byte-identical, unmodified shadows are removed.
        """
        skills_dir = two_profile_layout["profile_skills"]
        manifest_file = skills_dir / ".bundled_manifest"
        bundled_clair = two_profile_layout["bundled_clair_dir"]

        shadow = skills_dir / "devops" / "clair-qa-two-stage"
        shadow.mkdir(parents=True)
        # User customised it
        (shadow / "SKILL.md").write_text("# user-edited content", encoding="utf-8")
        bundled_hash = _dir_hash(bundled_clair)
        manifest_file.write_text(f"clair-qa-two-stage:{bundled_hash}\n", encoding="utf-8")

        with _patch_sync(two_profile_layout["bundled"], skills_dir, manifest_file):
            result = sync_skills(quiet=True)

        assert shadow.exists(), "User-customised shadow must NOT be deleted."
        assert any(
            e["name"] == "clair-qa-two-stage" for e in result["shadowed_by_external"]
        )

    def test_default_profile_without_external_dirs_unaffected(self, tmp_path, monkeypatch):
        """The existing fresh-install behaviour is preserved when no
        external_dirs are configured.
        """
        home = tmp_path / ".hermes"
        home.mkdir()
        # No config.yaml → no external_dirs.
        skills_dir = home / "skills"
        bundled = tmp_path / "bundled" / "skills"
        bundled_skill = bundled / "devops" / "clair-qa-two-stage"
        bundled_skill.mkdir(parents=True)
        (bundled_skill / "SKILL.md").write_text(
            "---\nname: clair-qa-two-stage\n---\n\nBody\n", encoding="utf-8"
        )
        manifest_file = skills_dir / ".bundled_manifest"

        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        skill_utils._external_dirs_cache_clear()

        try:
            with _patch_sync(bundled, skills_dir, manifest_file):
                result = sync_skills(quiet=True)
        finally:
            skill_utils._external_dirs_cache_clear()

        assert "clair-qa-two-stage" in result["copied"]
        assert (skills_dir / "devops" / "clair-qa-two-stage" / "SKILL.md").exists()
        assert result["shadowed_by_external"] == []


# ── Diagnostic improvements ──────────────────────────────────────────────


class TestMissingSkillDiagnostic:
    def test_diagnose_finds_the_external_candidate(self, two_profile_layout):
        info = diagnose_missing_skill("clair-qa-two-stage")
        assert info["identifier"] == "clair-qa-two-stage"
        assert any("clair-qa-two-stage" in m for m in info["matches_on_disk"])
        # Either single-match-but-loader-failed or no-match — both informative.
        assert info["rejection_reason"]

    def test_diagnose_reports_collision_when_two_candidates_exist(self, two_profile_layout):
        # Force the bug state: place a shadow alongside the canonical.
        shadow = two_profile_layout["profile_skills"] / "devops" / "clair-qa-two-stage"
        shadow.mkdir(parents=True)
        (shadow / "SKILL.md").write_text(
            "---\nname: clair-qa-two-stage\n---\nshadow\n", encoding="utf-8"
        )

        info = diagnose_missing_skill("clair-qa-two-stage")
        assert len(info["matches_on_disk"]) >= 2
        assert "collision" in info["rejection_reason"].lower()
        assert "external_dirs" in info["hint"].lower() or "shadow" in info["hint"].lower()

    def test_format_missing_skills_error_preserves_first_line(self, two_profile_layout):
        """The first line keeps the existing 'Unknown skill(s): X' format
        so existing tooling that regex-matches against it still works.
        """
        rendered = format_missing_skills_error(["clair-qa-two-stage", "totally-fake-skill"])
        first_line = rendered.splitlines()[0]
        assert first_line == "Unknown skill(s): clair-qa-two-stage, totally-fake-skill"
        # And the body explains each one.
        assert "clair-qa-two-stage" in rendered
        assert "totally-fake-skill" in rendered
        assert "searched" in rendered
        assert "reason" in rendered

    def test_format_missing_skills_error_for_missing_only(self, tmp_path, monkeypatch):
        home = tmp_path / ".hermes"
        home.mkdir()
        (home / "skills").mkdir()
        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        skill_utils._external_dirs_cache_clear()
        try:
            rendered = format_missing_skills_error(["nonexistent"])
        finally:
            skill_utils._external_dirs_cache_clear()
        assert rendered.startswith("Unknown skill(s): nonexistent")
        assert "not found" in rendered.lower() or "no skill.md" in rendered.lower()


# ── Worker-spawn integration check ────────────────────────────────────────


class TestWorkerSpawnSucceedsAfterSync:
    def test_skill_view_resolves_uniquely_after_sync(self, two_profile_layout):
        """End-to-end style: run sync_skills against the delegating
        profile, then ask skills_tool to look up the skill the same way
        a kanban worker would.  Must succeed with a single match, NOT
        return the ambiguous-collision error.
        """
        skills_dir = two_profile_layout["profile_skills"]
        manifest_file = skills_dir / ".bundled_manifest"

        with _patch_sync(two_profile_layout["bundled"], skills_dir, manifest_file):
            sync_skills(quiet=True)

        # Mimic skills_tool's collision-detection candidate gathering.
        from agent.skill_utils import (
            get_external_skills_dirs,
            iter_skill_index_files,
            is_excluded_skill_path,
        )

        all_dirs = []
        if skills_dir.exists():
            all_dirs.append(skills_dir)
        all_dirs.extend(get_external_skills_dirs())

        seen = set()
        candidates = []
        name = "clair-qa-two-stage"
        for d in all_dirs:
            direct = d / name
            if direct.is_dir() and (direct / "SKILL.md").exists():
                key = (direct / "SKILL.md").resolve()
                if key not in seen:
                    seen.add(key)
                    candidates.append(key)
            for found in iter_skill_index_files(d, "SKILL.md"):
                if is_excluded_skill_path(found):
                    continue
                if found.parent.name == name:
                    key = found.resolve()
                    if key not in seen:
                        seen.add(key)
                        candidates.append(key)

        assert len(candidates) == 1, (
            f"Worker spawn would crash with 'Unknown skill(s)' due to "
            f"{len(candidates)} candidates: {candidates}"
        )
