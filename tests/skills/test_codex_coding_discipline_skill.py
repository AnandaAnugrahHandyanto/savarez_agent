from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "optional-skills" / "software-development" / "codex-coding-discipline"
SCRIPT = SKILL_DIR / "scripts" / "install_agents_block.py"
SKILL_MD = SKILL_DIR / "SKILL.md"


def _load_script():
    spec = importlib.util.spec_from_file_location("install_agents_block", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_skill_description_meets_listing_standard():
    text = SKILL_MD.read_text(encoding="utf-8")
    line = next(line for line in text.splitlines() if line.startswith("description: "))
    description = line.split(":", 1)[1].strip()
    assert len(description) <= 60
    assert description.endswith(".")


def test_agents_installer_creates_and_checks_block(tmp_path):
    installer = _load_script()
    target = tmp_path / "AGENTS.md"

    assert installer.main([str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert installer.START in text
    assert installer.END in text
    assert "Delegation Contract" in text
    assert installer.main(["--check", str(target)]) == 0


def test_agents_installer_is_idempotent(tmp_path):
    installer = _load_script()
    target = tmp_path / "AGENTS.md"

    assert installer.main([str(target)]) == 0
    assert installer.main([str(target)]) == 0

    text = target.read_text(encoding="utf-8")
    assert text.count(installer.START) == 1
