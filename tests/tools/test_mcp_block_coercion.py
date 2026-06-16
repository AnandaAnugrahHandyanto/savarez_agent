"""Regression tests for MCP non-text, non-image content-block coercion.

Background
==========
MCP tool results can carry content blocks beyond plain text and images:
``resource_link`` (a URI pointer), an embedded ``resource`` (inline text or a
binary blob), ``audio``, and occasionally malformed or unknown shapes. The
tool-result handler in ``tools/mcp_tool.py`` used to iterate content blocks
handling only ``block.text`` and cached images; every other block type was
silently dropped, so the agent received an empty or partial result with no way
to tell content was lost.

``_coerce_mcp_block_to_text`` is the fallback that surfaces those remaining
block types as readable notes instead of dropping them. It probes by attribute
(not isinstance against MCP SDK classes) because the ``mcp`` package is an
optional/lazy dependency that is not importable in every process. These tests
lock in that nothing vanishes silently and that binary payloads are noted, not
inlined.
"""

from __future__ import annotations

from types import SimpleNamespace


class TestResourceLinkBlock:
    def test_resource_link_emits_uri_and_metadata(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        block = SimpleNamespace(
            type="resource_link",
            uri="file:///tmp/report.pdf",
            name="report.pdf",
            title="Quarterly report",
            mimeType="application/pdf",
        )
        out = _coerce_mcp_block_to_text(block)
        assert "resource_link" in out
        assert "file:///tmp/report.pdf" in out
        assert "report.pdf" in out
        assert "application/pdf" in out

    def test_resource_link_with_only_uri(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        block = SimpleNamespace(uri="https://example.com/x", resource=None)
        out = _coerce_mcp_block_to_text(block)
        assert "https://example.com/x" in out
        assert out != ""


class TestEmbeddedResourceBlock:
    def test_resource_with_inline_text_is_surfaced_verbatim(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        resource = SimpleNamespace(
            uri="file:///notes.txt", mimeType="text/plain", text="hello from resource"
        )
        block = SimpleNamespace(type="resource", resource=resource)
        assert _coerce_mcp_block_to_text(block) == "hello from resource"

    def test_resource_with_binary_blob_is_noted_not_inlined(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        resource = SimpleNamespace(
            uri="file:///audio.bin",
            mimeType="application/octet-stream",
            blob="QUJDRA==",  # base64 payload that must NOT be inlined
        )
        block = SimpleNamespace(type="resource", resource=resource)
        out = _coerce_mcp_block_to_text(block)
        assert "application/octet-stream" in out
        assert "not inlined" in out
        assert "QUJDRA==" not in out


class TestAudioBlock:
    def test_audio_block_is_noted_not_inlined(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        block = SimpleNamespace(
            type="audio", data="QUJDRA==", mimeType="audio/wav"
        )
        out = _coerce_mcp_block_to_text(block)
        assert "audio" in out
        assert "audio/wav" in out
        assert "not inlined" in out
        assert "QUJDRA==" not in out


class TestUnknownBlock:
    def test_unknown_block_type_is_not_silently_dropped(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        block = SimpleNamespace(type="future_block_kind", payload={"a": 1})
        out = _coerce_mcp_block_to_text(block)
        assert out != ""
        assert "future_block_kind" in out

    def test_block_with_no_type_falls_back_to_class_name(self):
        from tools.mcp_tool import _coerce_mcp_block_to_text

        class WeirdBlock:
            pass

        out = _coerce_mcp_block_to_text(WeirdBlock())
        assert out != ""
        assert "WeirdBlock" in out


class TestNothingDroppedAcrossMixedResult:
    def test_mixed_result_surfaces_every_block(self):
        """A result with text + resource_link + audio + unknown blocks must
        surface a note for each non-text, non-image block. Mirrors the loop in
        ``_make_tool_handler`` without needing a live MCP session."""
        from tools.mcp_tool import _cache_mcp_image_block, _coerce_mcp_block_to_text

        text_block = SimpleNamespace(text="plain answer")
        resource_link = SimpleNamespace(
            type="resource_link", uri="file:///a.txt", resource=None
        )
        audio = SimpleNamespace(type="audio", data="QUJD", mimeType="audio/mpeg")
        unknown = SimpleNamespace(type="mystery")

        parts = []
        for block in (text_block, resource_link, audio, unknown):
            if hasattr(block, "text") and block.text:
                parts.append(block.text)
                continue
            image_tag = _cache_mcp_image_block(block)
            if image_tag:
                parts.append(image_tag)
                continue
            coerced = _coerce_mcp_block_to_text(block)
            if coerced:
                parts.append(coerced)

        # text + 3 coerced notes; nothing dropped
        assert len(parts) == 4
        assert parts[0] == "plain answer"
        assert "file:///a.txt" in parts[1]
        assert "audio/mpeg" in parts[2]
        assert "mystery" in parts[3]
