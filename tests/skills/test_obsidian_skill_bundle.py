from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills" / "note-taking"
SKILLS_CATALOG = REPO_ROOT / "website" / "docs" / "reference" / "skills-catalog.md"


def test_official_obsidian_skills_are_bundled():
    expected = {
        "obsidian": [],
        "obsidian-markdown": [
            "references/PROPERTIES.md",
            "references/EMBEDS.md",
            "references/CALLOUTS.md",
        ],
        "obsidian-cli": [],
        "obsidian-bases": ["references/FUNCTIONS_REFERENCE.md"],
        "json-canvas": ["references/EXAMPLES.md"],
    }

    missing = []
    for skill_name, extra_files in expected.items():
        skill_dir = SKILLS_ROOT / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            missing.append(str(skill_md.relative_to(REPO_ROOT)))
            continue
        for rel_path in extra_files:
            file_path = skill_dir / rel_path
            if not file_path.exists():
                missing.append(str(file_path.relative_to(REPO_ROOT)))

    assert not missing, f"Missing bundled Obsidian skill files: {missing}"


def test_obsidian_wrapper_routes_to_specialized_skills():
    wrapper = (SKILLS_ROOT / "obsidian" / "SKILL.md").read_text(encoding="utf-8")

    required_markers = [
        "obsidian-markdown",
        "obsidian-cli",
        "obsidian-bases",
        "json-canvas",
    ]

    missing = [marker for marker in required_markers if marker not in wrapper]
    assert not missing, f"Obsidian wrapper is missing routing guidance for: {missing}"


def test_skills_catalog_lists_additive_obsidian_skills():
    catalog = SKILLS_CATALOG.read_text(encoding="utf-8")

    required_paths = [
        "`note-taking/obsidian`",
        "`note-taking/obsidian-markdown`",
        "`note-taking/obsidian-cli`",
        "`note-taking/obsidian-bases`",
        "`note-taking/json-canvas`",
    ]

    missing = [path for path in required_paths if path not in catalog]
    assert not missing, f"skills-catalog.md is missing rows: {missing}"
