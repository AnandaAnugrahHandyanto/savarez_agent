from __future__ import annotations

from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "optional-skills" / "creative" / "meme-generation" / "SKILL.md"


def test_meme_generation_skill_declares_render_verification():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert 'python "$SKILL_DIR/scripts/generate_meme.py" --list' in text
    assert 'python "$SKILL_DIR/scripts/generate_meme.py" --search "disaster"' in text
    assert 'python "$SKILL_DIR/scripts/generate_meme.py" this-is-fine /tmp/meme.png' in text
    assert "/tmp/meme.png" in text
