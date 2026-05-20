"""Regression tests for the xAI capability matrix docs page."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "website" / "docs" / "guides" / "xai-capability-matrix.md"
SIDEBAR_PATH = REPO_ROOT / "website" / "sidebars.ts"
OAUTH_GUIDE_PATH = REPO_ROOT / "website" / "docs" / "guides" / "xai-grok-oauth.md"
PROVIDERS_GUIDE_PATH = REPO_ROOT / "website" / "docs" / "integrations" / "providers.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_xai_capability_matrix_is_in_guides_sidebar():
    sidebar = SIDEBAR_PATH.read_text(encoding="utf-8")

    assert "'guides/xai-grok-oauth'" in sidebar
    assert "'guides/xai-capability-matrix'" in sidebar
    assert sidebar.index("'guides/xai-grok-oauth'") < sidebar.index("'guides/xai-capability-matrix'")


def test_xai_guides_link_to_capability_matrix():
    oauth_guide = OAUTH_GUIDE_PATH.read_text(encoding="utf-8")
    providers_guide = PROVIDERS_GUIDE_PATH.read_text(encoding="utf-8")

    assert "./xai-capability-matrix.md" in oauth_guide
    assert "../guides/xai-capability-matrix.md" in providers_guide


def test_xai_capability_matrix_covers_supported_surfaces():
    text = _doc_text()

    for expected in (
        "Chat / agent runtime",
        "OAuth and shared credentials",
        "General web search",
        "X search",
        "Image generation",
        "Video generation",
        "Text to speech",
        "Speech to text",
        "Model retirement guard",
        "`XAI_API_KEY`",
        "`xai-oauth`",
    ):
        assert expected in text


def test_xai_capability_matrix_keeps_not_exposed_gap_list():
    text = _doc_text()

    for expected in (
        "Not First-Class In Hermes Yet",
        "Batch jobs",
        "Deferred chat completions",
        "Server-side code execution",
        "Collections search / RAG",
        "Image editing",
        "Video editing",
        "Video extension",
    ):
        assert expected in text


def test_xai_capability_matrix_links_to_primary_xai_docs():
    text = _doc_text()

    for expected_link in (
        "https://docs.x.ai/developers/models",
        "https://docs.x.ai/developers/tools/web-search",
        "https://docs.x.ai/developers/tools/x-search",
        "https://docs.x.ai/developers/tools/code-execution",
        "https://docs.x.ai/developers/tools/collections-search",
        "https://docs.x.ai/developers/model-capabilities/images/generation",
        "https://docs.x.ai/developers/model-capabilities/video/generation",
        "https://docs.x.ai/developers/model-capabilities/audio/text-to-speech",
        "https://docs.x.ai/developers/model-capabilities/audio/speech-to-text",
        "https://docs.x.ai/developers/advanced-api-usage/batch-api",
        "https://docs.x.ai/developers/advanced-api-usage/deferred-chat-completions",
    ):
        assert expected_link in text
