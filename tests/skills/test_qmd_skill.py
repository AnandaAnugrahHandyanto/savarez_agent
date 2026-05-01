from __future__ import annotations

from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "qmd" / "SKILL.md"


def test_qmd_skill_declares_prerequisites_verification_and_pitfalls():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Prerequisites" in text
    assert "Node.js >= 22" in text
    assert "## Verification" in text
    assert 'qmd search "authentication middleware" --json' in text
    assert "## Pitfalls" in text
    assert "~2GB" in text
    assert "MCP config alone is not proof of integration" in text
