from __future__ import annotations

from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[2] / "optional-skills" / "research" / "bioinformatics" / "SKILL.md"


def test_bioinformatics_skill_declares_gateway_verification():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "## Verification" in text
    assert "git clone --depth 1 https://github.com/GPTomics/bioSkills.git /tmp/bioSkills-test" in text
    assert "git clone --depth 1 https://github.com/ClawBio/ClawBio.git /tmp/ClawBio-test" in text
    assert "variant-calling/gatk-variant-calling/SKILL.md" in text
    assert "skills/pharmgx-reporter/README.md" in text
    assert "## Pitfalls" in text
