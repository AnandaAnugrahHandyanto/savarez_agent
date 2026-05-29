"""Tests for gateway/platforms/base.py — MessageEvent, media extraction, message truncation."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.platforms.base import (
    BasePlatformAdapter,
    GATEWAY_SECRET_CAPTURE_UNSUPPORTED_MESSAGE,
    MessageEvent,
    safe_url_for_log,
    utf16_len,
    _FINAL_RESPONSE_IMAGE_EXTS,
    _FINAL_RESPONSE_VIDEO_EXTS,
    _MEDIA_REASON_ALLOWLISTED,
    _MEDIA_REASON_NOT_ABSOLUTE,
    _MEDIA_REASON_NOT_A_FILE,
    _MEDIA_REASON_OUTSIDE_DENIED_PREFIX,
    _MEDIA_REASON_OUTSIDE_NO_RECENCY,
    _MEDIA_REASON_OUTSIDE_STALE_MTIME,
    _MEDIA_REASON_DOES_NOT_RESOLVE,
    _MEDIA_REASON_RECENCY_TRUSTED,
    _MEDIA_REASON_VALIDATION_ERROR,
    _prefix_within_utf16_limit,
    _redact_path_for_log,
    _validate_media_delivery_path_with_reason,
)


class TestSecretCaptureGuidance:
    def test_gateway_secret_capture_message_points_to_local_setup(self):
        message = GATEWAY_SECRET_CAPTURE_UNSUPPORTED_MESSAGE
        assert "local cli" in message.lower()
        assert "~/.hermes/.env" in message


class TestSafeUrlForLog:
    def test_strips_query_fragment_and_userinfo(self):
        url = (
            "https://user:pass@example.com/private/path/image.png"
            "?X-Amz-Signature=supersecret&token=abc#frag"
        )
        result = safe_url_for_log(url)
        assert result == "https://example.com/.../image.png"
        assert "supersecret" not in result
        assert "token=abc" not in result
        assert "user:pass@" not in result

    def test_truncates_long_values(self):
        long_url = "https://example.com/" + ("a" * 300)
        result = safe_url_for_log(long_url, max_len=40)
        assert len(result) == 40
        assert result.endswith("...")

    def test_handles_small_and_non_positive_max_len(self):
        url = "https://example.com/very/long/path/file.png?token=secret"
        assert safe_url_for_log(url, max_len=3) == "..."
        assert safe_url_for_log(url, max_len=2) == ".."
        assert safe_url_for_log(url, max_len=0) == ""


# ---------------------------------------------------------------------------
# MessageEvent — command parsing
# ---------------------------------------------------------------------------


class TestMessageEventIsCommand:
    def test_slash_command(self):
        event = MessageEvent(text="/new")
        assert event.is_command() is True

    def test_regular_text(self):
        event = MessageEvent(text="hello world")
        assert event.is_command() is False

    def test_empty_text(self):
        event = MessageEvent(text="")
        assert event.is_command() is False

    def test_slash_only(self):
        event = MessageEvent(text="/")
        assert event.is_command() is True


class TestMessageEventGetCommand:
    def test_simple_command(self):
        event = MessageEvent(text="/new")
        assert event.get_command() == "new"

    def test_command_with_args(self):
        event = MessageEvent(text="/reset session")
        assert event.get_command() == "reset"

    def test_not_a_command(self):
        event = MessageEvent(text="hello")
        assert event.get_command() is None

    def test_command_is_lowercased(self):
        event = MessageEvent(text="/HELP")
        assert event.get_command() == "help"

    def test_slash_only_returns_empty(self):
        event = MessageEvent(text="/")
        assert event.get_command() == ""

    def test_command_with_at_botname(self):
        event = MessageEvent(text="/new@TigerNanoBot")
        assert event.get_command() == "new"

    def test_command_with_at_botname_and_args(self):
        event = MessageEvent(text="/compress@TigerNanoBot")
        assert event.get_command() == "compress"

    def test_command_mixed_case_with_at_botname(self):
        event = MessageEvent(text="/RESET@TigerNanoBot")
        assert event.get_command() == "reset"


class TestMessageEventGetCommandArgs:
    def test_command_with_args(self):
        event = MessageEvent(text="/new session id 123")
        assert event.get_command_args() == "session id 123"

    def test_command_without_args(self):
        event = MessageEvent(text="/new")
        assert event.get_command_args() == ""

    def test_not_a_command_returns_full_text(self):
        event = MessageEvent(text="hello world")
        assert event.get_command_args() == "hello world"


# ---------------------------------------------------------------------------
# extract_images
# ---------------------------------------------------------------------------


class TestExtractImages:
    def test_no_images(self):
        images, cleaned = BasePlatformAdapter.extract_images("Just regular text.")
        assert images == []
        assert cleaned == "Just regular text."

    def test_markdown_image_with_image_ext(self):
        content = "Here is a photo: ![cat](https://example.com/cat.png)"
        images, cleaned = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/cat.png"
        assert images[0][1] == "cat"
        assert "![cat]" not in cleaned

    def test_markdown_image_jpg(self):
        content = "![photo](https://example.com/photo.jpg)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/photo.jpg"
        assert images[0][1] == "photo"

    def test_markdown_image_jpeg(self):
        content = "![](https://example.com/photo.jpeg)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/photo.jpeg"
        assert images[0][1] == ""

    def test_markdown_image_gif(self):
        content = "![anim](https://example.com/anim.gif)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/anim.gif"
        assert images[0][1] == "anim"

    def test_markdown_image_webp(self):
        content = "![](https://example.com/img.webp)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/img.webp"
        assert images[0][1] == ""

    def test_fal_media_cdn(self):
        content = "![gen](https://fal.media/files/abc123/output.png)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://fal.media/files/abc123/output.png"
        assert images[0][1] == "gen"

    def test_fal_cdn_url(self):
        content = "![](https://fal-cdn.example.com/result)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://fal-cdn.example.com/result"
        assert images[0][1] == ""

    def test_replicate_delivery(self):
        content = "![](https://replicate.delivery/pbxt/abc/output)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://replicate.delivery/pbxt/abc/output"
        assert images[0][1] == ""

    def test_non_image_ext_not_extracted(self):
        """Markdown image with non-image extension should not be extracted."""
        content = "![doc](https://example.com/report.pdf)"
        images, cleaned = BasePlatformAdapter.extract_images(content)
        assert images == []
        assert "![doc]" in cleaned  # Should be preserved

    def test_html_img_tag(self):
        content = 'Check this: <img src="https://example.com/photo.png">'
        images, cleaned = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/photo.png"
        assert images[0][1] == ""  # HTML images have no alt text
        assert "<img" not in cleaned

    def test_html_img_self_closing(self):
        content = '<img src="https://example.com/photo.png"/>'
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/photo.png"
        assert images[0][1] == ""

    def test_html_img_with_closing_tag(self):
        content = '<img src="https://example.com/photo.png"></img>'
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://example.com/photo.png"
        assert images[0][1] == ""

    def test_multiple_images(self):
        content = "![a](https://example.com/a.png)\n![b](https://example.com/b.jpg)"
        images, cleaned = BasePlatformAdapter.extract_images(content)
        assert len(images) == 2
        assert "![a]" not in cleaned
        assert "![b]" not in cleaned

    def test_mixed_markdown_and_html(self):
        content = '![cat](https://example.com/cat.png)\n<img src="https://example.com/dog.jpg">'
        images, _ = BasePlatformAdapter.extract_images(content)
        assert len(images) == 2

    def test_cleaned_content_trims_excess_newlines(self):
        content = "Before\n\n![img](https://example.com/img.png)\n\n\n\nAfter"
        _, cleaned = BasePlatformAdapter.extract_images(content)
        assert "\n\n\n" not in cleaned

    def test_non_http_url_not_matched(self):
        content = "![file](file:///local/path.png)"
        images, _ = BasePlatformAdapter.extract_images(content)
        assert images == []

    def test_non_image_link_preserved_when_mixed_with_images(self):
        """Regression: non-image markdown links must not be silently removed
        when the response also contains real images."""
        content = (
            "Here is the image: ![photo](https://fal.media/cat.png)\n"
            "And a doc: ![report](https://example.com/report.pdf)"
        )
        images, cleaned = BasePlatformAdapter.extract_images(content)
        assert len(images) == 1
        assert images[0][0] == "https://fal.media/cat.png"
        # The PDF link must survive in cleaned content
        assert "![report](https://example.com/report.pdf)" in cleaned


# ---------------------------------------------------------------------------
# extract_media
# ---------------------------------------------------------------------------


class TestExtractMedia:
    def test_no_media(self):
        media, cleaned = BasePlatformAdapter.extract_media("Just text.")
        assert media == []
        assert cleaned == "Just text."

    def test_single_media_tag(self):
        content = "MEDIA:/path/to/audio.ogg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert len(media) == 1
        assert media[0][0] == "/path/to/audio.ogg"
        assert media[0][1] is False  # no voice tag

    def test_media_with_voice_directive(self):
        content = "[[audio_as_voice]]\nMEDIA:/path/to/voice.ogg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert len(media) == 1
        assert media[0][0] == "/path/to/voice.ogg"
        assert media[0][1] is True  # voice tag present

    def test_multiple_media_tags(self):
        content = "MEDIA:/a.ogg\nMEDIA:/b.ogg"
        media, _ = BasePlatformAdapter.extract_media(content)
        assert len(media) == 2

    def test_voice_directive_removed_from_content(self):
        content = "[[audio_as_voice]]\nSome text\nMEDIA:/voice.ogg"
        _, cleaned = BasePlatformAdapter.extract_media(content)
        assert "[[audio_as_voice]]" not in cleaned
        assert "MEDIA:" not in cleaned
        assert "Some text" in cleaned

    def test_media_with_text_before(self):
        content = "Here is your audio:\nMEDIA:/output.ogg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert len(media) == 1
        assert "Here is your audio" in cleaned

    def test_cleaned_content_trims_excess_newlines(self):
        content = "Before\n\nMEDIA:/audio.ogg\n\n\n\nAfter"
        _, cleaned = BasePlatformAdapter.extract_media(content)
        assert "\n\n\n" not in cleaned

    def test_media_tag_allows_optional_whitespace_after_colon(self):
        content = "MEDIA: /path/to/audio.ogg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [("/path/to/audio.ogg", False)]
        assert cleaned == ""

    def test_media_tag_strips_wrapping_quotes_and_backticks(self):
        content = "MEDIA: `/path/to/file.png`\nMEDIA:\"/path/to/file2.png\"\nMEDIA:'/path/to/file3.png'"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [
            ("/path/to/file.png", False),
            ("/path/to/file2.png", False),
            ("/path/to/file3.png", False),
        ]
        assert cleaned == ""

    def test_media_tag_supports_quoted_paths_with_spaces(self):
        content = "Here\nMEDIA: '/tmp/my image.png'\nAfter"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [("/tmp/my image.png", False)]
        assert "Here" in cleaned
        assert "After" in cleaned

    def test_media_tag_supports_unquoted_flac_paths_with_spaces(self):
        content = "MEDIA:/tmp/Jane Doe/speech.flac"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [("/tmp/Jane Doe/speech.flac", False)]
        assert cleaned == ""

    def test_as_document_directive_stripped_from_cleaned_text(self):
        """[[as_document]] is a routing directive — strip it from
        user-visible text just like [[audio_as_voice]]. Callers detect the
        directive on the original content (before extract_media)."""
        content = "Here is your infographic:\n[[as_document]]\nMEDIA:/tmp/x.jpg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [("/tmp/x.jpg", False)]
        assert "[[as_document]]" not in cleaned
        assert "Here is your infographic" in cleaned

    def test_as_document_directive_alone_does_not_attach_voice_flag(self):
        """[[as_document]] is independent of [[audio_as_voice]] — combining
        them in the same response should not entangle the flags."""
        content = "[[as_document]]\nMEDIA:/tmp/x.jpg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        assert media == [("/tmp/x.jpg", False)]  # voice flag stays False
        assert "[[as_document]]" not in cleaned

    def test_both_directives_can_coexist(self):
        """A response could (rarely) contain both [[audio_as_voice]] for an
        ogg file AND [[as_document]] for an attached image. The voice flag
        propagates per-tuple; [[as_document]] is detected at dispatch."""
        content = "[[audio_as_voice]]\n[[as_document]]\nMEDIA:/tmp/x.ogg"
        media, cleaned = BasePlatformAdapter.extract_media(content)
        # Voice flag is propagated to every media tuple (this matches the
        # existing extract_media contract)
        assert media == [("/tmp/x.ogg", True)]
        # Both directives stripped from cleaned text
        assert "[[audio_as_voice]]" not in cleaned
        assert "[[as_document]]" not in cleaned


class TestMediaDeliveryPathValidation:
    def _patch_roots(self, monkeypatch, *roots):
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            tuple(roots),
        )
        # All tests in this class cover strict-mode behavior (allowlist +
        # recency window + denylist). Force strict on so they keep
        # exercising the legacy path even though the public default
        # flipped to off in 2026-05.
        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")
        # Disable recency-based trust by default so the original allowlist
        # tests continue to exercise the strict-allowlist path. Tests that
        # specifically cover recency trust re-enable it themselves.
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

    def test_allows_existing_file_inside_safe_root(self, tmp_path, monkeypatch):
        root = tmp_path / "media-cache"
        media_file = root / "voice.ogg"
        media_file.parent.mkdir(parents=True)
        media_file.write_bytes(b"OggS")
        self._patch_roots(monkeypatch, root)

        assert BasePlatformAdapter.validate_media_delivery_path(str(media_file)) == str(media_file.resolve())

    def test_rejects_existing_file_outside_safe_root(self, tmp_path, monkeypatch):
        root = tmp_path / "media-cache"
        root.mkdir()
        secret = tmp_path / "secrets.txt"
        secret.write_text("not for upload")
        self._patch_roots(monkeypatch, root)

        assert BasePlatformAdapter.validate_media_delivery_path(str(secret)) is None

    def test_rejects_symlink_escape_from_safe_root(self, tmp_path, monkeypatch):
        root = tmp_path / "media-cache"
        root.mkdir()
        secret = tmp_path / "outside.png"
        secret.write_bytes(b"secret")
        link = root / "safe-looking.png"
        try:
            link.symlink_to(secret)
        except OSError:
            pytest.skip("symlink creation is unavailable")
        self._patch_roots(monkeypatch, root)

        assert BasePlatformAdapter.validate_media_delivery_path(str(link)) is None

    def test_filter_keeps_safe_media_and_drops_unsafe(self, tmp_path, monkeypatch):
        root = tmp_path / "media-cache"
        safe = root / "speech.ogg"
        unsafe = tmp_path / "outside.ogg"
        safe.parent.mkdir(parents=True)
        safe.write_bytes(b"OggS")
        unsafe.write_bytes(b"OggS")
        self._patch_roots(monkeypatch, root)

        filtered = BasePlatformAdapter.filter_media_delivery_paths([
            (str(unsafe), False),
            (str(safe), True),
        ])

        assert filtered == [(str(safe.resolve()), True)]

    def test_allows_operator_configured_extra_root(self, tmp_path, monkeypatch):
        extra_root = tmp_path / "operator-media"
        media_file = extra_root / "report.pdf"
        media_file.parent.mkdir(parents=True)
        media_file.write_bytes(b"%PDF-1.4")
        self._patch_roots(monkeypatch)
        monkeypatch.setenv("HERMES_MEDIA_ALLOW_DIRS", str(extra_root))

        assert BasePlatformAdapter.validate_media_delivery_path(str(media_file)) == str(media_file.resolve())

    def test_recency_trust_allows_freshly_produced_file(self, tmp_path, monkeypatch):
        """A PDF the agent just wrote to /tmp should be deliverable.

        Covers the natural case: agent runs ``pandoc -o /tmp/report.pdf`` or
        ``write_file('/home/user/report.pdf', ...)`` and asks the gateway to
        send the result. With recency trust on, fresh files outside the cache
        allowlist are accepted because the file's mtime is within the window.
        """
        self._patch_roots(monkeypatch)  # zero cache allowlist
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")

        fresh = tmp_path / "scratch" / "report.pdf"
        fresh.parent.mkdir(parents=True)
        fresh.write_bytes(b"%PDF-1.4")

        assert BasePlatformAdapter.validate_media_delivery_path(str(fresh)) == str(fresh.resolve())

    def test_recency_trust_rejects_old_file(self, tmp_path, monkeypatch):
        """A pre-existing host file (~/.bashrc, /etc/passwd shape) is rejected.

        Recency trust is the load-bearing anti-injection signal: prompt-injected
        paths point at files that have existed for days or months, well outside
        the trust window.
        """
        self._patch_roots(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "60")

        stale = tmp_path / "stale.pdf"
        stale.write_bytes(b"%PDF-1.4")
        old_mtime = time.time() - 7200  # 2 hours ago
        os.utime(stale, (old_mtime, old_mtime))

        assert BasePlatformAdapter.validate_media_delivery_path(str(stale)) is None

    def test_recency_trust_disabled_falls_back_to_pure_allowlist(self, tmp_path, monkeypatch):
        """Setting trust_recent_files=false reverts to pre-existing strict behavior."""
        self._patch_roots(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        fresh = tmp_path / "report.pdf"
        fresh.write_bytes(b"%PDF-1.4")  # mtime = now

        assert BasePlatformAdapter.validate_media_delivery_path(str(fresh)) is None

    def test_recency_trust_denies_system_paths_even_when_fresh(self, tmp_path, monkeypatch):
        """A freshly-touched file under /etc must NOT be uploaded.

        Belt-and-braces: even if an attacker rewrites the file's mtime
        (e.g. via a separately compromised tool result that touches a system
        file), the denylist refuses to deliver paths under /etc, /proc, /sys,
        ~/.ssh, ~/.aws, etc.
        """
        self._patch_roots(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")

        # Simulate $HOME so ~/.ssh resolves into our tmp dir.
        fake_home = tmp_path / "home"
        ssh_dir = fake_home / ".ssh"
        ssh_dir.mkdir(parents=True)
        secret = ssh_dir / "id_rsa.txt"
        secret.write_bytes(b"-----BEGIN ...")  # mtime = now
        monkeypatch.setenv("HOME", str(fake_home))

        assert BasePlatformAdapter.validate_media_delivery_path(str(secret)) is None

    def test_recency_trust_allows_pdf_in_project_dir(self, tmp_path, monkeypatch):
        """The motivating case: agent produces a PDF in a project directory.

        Reproduces the Discord-PDF-not-delivered bug. Before recency trust,
        files outside ~/.hermes/cache/* were silently dropped, leaving the
        user with a raw filepath in chat instead of an attachment.
        """
        self._patch_roots(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")

        project = tmp_path / "my-project"
        report = project / "build" / "weekly-report.pdf"
        report.parent.mkdir(parents=True)
        report.write_bytes(b"%PDF-1.4")

        assert BasePlatformAdapter.validate_media_delivery_path(str(report)) == str(report.resolve())

    def test_filter_keeps_recently_produced_files(self, tmp_path, monkeypatch):
        """End-to-end: filter_local_delivery_paths routes a fresh PDF through."""
        self._patch_roots(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")

        fresh = tmp_path / "report.pdf"
        fresh.write_bytes(b"%PDF-1.4")

        out = BasePlatformAdapter.filter_local_delivery_paths([str(fresh)])
        assert out == [str(fresh.resolve())]


class TestMediaDeliveryDefaultMode:
    """Default (non-strict) mode — denylist gates delivery, nothing else.

    Symmetric with inbound delivery: Telegram/Discord/Slack accept any
    document type the user uploads, and the agent can hand back any file
    that isn't a credential. Strict mode is opt-in for operators running
    public-facing gateways.
    """

    def _patch_roots(self, monkeypatch, *roots):
        # Empty cache allowlist so the only positive path through
        # validate_media_delivery_path in these tests is the
        # default-mode "anything not denied" branch.
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            tuple(roots),
        )
        # Pin strict OFF — the public default. Tests that exercise the
        # strict path live in TestMediaDeliveryPathValidation.
        monkeypatch.delenv("HERMES_MEDIA_DELIVERY_STRICT", raising=False)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)

    def test_accepts_stale_file_outside_allowlist(self, tmp_path, monkeypatch):
        """The motivating case — agent says ``MEDIA:/home/user/notes.md``
        for an .md it has been working with for hours. Strict mode would
        reject this (outside allowlist, outside recency window). Default
        mode delivers it.
        """
        self._patch_roots(monkeypatch)

        notes = tmp_path / "notes.md"
        notes.write_text("# Old notes\n")
        old_mtime = time.time() - 7200  # 2 hours ago — far outside any window
        os.utime(notes, (old_mtime, old_mtime))

        assert BasePlatformAdapter.validate_media_delivery_path(str(notes)) == str(notes.resolve())

    def test_accepts_any_extension_not_on_denylist(self, tmp_path, monkeypatch):
        """No extension allowlist — .md, .txt, .json, .py all deliver."""
        self._patch_roots(monkeypatch)

        for name in ("report.md", "log.txt", "data.json", "script.py", "blob.bin"):
            f = tmp_path / name
            f.write_bytes(b"x")
            assert BasePlatformAdapter.validate_media_delivery_path(str(f)) == str(f.resolve())

    def test_denylist_still_blocks_credentials(self, tmp_path, monkeypatch):
        """Default mode is permissive but not naive — credential paths
        remain blocked. Simulate $HOME so ~/.ssh resolves into tmp_path.
        """
        self._patch_roots(monkeypatch)

        fake_home = tmp_path / "home"
        ssh_dir = fake_home / ".ssh"
        ssh_dir.mkdir(parents=True)
        secret = ssh_dir / "id_rsa"
        secret.write_bytes(b"-----BEGIN ...")
        monkeypatch.setenv("HOME", str(fake_home))

        assert BasePlatformAdapter.validate_media_delivery_path(str(secret)) is None

    def test_denylist_blocks_system_prefixes(self, tmp_path, monkeypatch):
        """Files under /etc, /proc, /sys, /root, /boot, /var/{log,lib,run}
        are denied. We construct the test by patching the denylist root
        to a tmp dir so we don't need to read /etc.
        """
        self._patch_roots(monkeypatch)

        fake_etc = tmp_path / "fake-etc"
        fake_etc.mkdir()
        secret = fake_etc / "shadow"
        secret.write_bytes(b"root:!:0:0::/root:/bin/sh")

        monkeypatch.setattr(
            "gateway.platforms.base._MEDIA_DELIVERY_DENIED_PREFIXES",
            (str(fake_etc),),
        )

        assert BasePlatformAdapter.validate_media_delivery_path(str(secret)) is None

    def test_denylist_blocks_hermes_credentials(self, tmp_path, monkeypatch):
        """~/.hermes/.env and ~/.hermes/auth.json stay blocked even in
        default mode. They live under $HOME (not the system prefix list)
        so this exercises the home-relative denied paths.
        """
        self._patch_roots(monkeypatch)

        fake_home = tmp_path / "home"
        hermes_dir = fake_home / ".hermes"
        hermes_dir.mkdir(parents=True)
        env_file = hermes_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-...")
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setattr(
            "gateway.platforms.base._HERMES_HOME",
            hermes_dir,
        )

        assert BasePlatformAdapter.validate_media_delivery_path(str(env_file)) is None

    def test_strict_mode_envvar_restores_legacy_behavior(self, tmp_path, monkeypatch):
        """Setting HERMES_MEDIA_DELIVERY_STRICT=1 reactivates the older
        allowlist+recency logic. A stale file outside the allowlist is
        rejected.
        """
        self._patch_roots(monkeypatch)
        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        stale = tmp_path / "old.pdf"
        stale.write_bytes(b"%PDF-1.4")
        old_mtime = time.time() - 7200
        os.utime(stale, (old_mtime, old_mtime))

        assert BasePlatformAdapter.validate_media_delivery_path(str(stale)) is None

    def test_strict_mode_truthy_aliases(self, monkeypatch, tmp_path):
        """``HERMES_MEDIA_DELIVERY_STRICT=true|yes|on|1`` all enable strict mode."""
        self._patch_roots(monkeypatch)
        from gateway.platforms.base import _media_delivery_strict_mode

        for raw in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", raw)
            assert _media_delivery_strict_mode() is True

        for raw in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", raw)
            assert _media_delivery_strict_mode() is False

    def test_filter_passes_default_files_through(self, tmp_path, monkeypatch):
        """End-to-end: filter_local_delivery_paths accepts a stale .md in
        default mode where strict mode would drop it.
        """
        self._patch_roots(monkeypatch)

        notes = tmp_path / "notes.md"
        notes.write_text("# old\n")
        os.utime(notes, (time.time() - 86400, time.time() - 86400))

        out = BasePlatformAdapter.filter_local_delivery_paths([str(notes)])
        assert out == [str(notes.resolve())]


# ---------------------------------------------------------------------------
# MEDIA delivery — broader-than-images regression coverage (#31733 follow-up)
#
# These tests complement #31764 by covering:
#   - The actual ``MEDIA_DELIVERY_SAFE_ROOTS`` constant (no monkeypatch),
#     so canonical+legacy regressions surface against the real config.
#   - The legacy-and-canonical-co-exist failure shape the original bug
#     report calls out (legacy dir exists on disk; ``get_hermes_dir`` picks
#     legacy via *_CACHE_DIR; canonical files would otherwise be dropped).
#   - PDF / document attachments (the existing recency-trust tests cover
#     bare ``/tmp/report.pdf`` flow; these add explicit cache-root coverage).
#   - Diagnosable rejection reasons in logs — the previous generic
#     "Skipping unsafe MEDIA directive path outside allowed roots" warning
#     gave operators no way to tell allowlist-miss apart from stale-mtime
#     apart from denied-prefix.
#   - Final-response vs ``send_message`` extraction parity, since both
#     paths share ``extract_media`` + ``filter_media_delivery_paths`` by
#     design — a regression here silently splits behaviour.
# ---------------------------------------------------------------------------


class TestSafeRootsCoverage:
    """Assertions against the actual ``MEDIA_DELIVERY_SAFE_ROOTS`` constant."""

    def test_default_safe_roots_include_legacy_and_canonical_subdirs(self):
        """Both legacy ``image_cache`` and canonical ``cache/images`` are listed.

        Without explicit entries for both, the ``get_hermes_dir`` resolution
        (returns the legacy path when it exists on disk) silently drops the
        canonical one, which is exactly the failure shape reported in
        #31733 when ``image_generate`` writes to ``cache/images`` on a host
        that still has ``image_cache``.
        """
        from gateway.platforms.base import MEDIA_DELIVERY_SAFE_ROOTS

        # Compare on the last 2 parts (legacy) or last 3 parts (canonical)
        # of each Path. Direct tuple comparison reads more clearly than
        # string suffix matching and is host-path agnostic.
        legacy_tails = {tuple(p.parts[-2:]) for p in MEDIA_DELIVERY_SAFE_ROOTS if len(p.parts) >= 2}
        canonical_tails = {tuple(p.parts[-3:]) for p in MEDIA_DELIVERY_SAFE_ROOTS if len(p.parts) >= 3}

        expected_legacy = {
            (".hermes", "image_cache"),
            (".hermes", "audio_cache"),
            (".hermes", "video_cache"),
            (".hermes", "document_cache"),
            (".hermes", "browser_screenshots"),
        }
        expected_canonical = {
            (".hermes", "cache", "images"),
            (".hermes", "cache", "audio"),
            (".hermes", "cache", "videos"),
            (".hermes", "cache", "documents"),
            (".hermes", "cache", "screenshots"),
        }
        missing_legacy = expected_legacy - legacy_tails
        missing_canonical = expected_canonical - canonical_tails
        assert not missing_legacy, f"Missing legacy roots: {sorted(missing_legacy)}"
        assert not missing_canonical, f"Missing canonical roots: {sorted(missing_canonical)}"

    def test_legacy_and_canonical_image_caches_coexist(self, tmp_path, monkeypatch):
        """Files under canonical ``cache/images`` are deliverable when the legacy
        ``image_cache`` dir also exists on disk.

        This is the exact failure shape from #31733: with the legacy dir
        present, ``get_hermes_dir`` resolves ``IMAGE_CACHE_DIR`` to the legacy
        path, and the canonical path used to fall out of the safe roots tuple.
        The fix is to always list the canonical paths explicitly.
        """
        fake_home = tmp_path / "fake_home"
        legacy_dir = fake_home / ".hermes" / "image_cache"
        canonical_dir = fake_home / ".hermes" / "cache" / "images"
        legacy_dir.mkdir(parents=True)
        canonical_dir.mkdir(parents=True)

        legacy_file = legacy_dir / "legacy.png"
        canonical_file = canonical_dir / "generated.png"
        legacy_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        canonical_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        # Point MEDIA_DELIVERY_SAFE_ROOTS at both, exactly the way main does
        # for ``_HERMES_HOME / "image_cache"`` and ``_HERMES_HOME / "cache" / "images"``.
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            (legacy_dir, canonical_dir),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        assert BasePlatformAdapter.validate_media_delivery_path(str(canonical_file)) == str(canonical_file.resolve())
        assert BasePlatformAdapter.validate_media_delivery_path(str(legacy_file)) == str(legacy_file.resolve())

    def test_pdf_under_canonical_documents_dir_is_accepted(self, tmp_path, monkeypatch):
        """A PDF in ``~/.hermes/cache/documents`` is deliverable.

        Document delivery has been less covered than image delivery; this
        guards against future "canonical roots for images but not documents"
        regressions.
        """
        canonical_docs = tmp_path / ".hermes" / "cache" / "documents"
        canonical_docs.mkdir(parents=True)
        pdf = canonical_docs / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%mock")

        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            (canonical_docs,),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        assert BasePlatformAdapter.validate_media_delivery_path(str(pdf)) == str(pdf.resolve())

    def test_pdf_under_legacy_document_cache_is_accepted(self, tmp_path, monkeypatch):
        """A PDF in the legacy ``~/.hermes/document_cache`` is deliverable.

        Mirrors the canonical-documents test for hosts running older installs.
        """
        legacy_docs = tmp_path / ".hermes" / "document_cache"
        legacy_docs.mkdir(parents=True)
        pdf = legacy_docs / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%mock")

        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            (legacy_docs,),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        assert BasePlatformAdapter.validate_media_delivery_path(str(pdf)) == str(pdf.resolve())


class TestMediaDeliveryRejectionLogging:
    """``filter_*`` callers should log *why* a path was rejected.

    Before this work the warning was just ``"Skipping unsafe MEDIA directive
    path outside allowed roots"``, so operators chasing "the MEDIA tag didn't
    attach" had no way to tell allowlist-miss from stale-mtime from
    denied-prefix without rebuilding the bot with debug logging.

    Reason-tag assertions import the production constants rather than raw
    strings so a future rename of ``_MEDIA_REASON_*`` cannot silently drift
    these tests out of sync with what production actually emits.
    """

    def _patch_roots_empty(self, monkeypatch):
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            tuple(),
        )
        # The allowlist/recency rejection taxonomy this class asserts only
        # applies in strict mode. Since #34022 the default is denylist-only,
        # where an outside-allowlist file is accepted (denylist-cleared)
        # instead of being rejected for stale-mtime / no-recency.
        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")

    def test_filter_media_logs_redacted_path_and_reason_on_stale_mtime(self, tmp_path, monkeypatch, caplog):
        self._patch_roots_empty(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "60")

        stale = tmp_path / "nested" / "subdir" / "report.pdf"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"%PDF-1.4")
        old_mtime = time.time() - 7200
        os.utime(stale, (old_mtime, old_mtime))

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(str(stale), False)])

        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        # Reason tag is present (imported constant, not raw string).
        assert _MEDIA_REASON_OUTSIDE_STALE_MTIME in joined, joined
        # Redacted path keeps filename so operator can map back to the artifact.
        assert "report.pdf" in joined, joined
        # Intermediate "nested" / "subdir" path components are elided.
        assert "nested" not in joined, joined
        assert "subdir" not in joined, joined

    def test_filter_local_logs_reason_no_recency(self, tmp_path, monkeypatch, caplog):
        self._patch_roots_empty(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        fresh = tmp_path / "report.pdf"
        fresh.write_bytes(b"%PDF-1.4")

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_local_delivery_paths([str(fresh)])

        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_OUTSIDE_NO_RECENCY in joined, joined
        assert "report.pdf" in joined, joined

    def test_filter_media_logs_reason_does_not_resolve(self, tmp_path, monkeypatch, caplog):
        """A nonexistent path is the most common false report. Log it usefully."""
        self._patch_roots_empty(monkeypatch)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")

        ghost = tmp_path / "this-was-never-written.pdf"

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(str(ghost), False)])

        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_DOES_NOT_RESOLVE in joined, joined

    def test_filter_media_logs_reason_under_denied_prefix(self, tmp_path, monkeypatch, caplog):
        """A freshly-touched file under a denied prefix logs the denylist reason.

        Belt-and-braces with ``test_recency_trust_denies_system_paths_even_when_fresh``:
        that test asserts the *return value* is None; this asserts the
        *log message* carries the specific reason tag so operators can grep
        for denylist-rejected attempts.
        """
        self._patch_roots_empty(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")

        fake_home = tmp_path / "home"
        ssh_dir = fake_home / ".ssh"
        ssh_dir.mkdir(parents=True)
        secret = ssh_dir / "id_rsa.txt"
        secret.write_bytes(b"-----BEGIN ...")
        monkeypatch.setenv("HOME", str(fake_home))

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(str(secret), False)])

        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_OUTSIDE_DENIED_PREFIX in joined, joined

    def test_filter_media_log_neutralises_newlines_in_path(self, tmp_path, monkeypatch, caplog):
        """A path containing a newline must not produce two log records.

        Without sanitisation an attacker emitting ``MEDIA:/tmp/foo\\nFAKE``
        could forge a second log line that looks operator-emitted.
        """
        self._patch_roots_empty(monkeypatch)
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        evil = "/tmp/foo\nFAKE LOG ENTRY: granted access"

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(evil, False)])

        assert out == []
        # Exactly one record was produced.
        assert len(caplog.records) == 1
        # The newline is replaced with a placeholder so the message stays
        # on a single physical line in the operator log.
        rendered = caplog.records[0].getMessage()
        assert "\n" not in rendered, rendered
        assert "FAKE LOG ENTRY" in rendered  # body still visible, just neutralised


class TestRedactPathForLog:
    """Direct unit coverage for ``_redact_path_for_log``.

    Previously this helper was only exercised indirectly through
    ``filter_media_delivery_paths``. The elision boundary and the
    control-character / line-separator neutralisation are the log-injection
    defense, so they get their own assertions here.
    """

    def test_empty_returns_empty_string(self):
        assert _redact_path_for_log("") == ""

    def test_short_path_is_not_elided(self):
        # 3 or fewer parts ('/', 'etc', 'passwd') -> nothing to elide.
        assert _redact_path_for_log("/etc/passwd") == "/etc/passwd"

    def test_long_path_elides_intermediate_components(self):
        out = _redact_path_for_log("/home/user/projects/sub/report.pdf")
        assert "report.pdf" in out
        assert "..." in out
        assert "projects" not in out
        assert "sub" not in out

    def test_c0_control_chars_replaced(self):
        out = _redact_path_for_log("/tmp/a/b/c/deep\n\r\x00\x1b.pdf")
        for ch in ("\n", "\r", "\x00", "\x1b"):
            assert ch not in out
        assert len(out.splitlines()) == 1, out

    def test_unicode_line_separators_replaced(self):
        # NEL / LS / PS are treated as line breaks by str.splitlines() and most
        # log aggregators, so the redactor must neutralise them too, not just
        # the C0 range.
        for sep in ("\u0085", "\u2028", "\u2029"):
            evil = f"/home/user/deep/dir/evil{sep}INJECTED.pdf"
            out = _redact_path_for_log(evil)
            assert sep not in out, (sep, out)
            assert len(out.splitlines()) == 1, (sep, out)
            assert "INJECTED.pdf" in out  # filename still visible, just neutralised

    def test_unprintable_fallback_for_unconstructable_input(self):
        class _Boom:
            def __fspath__(self):
                raise ValueError("boom")

        # Path(_Boom()).parts raises -> the guarded fallback returns a marker.
        assert _redact_path_for_log(_Boom()) == "<unprintable>"


class TestMediaDeliveryBatchIsolation:
    """One unprocessable MEDIA path must not drop the whole attachment batch.

    Regression for the ``~\\x00...`` cascade: ``os.path.expanduser`` raised
    ``ValueError: embedded null byte`` before ``.resolve()`` was reached, and
    the filter loop had no per-item guard, so a single crafted path aborted the
    batch and silently discarded every other (legitimate) attachment.
    """

    def _patch_roots(self, monkeypatch, *roots):
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            tuple(roots),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

    def test_helper_does_not_raise_on_nul_after_tilde(self):
        resolved, reason = _validate_media_delivery_path_with_reason("~\x00/evil.pdf")
        assert resolved is None
        assert reason == _MEDIA_REASON_DOES_NOT_RESOLVE

    def test_nul_after_tilde_path_does_not_abort_batch(self, tmp_path, monkeypatch, caplog):
        good_dir = tmp_path / "cache"
        good_dir.mkdir()
        good = good_dir / "good.pdf"
        good.write_bytes(b"%PDF-1.4")
        self._patch_roots(monkeypatch, good_dir)

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths(
                [("~\x00/evil.pdf", False), (str(good), False)]
            )

        # The good file survives; the crafted path is dropped, not raised.
        assert out == [(str(good.resolve()), False)]
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_DOES_NOT_RESOLVE in joined, joined

    def test_validator_exception_is_isolated_per_item(self, tmp_path, monkeypatch, caplog):
        """Even an unexpected raise inside the validator drops only that item.

        Exercises the defensive per-item ``try/except`` in the filter loop
        independently of the specific NUL vector (now handled upstream).
        """
        good_dir = tmp_path / "cache"
        good_dir.mkdir()
        good = good_dir / "good.pdf"
        good.write_bytes(b"%PDF-1.4")
        self._patch_roots(monkeypatch, good_dir)

        real = _validate_media_delivery_path_with_reason

        def _boom(path):
            if "boom" in path:
                raise RuntimeError("synthetic validator failure")
            return real(path)

        monkeypatch.setattr(
            "gateway.platforms.base._validate_media_delivery_path_with_reason",
            _boom,
        )

        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths(
                [("/tmp/boom.pdf", False), (str(good), False)]
            )

        assert out == [(str(good.resolve()), False)]
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_VALIDATION_ERROR in joined, joined


class TestMediaDeliveryRejectionReasons:
    """Log-reason coverage for reject branches the original suite skipped."""

    def _patch_roots_empty(self, monkeypatch):
        monkeypatch.setattr("gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS", tuple())
        monkeypatch.delenv("HERMES_MEDIA_ALLOW_DIRS", raising=False)
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

    def test_filter_media_logs_reason_not_absolute(self, monkeypatch, caplog):
        self._patch_roots_empty(monkeypatch)
        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([("relative/report.pdf", False)])
        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_NOT_ABSOLUTE in joined, joined

    def test_filter_media_logs_reason_not_a_file(self, tmp_path, monkeypatch, caplog):
        self._patch_roots_empty(monkeypatch)
        a_dir = tmp_path / "subdir"
        a_dir.mkdir()
        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(str(a_dir), False)])
        assert out == []
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert _MEDIA_REASON_NOT_A_FILE in joined, joined

    def test_filter_media_log_neutralises_unicode_line_separator(self, monkeypatch, caplog):
        """A path containing U+2028 must still produce exactly one log record.

        Companion to ``test_filter_media_log_neutralises_newlines_in_path`` for
        the Unicode line-separator vector that the C0-only regex used to miss.
        """
        self._patch_roots_empty(monkeypatch)
        evil = "/tmp/foo\u2028FAKE LOG ENTRY: granted access"
        with caplog.at_level("WARNING", logger="gateway.platforms.base"):
            out = BasePlatformAdapter.filter_media_delivery_paths([(evil, False)])
        assert out == []
        assert len(caplog.records) == 1
        rendered = caplog.records[0].getMessage()
        assert len(rendered.splitlines()) == 1, rendered
        assert "\u2028" not in rendered


class TestValidateMediaDeliveryPathDelegation:
    """``validate_media_delivery_path`` must agree with the reason-bearing helper.

    The public ``validate_media_delivery_path`` discards the reason and
    returns just the resolved path. If those two surfaces ever diverge,
    callers seeing ``None`` would log one reason while callers seeing the
    resolved path would assume a different one.
    """

    def _patch_roots(self, monkeypatch, *roots):
        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            tuple(roots),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

    def test_public_and_reason_helper_agree_on_resolved_path(self, tmp_path, monkeypatch):
        root = tmp_path / "cache"
        root.mkdir()
        accepted = root / "ok.pdf"
        accepted.write_bytes(b"%PDF-1.4")
        rejected = tmp_path / "outside.pdf"
        rejected.write_bytes(b"%PDF-1.4")
        self._patch_roots(monkeypatch, root)

        # Recency disabled (set by _patch_roots): covers the allowlisted ACCEPT
        # plus the reject branches empty / not-absolute / does-not-resolve /
        # not-a-file (str(root) resolves but is a directory).
        for candidate in (
            str(accepted),          # allowlisted ACCEPT
            str(root),              # resolves but is a directory -> not-a-file
            str(rejected),          # outside allowlist, recency off -> reject
            "",                     # empty
            "relative.pdf",         # not-absolute
            "/does/not/exist.pdf",  # does-not-resolve
        ):
            public = BasePlatformAdapter.validate_media_delivery_path(candidate)
            internal_resolved, _reason = _validate_media_delivery_path_with_reason(candidate)
            assert public == internal_resolved, (
                f"Public API drifted from reason-bearing helper for input {candidate!r}: "
                f"public={public!r} internal={internal_resolved!r}"
            )

        # Recency-trusted ACCEPT path: an outside-allowlist file fresh enough to
        # pass recency trust must also agree between the two surfaces. This case
        # was previously unreachable here because recency was disabled
        # unconditionally, leaving the ACCEPT-via-recency branch unverified.
        # Recency only gates delivery in strict mode (the default is
        # denylist-only since #34022), so enable strict mode to reach it.
        monkeypatch.setenv("HERMES_MEDIA_DELIVERY_STRICT", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "1")
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_SECONDS", "600")
        fresh_outside = tmp_path / "fresh_report.pdf"
        fresh_outside.write_bytes(b"%PDF-1.4")
        public = BasePlatformAdapter.validate_media_delivery_path(str(fresh_outside))
        internal_resolved, reason = _validate_media_delivery_path_with_reason(str(fresh_outside))
        assert public == internal_resolved == str(fresh_outside.resolve())
        assert reason == _MEDIA_REASON_RECENCY_TRUSTED


class TestFinalResponseSendMessageParity:
    """Final-response and ``send_message`` tool paths share extraction/validation.

    Both call ``extract_media`` + ``filter_media_delivery_paths`` on the
    response body, by design, so a MEDIA tag that survives one path must
    survive the other. A regression here would silently split behaviour
    (e.g. final response stops attaching while send_message keeps working,
    which is exactly the operator pain reported alongside #31733).
    """

    def test_send_message_tool_imports_the_same_extraction_surface(self):
        """``send_message`` tool must reach for ``BasePlatformAdapter`` and the
        same ``extract_media`` / ``filter_media_delivery_paths`` staticmethods.

        If a future refactor splits the tool onto a separate extraction chain,
        this test catches it at import time before behaviour can drift.
        """
        from tools import send_message_tool
        import inspect

        src = inspect.getsource(send_message_tool)
        assert "from gateway.platforms.base import BasePlatformAdapter" in src
        assert "BasePlatformAdapter.extract_media" in src
        assert "BasePlatformAdapter.filter_media_delivery_paths" in src

    def test_pdf_media_tag_resolves_through_shared_extraction_surface(self, tmp_path, monkeypatch):
        """Drive the shared ``extract_media`` + ``filter_media_delivery_paths``
        surface with a representative PDF MEDIA tag and confirm a clean resolve.

        This does NOT prove behavioural parity on its own: it exercises the
        shared staticmethods once, it does not invoke ``send_message_tool``.
        The parity guarantee is structural and is asserted separately by
        ``test_send_message_tool_imports_the_same_extraction_surface`` (both
        call sites reach the same ``BasePlatformAdapter`` staticmethods). This
        test guards that those staticmethods still produce what both callers
        expect for the canonical-documents PDF case.
        """
        canonical_docs = tmp_path / ".hermes" / "cache" / "documents"
        canonical_docs.mkdir(parents=True)
        pdf = canonical_docs / "quote.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            (canonical_docs,),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        body = f"Here is your quote.\n\nMEDIA:{pdf}\n"

        media, cleaned = BasePlatformAdapter.extract_media(body)
        filtered = BasePlatformAdapter.filter_media_delivery_paths(media)

        assert filtered == [(str(pdf.resolve()), False)]
        assert "MEDIA:" not in cleaned

    def test_pdf_extension_routes_to_document_not_image_or_video(self, tmp_path, monkeypatch):
        """A PDF must land on the document/send_document branch, not image or video.

        Guards against future regressions in the dispatch partition in
        ``_process_message_background``, which uses
        ``_FINAL_RESPONSE_IMAGE_EXTS`` / ``_FINAL_RESPONSE_VIDEO_EXTS``
        (imported from production) to decide between ``send_multiple_images`` /
        ``send_video`` / ``send_document``.
        """
        canonical_docs = tmp_path / ".hermes" / "cache" / "documents"
        canonical_docs.mkdir(parents=True)
        pdf = canonical_docs / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        monkeypatch.setattr(
            "gateway.platforms.base.MEDIA_DELIVERY_SAFE_ROOTS",
            (canonical_docs,),
        )
        monkeypatch.setenv("HERMES_MEDIA_TRUST_RECENT_FILES", "0")

        media, _ = BasePlatformAdapter.extract_media(f"MEDIA:{pdf}")
        filtered = BasePlatformAdapter.filter_media_delivery_paths(media)
        assert filtered == [(str(pdf.resolve()), False)]

        ext = Path(filtered[0][0]).suffix.lower()
        assert ext == ".pdf"
        # Use the production constants so a future addition like ``.heic``
        # to the image set would surface here instead of drifting silently.
        assert ext not in _FINAL_RESPONSE_IMAGE_EXTS, "PDF must NOT route through send_multiple_images"
        assert ext not in _FINAL_RESPONSE_VIDEO_EXTS, "PDF must NOT route through send_video"


# ---------------------------------------------------------------------------
# should_send_media_as_audio
# ---------------------------------------------------------------------------

class TestShouldSendMediaAsAudio:
    """Audio-routing policy shared by gateway + scheduler + send_message."""

    def test_unknown_extension_returns_false(self):
        from gateway.platforms.base import should_send_media_as_audio
        assert should_send_media_as_audio(None, ".png") is False
        assert should_send_media_as_audio("telegram", ".pdf") is False

    def test_non_telegram_platforms_route_all_audio(self):
        from gateway.platforms.base import should_send_media_as_audio
        for ext in (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus"):
            assert should_send_media_as_audio("discord", ext) is True
            assert should_send_media_as_audio("slack", ext) is True

    def test_telegram_mp3_and_m4a_route_to_audio(self):
        from gateway.platforms.base import should_send_media_as_audio
        assert should_send_media_as_audio("telegram", ".mp3") is True
        assert should_send_media_as_audio("telegram", ".m4a") is True

    def test_telegram_wav_and_flac_fall_through_to_document(self):
        from gateway.platforms.base import should_send_media_as_audio
        assert should_send_media_as_audio("telegram", ".wav") is False
        assert should_send_media_as_audio("telegram", ".flac") is False

    def test_telegram_ogg_opus_only_when_voice_flagged(self):
        from gateway.platforms.base import should_send_media_as_audio
        assert should_send_media_as_audio("telegram", ".ogg", is_voice=True) is True
        assert should_send_media_as_audio("telegram", ".opus", is_voice=True) is True
        assert should_send_media_as_audio("telegram", ".ogg") is False
        assert should_send_media_as_audio("telegram", ".opus") is False

    def test_accepts_platform_enum(self):
        from gateway.config import Platform
        from gateway.platforms.base import should_send_media_as_audio
        assert should_send_media_as_audio(Platform.TELEGRAM, ".mp3") is True
        assert should_send_media_as_audio(Platform.TELEGRAM, ".flac") is False
        assert should_send_media_as_audio(Platform.DISCORD, ".flac") is True


# ---------------------------------------------------------------------------
# truncate_message
# ---------------------------------------------------------------------------


class TestTruncateMessage:
    def _adapter(self):
        """Create a minimal adapter instance for testing static/instance methods."""

        class StubAdapter(BasePlatformAdapter):
            async def connect(self):
                return True

            async def disconnect(self):
                pass

            async def send(self, *a, **kw):
                pass

            async def get_chat_info(self, *a):
                return {}

        from gateway.config import Platform, PlatformConfig

        config = PlatformConfig(enabled=True, token="test")
        return StubAdapter(config=config, platform=Platform.TELEGRAM)

    def test_short_message_single_chunk(self):
        adapter = self._adapter()
        chunks = adapter.truncate_message("Hello world", max_length=100)
        assert chunks == ["Hello world"]

    def test_exact_length_single_chunk(self):
        adapter = self._adapter()
        msg = "x" * 100
        chunks = adapter.truncate_message(msg, max_length=100)
        assert chunks == [msg]

    def test_long_message_splits(self):
        adapter = self._adapter()
        msg = "word " * 200  # ~1000 chars
        chunks = adapter.truncate_message(msg, max_length=200)
        assert len(chunks) > 1
        # Verify all original content is preserved across chunks
        reassembled = "".join(chunks)
        # Strip chunk indicators like (1/N) to get raw content
        for word in msg.strip().split():
            assert word in reassembled, f"Word '{word}' lost during truncation"

    def test_chunks_have_indicators(self):
        adapter = self._adapter()
        msg = "word " * 200
        chunks = adapter.truncate_message(msg, max_length=200)
        assert "(1/" in chunks[0]
        assert f"({len(chunks)}/{len(chunks)})" in chunks[-1]

    def test_code_block_first_chunk_closed(self):
        adapter = self._adapter()
        msg = "Before\n```python\n" + "x = 1\n" * 100 + "```\nAfter"
        chunks = adapter.truncate_message(msg, max_length=300)
        assert len(chunks) > 1
        # First chunk must have a closing fence appended (code block was split)
        first_fences = chunks[0].count("```")
        assert first_fences == 2, "First chunk should have opening + closing fence"

    def test_code_block_language_tag_carried(self):
        adapter = self._adapter()
        msg = "Start\n```javascript\n" + "console.log('x');\n" * 80 + "```\nEnd"
        chunks = adapter.truncate_message(msg, max_length=300)
        if len(chunks) > 1:
            # At least one continuation chunk should reopen with ```javascript
            reopened_with_lang = any("```javascript" in chunk for chunk in chunks[1:])
            assert reopened_with_lang, (
                "No continuation chunk reopened with language tag"
            )

    def test_continuation_chunks_have_balanced_fences(self):
        """Regression: continuation chunks must close reopened code blocks."""
        adapter = self._adapter()
        msg = "Before\n```python\n" + "x = 1\n" * 100 + "```\nAfter"
        chunks = adapter.truncate_message(msg, max_length=300)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            fence_count = chunk.count("```")
            assert fence_count % 2 == 0, (
                f"Chunk {i} has unbalanced fences ({fence_count})"
            )

    def test_each_chunk_under_max_length(self):
        adapter = self._adapter()
        msg = "word " * 500
        max_len = 200
        chunks = adapter.truncate_message(msg, max_length=max_len)
        for i, chunk in enumerate(chunks):
            assert len(chunk) <= max_len + 20, (
                f"Chunk {i} too long: {len(chunk)} > {max_len}"
            )


# ---------------------------------------------------------------------------
# _get_human_delay
# ---------------------------------------------------------------------------


class TestGetHumanDelay:
    def test_off_mode(self):
        with patch.dict(os.environ, {"HERMES_HUMAN_DELAY_MODE": "off"}):
            assert BasePlatformAdapter._get_human_delay() == 0.0

    def test_default_is_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HERMES_HUMAN_DELAY_MODE", None)
            assert BasePlatformAdapter._get_human_delay() == 0.0

    def test_natural_mode_range(self):
        with patch.dict(os.environ, {"HERMES_HUMAN_DELAY_MODE": "natural"}):
            delay = BasePlatformAdapter._get_human_delay()
            assert 0.8 <= delay <= 2.5

    def test_natural_mode_ignores_malformed_custom_env_vars(self):
        env = {
            "HERMES_HUMAN_DELAY_MODE": "natural",
            "HERMES_HUMAN_DELAY_MIN_MS": "oops",
            "HERMES_HUMAN_DELAY_MAX_MS": "still-bad",
        }
        with patch.dict(os.environ, env):
            delay = BasePlatformAdapter._get_human_delay()
            assert 0.8 <= delay <= 2.5

    def test_custom_mode_uses_env_vars(self):
        env = {
            "HERMES_HUMAN_DELAY_MODE": "custom",
            "HERMES_HUMAN_DELAY_MIN_MS": "100",
            "HERMES_HUMAN_DELAY_MAX_MS": "200",
        }
        with patch.dict(os.environ, env):
            delay = BasePlatformAdapter._get_human_delay()
            assert 0.1 <= delay <= 0.2

    def test_custom_mode_tolerates_malformed_env_vars(self):
        env = {
            "HERMES_HUMAN_DELAY_MODE": "custom",
            "HERMES_HUMAN_DELAY_MIN_MS": "oops",
            "HERMES_HUMAN_DELAY_MAX_MS": "still-bad",
        }
        with patch.dict(os.environ, env):
            # falls back to the custom-mode defaults instead of crashing
            delay = BasePlatformAdapter._get_human_delay()
            assert 0.8 <= delay <= 2.5


# ---------------------------------------------------------------------------
# utf16_len / _prefix_within_utf16_limit / truncate_message with len_fn
# ---------------------------------------------------------------------------
# Ported from nearai/ironclaw#2304 — Telegram counts message length in UTF-16
# code units, not Unicode code-points.  Astral-plane characters (emoji, CJK
# Extension B) are surrogate pairs: 1 Python char but 2 UTF-16 units.


class TestUtf16Len:
    """Verify the UTF-16 length helper."""

    def test_ascii(self):
        assert utf16_len("hello") == 5

    def test_bmp_cjk(self):
        # CJK ideographs in the BMP are 1 code unit each
        assert utf16_len("你好") == 2

    def test_emoji_surrogate_pair(self):
        # 😀 (U+1F600) is outside BMP → 2 UTF-16 code units
        assert utf16_len("😀") == 2

    def test_mixed(self):
        # "hi😀" = 2 + 2 = 4 UTF-16 units
        assert utf16_len("hi😀") == 4

    def test_musical_symbol(self):
        # 𝄞 (U+1D11E) — Musical Symbol G Clef, surrogate pair
        assert utf16_len("𝄞") == 2

    def test_empty(self):
        assert utf16_len("") == 0


class TestPrefixWithinUtf16Limit:
    """Verify UTF-16-aware prefix truncation."""

    def test_fits_entirely(self):
        assert _prefix_within_utf16_limit("hello", 10) == "hello"

    def test_ascii_truncation(self):
        result = _prefix_within_utf16_limit("hello world", 5)
        assert result == "hello"
        assert utf16_len(result) <= 5

    def test_does_not_split_surrogate_pair(self):
        # "a😀b" = 1 + 2 + 1 = 4 UTF-16 units; limit 2 should give "a"
        result = _prefix_within_utf16_limit("a😀b", 2)
        assert result == "a"
        assert utf16_len(result) <= 2

    def test_emoji_at_limit(self):
        # "😀" = 2 UTF-16 units; limit 2 should include it
        result = _prefix_within_utf16_limit("😀x", 2)
        assert result == "😀"

    def test_all_emoji(self):
        msg = "😀" * 10  # 20 UTF-16 units
        result = _prefix_within_utf16_limit(msg, 6)
        assert result == "😀😀😀"
        assert utf16_len(result) == 6

    def test_empty(self):
        assert _prefix_within_utf16_limit("", 5) == ""


class TestTruncateMessageUtf16:
    """Verify truncate_message respects UTF-16 lengths when len_fn=utf16_len."""

    def test_short_emoji_message_no_split(self):
        """A short message under the UTF-16 limit should not be split."""
        msg = "Hello 😀 world"
        chunks = BasePlatformAdapter.truncate_message(msg, 4096, len_fn=utf16_len)
        assert len(chunks) == 1
        assert chunks[0] == msg

    def test_emoji_near_limit_triggers_split(self):
        """A message at 4096 codepoints but >4096 UTF-16 units must split."""
        # 2049 emoji = 2049 codepoints but 4098 UTF-16 units → exceeds 4096
        msg = "😀" * 2049
        assert len(msg) == 2049  # Python len sees 2049 chars
        assert utf16_len(msg) == 4098  # but it's 4098 UTF-16 units

        # Without UTF-16 awareness, this would NOT split (2049 < 4096)
        chunks_naive = BasePlatformAdapter.truncate_message(msg, 4096)
        assert len(chunks_naive) == 1, "Without len_fn, no split expected"

        # With UTF-16 awareness, it MUST split
        chunks = BasePlatformAdapter.truncate_message(msg, 4096, len_fn=utf16_len)
        assert len(chunks) > 1, "With utf16_len, message should be split"

        # Each chunk must fit within the UTF-16 limit
        for i, chunk in enumerate(chunks):
            assert utf16_len(chunk) <= 4096, (
                f"Chunk {i} exceeds 4096 UTF-16 units: {utf16_len(chunk)}"
            )

    def test_each_utf16_chunk_within_limit(self):
        """All chunks produced with utf16_len must fit the limit."""
        # Mix of BMP and astral-plane characters
        msg = ("Hello 😀 world 🎵 test 𝄞 " * 200).strip()
        max_len = 200
        chunks = BasePlatformAdapter.truncate_message(msg, max_len, len_fn=utf16_len)
        for i, chunk in enumerate(chunks):
            u16_len = utf16_len(chunk)
            assert u16_len <= max_len + 20, (
                f"Chunk {i} UTF-16 length {u16_len} exceeds {max_len}"
            )

    def test_all_content_preserved(self):
        """Splitting with utf16_len must not lose content."""
        words = ["emoji😀", "music🎵", "cjk你好", "plain"] * 100
        msg = " ".join(words)
        chunks = BasePlatformAdapter.truncate_message(msg, 200, len_fn=utf16_len)
        reassembled = " ".join(chunks)
        for word in words:
            assert word in reassembled, f"Word '{word}' lost during UTF-16 split"

    def test_code_blocks_preserved_with_utf16(self):
        """Code block fence handling should work with utf16_len too."""
        msg = "Before\n```python\n" + "x = '😀'\n" * 200 + "```\nAfter"
        chunks = BasePlatformAdapter.truncate_message(msg, 300, len_fn=utf16_len)
        assert len(chunks) > 1
        # Each chunk should have balanced fences
        for i, chunk in enumerate(chunks):
            fence_count = chunk.count("```")
            assert fence_count % 2 == 0, (
                f"Chunk {i} has unbalanced fences ({fence_count})"
            )


class TestProxyKwargsForAiohttp:
    """Verify proxy_kwargs_for_aiohttp routes all schemes through ProxyConnector."""

    def test_none_returns_empty(self):
        from gateway.platforms.base import proxy_kwargs_for_aiohttp

        sess_kw, req_kw = proxy_kwargs_for_aiohttp(None)
        assert sess_kw == {}
        assert req_kw == {}

    def test_http_proxy_uses_connector_when_aiohttp_socks_available(self):
        pytest.importorskip("aiohttp_socks")
        from unittest.mock import MagicMock
        from gateway.platforms.base import proxy_kwargs_for_aiohttp

        sentinel = MagicMock(name="ProxyConnector")
        with patch("aiohttp_socks.ProxyConnector.from_url", return_value=sentinel):
            sess_kw, req_kw = proxy_kwargs_for_aiohttp("http://proxy:8080")
        assert sess_kw.get("connector") is sentinel, (
            "HTTP proxy must use ProxyConnector so libraries that don't "
            "forward per-request proxy= kwargs still route through the proxy"
        )
        assert req_kw == {}

    def test_socks_proxy_uses_connector(self):
        pytest.importorskip("aiohttp_socks")
        from unittest.mock import MagicMock
        from gateway.platforms.base import proxy_kwargs_for_aiohttp

        sentinel = MagicMock(name="ProxyConnector")
        with patch("aiohttp_socks.ProxyConnector.from_url", return_value=sentinel):
            sess_kw, req_kw = proxy_kwargs_for_aiohttp("socks5://proxy:1080")
        assert sess_kw.get("connector") is sentinel
        assert req_kw == {}

    def test_http_proxy_falls_back_without_aiohttp_socks(self):
        from gateway.platforms.base import proxy_kwargs_for_aiohttp

        with patch.dict("sys.modules", {"aiohttp_socks": None}):
            sess_kw, req_kw = proxy_kwargs_for_aiohttp("http://proxy:8080")
            assert sess_kw == {}
            assert req_kw == {"proxy": "http://proxy:8080"}
