from __future__ import annotations

from pathlib import Path


SIYUAN_SKILL = Path(__file__).resolve().parents[2] / "optional-skills" / "productivity" / "siyuan" / "SKILL.md"
SHERLOCK_SKILL = Path(__file__).resolve().parents[2] / "optional-skills" / "security" / "sherlock" / "SKILL.md"


def test_siyuan_skill_declares_verification_and_acceptance_ladder():
    text = SIYUAN_SKILL.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "check_siyuan.py" in text
    assert "build_a_share_workspace.py" in text
    assert "payload reports `ok: true`" in text


def test_sherlock_skill_verification_covers_zero_result_outcomes():
    text = SHERLOCK_SKILL.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "sherlock --version" in text
    assert "explicit zero-result outcome" in text
    assert "manually open at least one returned URL" in text
    assert "[+]" in text
