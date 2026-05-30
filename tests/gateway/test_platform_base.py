"""Regression tests for BasePlatformAdapter.extract_media()."""
from __future__ import annotations

from gateway.platforms.base import BasePlatformAdapter


class TestExtractMedia:
    """MEDIA:<path> tag extraction with Windows drive-letter paths."""

    def test_windows_backslash(self):
        """Windows backslash path like C:\\Users\\..."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "MEDIA:C:\\Users\\test\\file.png"
        )
        assert len(media) == 1
        assert media[0][0].endswith("file.png")

    def test_windows_forward_slash(self):
        """Windows forward-slash path like C:/Users/..."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "MEDIA:C:/Users/test/file.png"
        )
        assert len(media) == 1
        assert media[0][0].endswith("file.png")

    def test_windows_with_spaces(self):
        """Windows path containing spaces."""
        media, cleaned = BasePlatformAdapter.extract_media(
            r"MEDIA:C:\Users\test\my file.png"
        )
        assert len(media) == 1
        assert media[0][0].endswith("my file.png")

    def test_unix_absolute(self):
        """Unix absolute path like /tmp/file.png (should still work)."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "MEDIA:/tmp/file.png"
        )
        assert len(media) == 1
        assert media[0][0].endswith("path") is False  # /tmp/file.png
        # Just check it was extracted
        assert "/tmp/" in media[0][0]

    def test_tilde_path(self):
        """Unix tilde path like ~/file.png (should still work)."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "MEDIA:~/file.png"
        )
        assert len(media) == 1
        assert media[0][0].endswith("file.png")

    def test_mixed_text_and_media(self):
        """MEDIA tag alongside other text."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "Here is the file: MEDIA:C:\\Users\\test\\img.png\nPlease review."
        )
        assert len(media) == 1
        assert "MEDIA:" not in cleaned  # tag should be stripped

    def test_no_match_for_non_media(self):
        """Regular text without MEDIA: tag should not match."""
        media, cleaned = BasePlatformAdapter.extract_media(
            "Just some text with a path C:\\Users\\test\\file.png"
        )
        assert len(media) == 0  # no MEDIA: prefix, no match
