from __future__ import annotations

from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "parallel-cli" / "SKILL.md"


def test_parallel_cli_skill_declares_prerequisites_verification_and_pitfalls():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Prerequisites" in text
    assert "parallel-cli auth" in text
    assert "## Verification" in text
    assert 'parallel-cli search "latest AI coding agent news" --max-results 3 --json' in text
    assert "research poll" in text
    assert "## Pitfalls" in text
    assert "queued async job is not a completed result" in text
