"""Tests for the file upload validation pipeline (file.attach JSON-RPC).

The pipeline is:
  1. _resolve_attachment_path(path)         # existing — path → Path
  2. _validate_upload(path, mime, size)     # NEW — whitelist + size
  3. _copy_to_sandbox(path, session_id)     # NEW — /tmp/<sid>/<hash>.<ext>
  4. _list_attached(session_id)             # NEW — list in sandbox

These tests cover step 2 first (pure, no FS side effects).
"""

import pytest

from cli import _validate_upload, _FILE_WHITELIST


class TestFileWhitelist:
    def test_includes_common_image_types(self):
        assert "image/png" in _FILE_WHITELIST
        assert "image/jpeg" in _FILE_WHITELIST
        assert "image/gif" in _FILE_WHITELIST
        assert "image/webp" in _FILE_WHITELIST

    def test_includes_pdf(self):
        assert "application/pdf" in _FILE_WHITELIST

    def test_includes_plain_text(self):
        assert "text/plain" in _FILE_WHITELIST

    def test_includes_json_yaml_toml(self):
        assert "application/json" in _FILE_WHITELIST
        assert "application/x-yaml" in _FILE_WHITELIST
        assert "application/toml" in _FILE_WHITELIST

    def test_excludes_executables(self):
        # Application/octet-stream is the generic binary catch-all — must be out.
        assert "application/octet-stream" not in _FILE_WHITELIST
        # Windows .exe / .dll MIME types are not in the whitelist.
        assert "application/x-msdownload" not in _FILE_WHITELIST
        assert "application/x-msdos-program" not in _FILE_WHITELIST

    def test_excludes_elf_and_mach_o(self):
        # Linux executables and macOS native binaries.
        assert "application/x-executable" not in _FILE_WHITELIST
        assert "application/x-mach-binary" not in _FILE_WHITELIST

    def test_is_a_frozenset(self):
        # Must be immutable so it can be defined at module scope safely.
        from cli import _FILE_WHITELIST as wl
        assert isinstance(wl, frozenset)


class TestValidateUpload:
    def test_accepts_png_under_limit(self, tmp_path):
        png = tmp_path / "test.png"
        # Minimal valid PNG (1x1 transparent).
        png.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x03\x00\x05\xfe\x02\xfe\xa3\x9b"
            b"\xe0\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        # Should not raise.
        result = _validate_upload(png, mime="image/png", size_bytes=png.stat().st_size)
        assert result.mime_type == "image/png"
        assert result.allowed is True

    def test_rejects_executable_mime(self, tmp_path):
        f = tmp_path / "evil"
        f.write_bytes(b"MZ\x90\x00")  # PE/EXE header
        with pytest.raises(ValueError, match="MIME type not allowed"):
            _validate_upload(f, mime="application/x-msdownload", size_bytes=4)

    def test_rejects_file_over_size_limit(self, tmp_path, monkeypatch):
        # Patch the limit to something tiny for the test.
        import cli
        monkeypatch.setattr(cli, "MAX_UPLOAD_SIZE_BYTES", 100)
        f = tmp_path / "big.png"
        f.write_bytes(b"x" * 200)
        with pytest.raises(ValueError, match="exceeds size limit"):
            _validate_upload(f, mime="image/png", size_bytes=200)

    def test_wildcard_whitelist_allows_any(self, tmp_path, monkeypatch):
        import cli
        monkeypatch.setattr(cli, "_FILE_WHITELIST_ACTIVE", frozenset({"*"}))
        f = tmp_path / "any.bin"
        f.write_bytes(b"\x00\x01\x02")
        result = _validate_upload(f, mime="application/octet-stream", size_bytes=3)
        assert result.allowed is True
