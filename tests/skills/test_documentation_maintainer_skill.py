from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "software-development" / "documentation-maintainer" / "SKILL.md"


def _frontmatter_and_body():
    src = SKILL_MD.read_text(encoding="utf-8")
    assert src.startswith("---\n")
    end = src.find("\n---\n", 4)
    assert end != -1, "SKILL.md missing closing YAML frontmatter fence"
    frontmatter = yaml.safe_load(src[4:end])
    body = src[end + len("\n---\n"):]
    return frontmatter, body


def test_documentation_maintainer_skill_metadata():
    frontmatter, body = _frontmatter_and_body()

    assert frontmatter["name"] == "documentation-maintainer"
    assert "documentation" in frontmatter["metadata"]["hermes"]["tags"]
    assert "systematic-debugging" in frontmatter["metadata"]["hermes"]["related_skills"]
    assert len(frontmatter["description"]) <= 1024
    assert "## Operating Loop" in body
    assert "git status --short --branch" in body
    assert "Auggie workspace indexing" in body
    assert "CocoIndex" in body
    assert "latest `origin/main`" in body
    assert "Documentation should behave like a build artifact" in body
    assert "Scheduled-run architecture" in body
    assert "cron job `workdir`" in body
    assert "`terminal` and `file` toolsets" in body
    assert "two-pass scan" in body
    assert "evidence ledger" in body


def test_documentation_maintainer_skill_is_not_auto_scheduled_on_install():
    """The bundled skill is loaded by the curated blueprint; installing the skill alone should not create a duplicate suggestion."""
    from tools.blueprints import parse_blueprint

    assert parse_blueprint(SKILL_MD.read_text(encoding="utf-8")) is None
