from pathlib import Path
import textwrap

from agent.skill_inventory import SkillEntry, load_inventory


def _write_skill(root: Path, name: str, description: str, category: str = ""):
    skill_dir = root / category / name if category else root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            description: {description}
            ---
            body
            """
        ),
        encoding="utf-8",
    )


def test_load_inventory_returns_skill_entries(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "alpha", "First skill", category="cat1")
    _write_skill(skills_dir, "beta", "Second skill", category="cat1")

    monkeypatch.setattr("agent.skill_inventory.get_skills_dir", lambda: skills_dir)
    monkeypatch.setattr("agent.skill_inventory.get_all_skills_dirs", lambda: [skills_dir])

    inv = load_inventory()
    names = sorted(e.name for e in inv.entries)
    assert names == ["alpha", "beta"]
    assert all(isinstance(e, SkillEntry) for e in inv.entries)
    assert all(e.category == "cat1" for e in inv.entries)
    assert {e.description for e in inv.entries} == {"First skill", "Second skill"}

