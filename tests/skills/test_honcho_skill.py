from __future__ import annotations

from pathlib import Path


def test_honcho_skill_declares_verification_and_pitfalls():
    skill_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "autonomous-ai-agents"
        / "honcho"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "hermes honcho status" in text
    assert "hermes honcho sync" in text
    assert "memory.provider" in text
    assert "## Pitfalls" in text
    assert "honcho.json" in text
    assert "writeFrequency: session" in text
