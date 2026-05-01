from __future__ import annotations

from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "gitnexus-explorer" / "SKILL.md"


def test_gitnexus_skill_declares_prerequisites_verification_and_pitfalls():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Prerequisites" in text
    assert "cloudflared" in text
    assert "## Verification" in text
    assert "npx gitnexus --help >/dev/null" in text
    assert 'test -d "$GITNEXUS_DIR/gitnexus-web/dist"' in text
    assert "curl -s http://localhost:8888/api/repos" in text
    assert "## Pitfalls" in text
    assert "--config /dev/null" in text
