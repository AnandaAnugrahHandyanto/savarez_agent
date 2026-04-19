"""Tests for _preprocess_message_images in the API server adapter.

The preprocessor converts OpenAI multipart ``image_url`` content into text
descriptions via the auxiliary vision tool, so images work end-to-end through
any provider backend (the agent pipeline itself is text-only).
"""

import base64
import json
import sys
from unittest.mock import patch

import pytest

from gateway.platforms.api_server import (
    _materialize_data_url,
    _preprocess_message_images,
    _split_content_parts,
)


# ── Helpers ──────────────────────────────────────────────────────────────

_TINY_PNG_BYTES = bytes.fromhex(
    # 1x1 solid-black PNG, smallest valid PNG file.
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000050001aa3e8d610000000049454e44ae426082"
)


def _tiny_png_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(_TINY_PNG_BYTES).decode()


async def _ok_vision(image_url, user_prompt, **_kw):
    return json.dumps({"success": True, "analysis": "a tiny black square"})


async def _failing_vision(image_url, user_prompt, **_kw):
    return json.dumps({"success": False, "analysis": "vision backend unreachable"})


async def _raising_vision(image_url, user_prompt, **_kw):
    raise RuntimeError("boom")


def _install_vision_stub(monkeypatch, impl):
    """Register a stub ``tools.vision_tools.vision_analyze_tool``.

    The preprocessor imports the tool lazily inside the function body, so we
    patch ``sys.modules`` rather than the caller's namespace.
    """
    stub = type(sys)("tools.vision_tools")
    stub.vision_analyze_tool = impl  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tools.vision_tools", stub)


# ── _split_content_parts ─────────────────────────────────────────────────


class TestSplitContentParts:
    def test_separates_text_and_images(self):
        text, urls = _split_content_parts([
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "https://example/a.png"}},
            {"type": "input_text", "text": " world"},
            {"type": "image_url", "image_url": {"url": "https://example/b.png"}},
        ])
        assert text == ["hello", "world"]
        assert urls == ["https://example/a.png", "https://example/b.png"]

    def test_image_url_string_variant(self):
        _, urls = _split_content_parts([
            {"type": "image_url", "image_url": "https://example/c.png"},
        ])
        assert urls == ["https://example/c.png"]

    def test_plain_string_part_is_text(self):
        text, urls = _split_content_parts(["standalone string", {"type": "text", "text": "dict"}])
        assert text == ["standalone string", "dict"]
        assert urls == []

    def test_unknown_type_ignored(self):
        text, urls = _split_content_parts([{"type": "something_weird", "foo": "bar"}])
        assert text == []
        assert urls == []


# ── _materialize_data_url ────────────────────────────────────────────────


class TestMaterializeDataUrl:
    def test_non_data_url_passes_through(self):
        path, cleanup = _materialize_data_url("https://example.com/img.png")
        assert path == "https://example.com/img.png"
        assert cleanup is None

    def test_data_url_written_to_tempfile(self):
        url = _tiny_png_data_url()
        path, cleanup = _materialize_data_url(url)
        try:
            assert cleanup is not None
            assert cleanup.exists()
            assert cleanup.suffix == ".png"
            assert cleanup.read_bytes() == _TINY_PNG_BYTES
            assert path == str(cleanup)
        finally:
            if cleanup is not None and cleanup.exists():
                cleanup.unlink()

    def test_unknown_mime_defaults_to_jpg_suffix(self):
        url = "data:image/tiff;base64," + base64.b64encode(b"tiffdata").decode()
        path, cleanup = _materialize_data_url(url)
        try:
            assert cleanup is not None
            assert cleanup.suffix == ".jpg"
        finally:
            if cleanup is not None and cleanup.exists():
                cleanup.unlink()


# ── _preprocess_message_images ───────────────────────────────────────────


class TestPreprocessMessageImages:
    @pytest.mark.asyncio
    async def test_no_images_leaves_messages_untouched(self, monkeypatch):
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [{"role": "user", "content": "just text"}]
        await _preprocess_message_images(messages)
        assert messages == [{"role": "user", "content": "just text"}]

    @pytest.mark.asyncio
    async def test_multipart_without_image_is_untouched(self, monkeypatch):
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [{
            "role": "user",
            "content": [{"type": "text", "text": "hi"}],
        }]
        await _preprocess_message_images(messages)
        # We only flatten when images are present; text-only multi-part is left
        # for _normalize_chat_content to handle.
        assert messages[0]["content"] == [{"type": "text", "text": "hi"}]

    @pytest.mark.asyncio
    async def test_image_with_text_becomes_enriched_string(self, monkeypatch):
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "what's this?"},
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
            ],
        }]
        await _preprocess_message_images(messages)
        content = messages[0]["content"]
        assert isinstance(content, str)
        assert "a tiny black square" in content
        assert "what's this?" in content
        # Description prefixes the user's text.
        assert content.index("a tiny black square") < content.index("what's this?")

    @pytest.mark.asyncio
    async def test_image_without_text(self, monkeypatch):
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
            ],
        }]
        await _preprocess_message_images(messages)
        assert messages[0]["content"] == (
            "[The user attached an image. Here's what it contains:\n"
            "a tiny black square]"
        )

    @pytest.mark.asyncio
    async def test_multiple_images_concatenated(self, monkeypatch):
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
                {"type": "text", "text": "compare"},
            ],
        }]
        await _preprocess_message_images(messages)
        content = messages[0]["content"]
        # Both descriptions appear, separated from user text.
        assert content.count("a tiny black square") == 2
        assert content.endswith("compare")

    @pytest.mark.asyncio
    async def test_vision_tool_failure_produces_note(self, monkeypatch):
        _install_vision_stub(monkeypatch, _failing_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "https://example/x.png"}},
            ],
        }]
        await _preprocess_message_images(messages)
        content = messages[0]["content"]
        assert isinstance(content, str)
        assert "analysis failed" in content
        assert "look" in content

    @pytest.mark.asyncio
    async def test_vision_tool_exception_produces_note(self, monkeypatch):
        _install_vision_stub(monkeypatch, _raising_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://example/x.png"}},
            ],
        }]
        await _preprocess_message_images(messages)
        content = messages[0]["content"]
        assert "analysis raised" in content
        assert "boom" in content

    @pytest.mark.asyncio
    async def test_data_url_tempfile_cleaned_up(self, monkeypatch):
        seen_paths = []

        async def capture_vision(image_url, user_prompt, **_kw):
            seen_paths.append(image_url)
            return json.dumps({"success": True, "analysis": "ok"})

        _install_vision_stub(monkeypatch, capture_vision)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
            ],
        }]
        await _preprocess_message_images(messages)
        assert len(seen_paths) == 1
        # The tempfile the tool received must have been cleaned up after use.
        from pathlib import Path
        assert not Path(seen_paths[0]).exists()

    @pytest.mark.asyncio
    async def test_missing_vision_tool_does_not_crash(self, monkeypatch):
        # Simulate ``from tools.vision_tools import vision_analyze_tool``
        # raising ImportError by blocking the import.
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == "tools.vision_tools":
                raise ImportError("simulated missing")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "still here"},
                {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
            ],
        }]
        await _preprocess_message_images(messages)
        # Message content is left as-is so downstream normalization handles it.
        assert isinstance(messages[0]["content"], list)

    @pytest.mark.asyncio
    async def test_non_user_messages_also_processed(self, monkeypatch):
        """Processor walks every message, not just user ones."""
        _install_vision_stub(monkeypatch, _ok_vision)
        messages = [
            {"role": "assistant", "content": [
                {"type": "image_url", "image_url": {"url": _tiny_png_data_url()}},
            ]},
        ]
        await _preprocess_message_images(messages)
        assert "a tiny black square" in messages[0]["content"]
