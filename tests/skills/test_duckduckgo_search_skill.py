from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "optional-skills" / "research" / "duckduckgo-search" / "SKILL.md"


def test_duckduckgo_skill_declares_verification_and_pitfalls():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "command -v ddgs" in text
    assert 'ddgs text -k "fastapi deployment guide" -m 3 -o json' in text
    assert "build_a_share_queries.py" in text
    assert "## Pitfalls" in text
    assert "max_results" in text
    assert "Search is not source confirmation" in text
