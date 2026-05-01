from __future__ import annotations

from pathlib import Path


BLOGWATCHER_A_SHARE = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "blogwatcher-a-share" / "SKILL.md"
QMD_A_SHARE = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "qmd-a-share" / "SKILL.md"


def test_blogwatcher_a_share_skill_declares_full_verification_chain():
    text = BLOGWATCHER_A_SHARE.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "build_a_share_watchlist.py" in text
    assert "build_scrapling_supplement.py" in text
    assert "build_cron_closure.py" in text
    assert "深交所 / 巨潮 / 证监会" in text


def test_qmd_a_share_skill_declares_verification_and_pitfalls():
    text = QMD_A_SHARE.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert 'qmd search "竞价" --limit 3' in text
    assert "## Pitfalls" in text
    assert "只生成 bootstrap JSON 不等于知识库可用" in text
