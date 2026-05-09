"""Static/regression tests for dashboard locale switching."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_skills_descriptions_only_use_japanese_when_locale_is_ja():
    content = (ROOT / "web" / "src" / "pages" / "SkillsPage.tsx").read_text(encoding="utf-8")

    assert 'if (locale === "ja") return SKILL_DESCRIPTION_JA[skill.name] || skill.description;' in content
    assert "return skill.description;" in content
    assert "localizeSkillDescription(skill)" not in content


def test_achievements_plugin_fetches_payload_for_current_locale():
    content = (
        ROOT
        / "plugins"
        / "hermes-achievements"
        / "dashboard"
        / "dist"
        / "index.js"
    ).read_text(encoding="utf-8")

    assert 'localStorage.getItem("hermes-locale") === "ja" ? "ja" : "en"' in content
    assert '"locale=" + encodeURIComponent(currentLocale())' in content
    assert 'tr("Unlocked", "解除済み")' in content
    assert 'React.createElement(StatCard, { label: "解除済み"' not in content
