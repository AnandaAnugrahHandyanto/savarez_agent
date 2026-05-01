import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "website" / "scripts" / "skills_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skills_inventory_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_inventory_keeps_superpowers_as_active_primary_compat_skill(
    tmp_path: Path,
    monkeypatch,
):
    mod = load_module()
    runtime_root = tmp_path / "skills"
    skill_dir = runtime_root / "openclaw-imports" / "superpowers"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: superpowers\n"
        "description: Runtime-only OpenClaw compatibility skill.\n"
        "---\n\n"
        "# Superpowers\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "RUNTIME_SKILLS_DIR", runtime_root)

    runtime_skills = mod.collect_runtime_skills(local_skills=[])

    assert len(runtime_skills) == 1
    item = runtime_skills[0]
    assert item["name"] == "superpowers"
    assert item["path"] == "openclaw-imports/superpowers"
    assert item["source"] == "openclaw-compat"
    assert item["status"] == "active"
    assert item["variant"] == "primary"
    assert item["duplicateOf"] == ""

    summary = mod.build_runtime_summary(runtime_skills)
    assert summary["physical_total"] == 1
    assert summary["effective_total"] == 1
    assert summary["by_source"] == {"openclaw-compat": 1}
    assert summary["by_status"] == {"active": 1}
    assert summary["duplicates"] == 0

    compatibility_markdown = mod.render_compatibility_markdown(runtime_skills, summary)
    assert "| `superpowers` | primary | active | — | `openclaw-imports/superpowers` |" in compatibility_markdown
