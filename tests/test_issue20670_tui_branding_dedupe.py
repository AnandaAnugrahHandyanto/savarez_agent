from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "ui-tui" / "src" / "components" / "branding.tsx"
SOURCE = BRANDING.read_text(encoding="utf-8")


def test_branding_uses_shared_section_list_body_helper():
    assert "const sectionListBody =" in SOURCE
    assert "skillsBody" not in SOURCE
    assert "toolsBody" not in SOURCE


def test_branding_keeps_distinct_overflow_labels():
    assert "'categories'" in SOURCE
    assert "'toolsets'" in SOURCE
    assert "overflowLabel" in SOURCE


def test_branding_has_single_category_row_renderer():
    assert SOURCE.count("shown.map(([k, vs])") == 1
