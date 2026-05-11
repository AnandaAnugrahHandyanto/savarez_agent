"""Tests for agent/skill_utils.py — extract_skill_conditions metadata handling."""

from agent.skill_utils import extract_skill_conditions


def test_metadata_as_dict_with_hermes():
    """Normal case: metadata is a dict containing hermes keys."""
    frontmatter = {
        "metadata": {
            "hermes": {
                "fallback_for_toolsets": ["toolset_a"],
                "requires_toolsets": ["toolset_b"],
                "fallback_for_tools": ["tool_x"],
                "requires_tools": ["tool_y"],
            }
        }
    }
    result = extract_skill_conditions(frontmatter)
    assert result["fallback_for_toolsets"] == ["toolset_a"]
    assert result["requires_toolsets"] == ["toolset_b"]
    assert result["fallback_for_tools"] == ["tool_x"]
    assert result["requires_tools"] == ["tool_y"]


def test_metadata_as_string_does_not_crash():
    """Bug case: metadata is a non-dict truthy value (e.g. a YAML string)."""
    frontmatter = {"metadata": "some text"}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


def test_metadata_as_none():
    """metadata key is present but set to null/None."""
    frontmatter = {"metadata": None}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


def test_metadata_missing_entirely():
    """metadata key is absent from frontmatter."""
    frontmatter = {"name": "my-skill", "description": "Does stuff."}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


# ── rglob_follow tests ────────────────────────────────────────────────────

from agent.skill_utils import rglob_follow


def test_rglob_follow_finds_through_symlink(tmp_path):
    """rgollow should descend into symlinked directories."""
    real = tmp_path / "real-skills" / "alpha"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("name: alpha")

    root = tmp_path / "skills"
    root.mkdir()
    (root / "alpha").symlink_to(real)

    results = list(rglob_follow(root, "SKILL.md"))
    names = [r.parent.name for r in results]
    assert "alpha" in names


def test_rglob_follow_finds_nested_through_symlink(tmp_path):
    """rgollow handles category/<skill>/SKILL.md inside symlinked dirs."""
    real = tmp_path / "workspace" / "skills"
    for name in ["skill-a", "skill-b", "skill-c"]:
        d = real / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"name: {name}")

    root = tmp_path / "hermes-skills"
    root.mkdir()
    (root / "my-skills").symlink_to(real)

    results = list(rglob_follow(root, "SKILL.md"))
    names = {r.parent.name for r in results}
    assert names == {"skill-a", "skill-b", "skill-c"}


def test_rglob_follow_skips_excluded_dirs(tmp_path):
    """Excluded dirs like .archive and .git should be pruned."""
    root = tmp_path / "skills"
    (root / "good").mkdir(parents=True)
    (root / "good" / "SKILL.md").write_text("name: good")
    (root / ".archive").mkdir()
    (root / ".archive" / "old").mkdir()
    (root / ".archive" / "old" / "SKILL.md").write_text("name: old")
    (root / ".git").mkdir()

    results = list(rglob_follow(root, "SKILL.md"))
    names = [r.parent.name for r in results]
    assert "good" in names
    assert "old" not in names


def test_rglob_follow_matches_directory_names(tmp_path):
    """rgollow can also match directory names, not just files."""
    root = tmp_path / "skills"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "SKILL.md").write_text("")

    results = list(rglob_follow(root, "alpha"))
    assert any(r.is_dir() for r in results)


def test_rglob_follow_finds_regular_files(tmp_path):
    """rgollow also works on regular (non-symlinked) directory trees."""
    root = tmp_path / "skills"
    for name in ["a", "b", "c"]:
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"name: {name}")

    results = list(rglob_follow(root, "SKILL.md"))
    assert len(results) == 3
