"""Tests for agent/inline_images.py"""
import json
import os
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.inline_images import (
    _calculate_display_cells,
    _get_png_dimensions,
    _get_image_dimensions_from_data,
    _ensure_png,
    detect_image_protocol,
    extract_image_path_from_tool_result,
    try_render_inline,
    _cached_protocol,
)


def _make_test_png(width=100, height=50) -> bytes:
    """Create a minimal valid PNG file."""
    def make_chunk(chunk_type, data):
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend([128, 128, 128])
    compressed = zlib.compress(bytes(raw), 1)

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', ihdr_data)
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')
    return png


def _make_test_jpeg(width=100, height=50) -> bytes:
    """Create a minimal valid JPEG file via PIL, or a hand-crafted stub."""
    try:
        import io as _io
        from PIL import Image
        img = Image.new("RGB", (width, height), color=(128, 128, 128))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Hand-craft a minimal JPEG with a SOF0 marker so _get_jpeg_dimensions works
        sof = b"\xff\xc0"  # SOF0 marker
        sof_len = struct.pack(">H", 11)  # length
        sof_data = struct.pack(">BHHB", 8, height, width, 3)  # precision, h, w, components
        sof_data += b"\x01\x11\x00\x02\x11\x00\x03\x11\x00"  # component specs
        return b"\xff\xd8" + sof + sof_len + sof_data + b"\xff\xd9"


class TestDetectProtocol:
    def test_kitty_window_id(self):
        with patch.dict(os.environ, {"KITTY_WINDOW_ID": "1", "TERM": "", "TERM_PROGRAM": ""}):
            import agent.inline_images as m
            m._cached_protocol = None
            assert detect_image_protocol() == "kitty"

    def test_ghostty_term(self):
        with patch.dict(os.environ, {"TERM": "xterm-ghostty", "TERM_PROGRAM": "", "KITTY_WINDOW_ID": ""}, clear=False):
            import agent.inline_images as m
            m._cached_protocol = None
            assert detect_image_protocol() == "kitty"

    def test_ghostty_term_program(self):
        with patch.dict(os.environ, {"TERM_PROGRAM": "ghostty", "TERM": "", "KITTY_WINDOW_ID": ""}, clear=False):
            import agent.inline_images as m
            m._cached_protocol = None
            assert detect_image_protocol() == "kitty"

    def test_iterm2(self):
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm2", "TERM": "", "KITTY_WINDOW_ID": ""}, clear=False):
            import agent.inline_images as m
            m._cached_protocol = None
            assert detect_image_protocol() == "iterm2"

    def test_none(self):
        with patch.dict(os.environ, {"TERM": "xterm-256color", "TERM_PROGRAM": "", "KITTY_WINDOW_ID": ""}, clear=False):
            import agent.inline_images as m
            m._cached_protocol = None
            assert detect_image_protocol() == "none"


class TestPNGDimensions:
    def test_valid_png(self):
        png = _make_test_png(320, 200)
        assert _get_png_dimensions(png) == (320, 200)

    def test_invalid_data(self):
        with pytest.raises(ValueError):
            _get_png_dimensions(b"not a png")


class TestExtractImagePath:
    def test_browser_vision(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(_make_test_png())
            f.flush()
            result = json.dumps({"analysis": "a webpage", "screenshot_path": f.name})
            path = extract_image_path_from_tool_result("browser_vision", result)
            assert path == f.name
            os.unlink(f.name)

    def test_image_generate(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(_make_test_png())
            f.flush()
            result = json.dumps({"image": f.name})
            path = extract_image_path_from_tool_result("image_generate", result)
            assert path == f.name
            os.unlink(f.name)

    def test_url_ignored(self):
        result = json.dumps({"image": "https://example.com/image.png"})
        path = extract_image_path_from_tool_result("image_generate", result)
        assert path is None

    def test_unrelated_tool(self):
        result = json.dumps({"screenshot_path": "/tmp/test.png"})
        path = extract_image_path_from_tool_result("terminal", result)
        assert path is None

    def test_invalid_json(self):
        path = extract_image_path_from_tool_result("browser_vision", "not json")
        assert path is None


class TestTryRenderInline:
    def test_disabled_by_config(self):
        result = try_render_inline("/tmp/test.png", config_value=False)
        assert result is False

    def test_nonexistent_file(self):
        result = try_render_inline("/tmp/nonexistent_image_12345.png", config_value="kitty")
        assert result is False

    def test_unsupported_format(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not an image")
            f.flush()
            result = try_render_inline(f.name, config_value="kitty")
            assert result is False
            os.unlink(f.name)

    def test_kitty_renders(self, capsys):
        """Test that kitty protocol produces escape sequences."""
        png = _make_test_png(100, 50)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png)
            f.flush()
            # try_render_inline writes to sys.__stdout__ (bypassing prompt_toolkit),
            # so redirect __stdout__ to a StringIO for capture in tests.
            import io
            buf = io.StringIO()
            old_real = getattr(sys, "__stdout__", sys.stdout)
            sys.__stdout__ = buf
            try:
                result = try_render_inline(f.name, config_value="kitty", indent="")
            finally:
                sys.__stdout__ = old_real
            if result:
                # Should contain kitty escape sequence
                assert "\033_G" in buf.getvalue()
            os.unlink(f.name)


class TestCalculateDisplayCells:
    def test_basic(self):
        cols, rows = _calculate_display_cells(800, 600, max_cols=80, max_rows=24)
        assert 1 <= cols <= 80
        assert 1 <= rows <= 24

    def test_tiny_image(self):
        cols, rows = _calculate_display_cells(10, 10, max_cols=80, max_rows=24)
        assert cols >= 1
        assert rows >= 1


class TestImageDimensionsFromData:
    """Tests for _get_image_dimensions_from_data — the format-agnostic dimension reader."""

    def test_png_data(self):
        png = _make_test_png(320, 200)
        assert _get_image_dimensions_from_data(png) == (320, 200)

    def test_jpeg_data(self):
        jpeg = _make_test_jpeg(160, 120)
        w, h = _get_image_dimensions_from_data(jpeg)
        assert w == 160
        assert h == 120

    def test_unknown_format_fallback(self):
        assert _get_image_dimensions_from_data(b"not an image at all") == (800, 600)


class TestEnsurePng:
    """Tests for _ensure_png — the non-PNG-to-PNG converter."""

    def test_png_passthrough(self):
        """PNG data should be returned unchanged."""
        png = _make_test_png(10, 10)
        result = _ensure_png(png)
        assert result is png  # exact same object, no conversion

    def test_jpeg_converted_to_png(self):
        """JPEG data should be converted to valid PNG (if PIL is available)."""
        jpeg = _make_test_jpeg(20, 15)
        result = _ensure_png(jpeg)
        try:
            import PIL  # noqa: F401
            # PIL available — should have been converted
            assert result[:8] == b"\x89PNG\r\n\x1a\n", "JPEG should be converted to PNG"
            # Verify dimensions are preserved
            w, h = _get_png_dimensions(result)
            assert w == 20
            assert h == 15
        except ImportError:
            # No PIL — data returned as-is
            assert result == jpeg

    def test_unknown_format_passthrough(self):
        """Unknown format should be returned as-is (best-effort)."""
        data = b"definitely not an image"
        result = _ensure_png(data)
        assert result == data


class TestKittySSHJpeg:
    """Regression test: JPEG images over SSH should get correct dimensions and valid protocol output."""

    def test_jpeg_over_ssh_renders(self):
        """Simulate SSH rendering of a JPEG — should produce valid Kitty escape sequences."""
        from agent.inline_images import _render_kitty_from_data
        jpeg = _make_test_jpeg(200, 100)
        output = _render_kitty_from_data(jpeg, max_cols=80, max_rows=24)
        # Must contain kitty graphics protocol escape
        assert "\033_G" in output
        # f=100 is declared (PNG format) — the data should have been converted to PNG
        assert "f=100" in output
