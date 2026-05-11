"""Contract tests for the artifact-builder skill."""

from pathlib import Path

from tools.skill_manager_tool import _validate_frontmatter


ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "skills" / "creative" / "artifact-builder" / "SKILL.md"
RUNTIME_REF_PATH = ROOT / "skills" / "creative" / "artifact-builder" / "references" / "artifact-runtime-api.md"


def _skill_content() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_artifact_builder_skill_exists_with_valid_frontmatter():
    assert SKILL_PATH.exists()
    content = _skill_content()
    assert _validate_frontmatter(content) is None
    assert "name: artifact-builder" in content
    assert "description: Use when" in content


def test_artifact_builder_skill_enforces_out_of_band_registration_contract():
    content = _skill_content()
    required_phrases = [
        "artifact_present",
        "Main chat never receives raw HTML dumps by default",
        "Return structured artifact metadata",
        "sandboxed preview",
        "No `canvas.eval`",
        "No `allow-same-origin` by default",
        "timeout/failure",
    ]
    for phrase in required_phrases:
        assert phrase in content


def test_artifact_builder_skill_documents_runtime_api_reference():
    assert RUNTIME_REF_PATH.exists()
    reference = RUNTIME_REF_PATH.read_text(encoding="utf-8")
    required_phrases = [
        "artifact_present",
        "contentType",
        "url",
        "/api/plugins/artifacts/preview/",
        "text/html",
        "image/svg+xml",
        "application/vnd.mermaid",
    ]
    for phrase in required_phrases:
        assert phrase in reference
