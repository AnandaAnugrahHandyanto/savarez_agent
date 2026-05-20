"""Regression tests for the xurl / x_search routing contract."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
XURL_SKILL = REPO_ROOT / "skills" / "social-media" / "xurl" / "SKILL.md"
X_SEARCH_DOC = REPO_ROOT / "website" / "docs" / "user-guide" / "features" / "x-search.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_xurl_skill_explains_when_to_use_x_search():
    text = _read(XURL_SKILL)

    required_phrases = [
        "If Hermes also exposes the `x_search` tool, route by intent:",
        "Use `x_search` for read-only public X discovery",
        "Use `xurl` for exact or authenticated X API work",
        "use `x_search` to discover candidate public posts",
        "Never treat an `x_search` answer as evidence that an X write happened",
        "Prefer `x_search` over `xurl search`",
    ]
    for phrase in required_phrases:
        assert phrase in text


def test_xurl_agent_workflow_preserves_x_search_preflight():
    text = _read(XURL_SKILL)

    assert "Before using `xurl search`, check intent" in text
    assert "broad public X discovery" in text
    assert "exact API read, authenticated account context, or any X write action" in text


def test_x_search_doc_points_authenticated_actions_to_xurl():
    text = _read(X_SEARCH_DOC)

    required_phrases = [
        "## `x_search` vs `xurl`",
        "Read-only public X discovery",
        "Posting, replying, liking, DMs, media upload, deleting",
        "Exact or authenticated X API work",
        "Any state-changing X action must be confirmed by `xurl` output",
        "switch to the `xurl` skill",
    ]
    for phrase in required_phrases:
        assert phrase in text
