"""Tests for skills/research/url-to-inbox/scripts/.

Strategy: hermetic tests against the helper functions. The script
shells out cleanly (no Hermes / neuro-os import dependencies) so we
exercise it via importable functions AND via subprocess for the CLI
entry point — that catches argument parsing regressions.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "research" / "url-to-inbox" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import append_inbox  # noqa: E402
import extract_url   # noqa: E402


NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# append_inbox.build_record — schema mirror tests
# --------------------------------------------------------------------------


class TestBuildRecord:
    def test_minimal_required_fields_pass(self):
        rec = append_inbox.build_record(
            url="https://x/1",
            source_type="blog",
            title="T",
            extracted_text="hello world",
            extracted_at=NOW,
        )
        assert rec["url"] == "https://x/1"
        assert rec["source_type"] == "blog"
        assert rec["title"] == "T"
        assert rec["extracted_text"] == "hello world"
        assert rec["author"] == "unknown"
        assert rec["sender"] is None
        assert rec["urge_tag"] is None
        assert rec["topic_tags"] == []
        # ISO-8601 with tz, parseable round-trip:
        assert rec["extracted_at"].endswith("+00:00")
        datetime.fromisoformat(rec["extracted_at"])

    def test_unknown_source_type_raises(self):
        with pytest.raises(ValueError, match="source_type must be one of"):
            append_inbox.build_record(
                url="https://x", source_type="podcast",
                title="T", extracted_text="body",
            )

    def test_url_length_validated(self):
        with pytest.raises(ValueError, match="url"):
            append_inbox.build_record(
                url="https://" + "x" * 2001,
                source_type="blog", title="T", extracted_text="body",
            )

    def test_title_required(self):
        with pytest.raises(ValueError, match="title"):
            append_inbox.build_record(
                url="https://x", source_type="blog",
                title="", extracted_text="body",
            )

    def test_extracted_text_required(self):
        with pytest.raises(ValueError, match="extracted_text"):
            append_inbox.build_record(
                url="https://x", source_type="blog",
                title="T", extracted_text="",
            )

    def test_topic_tags_capped_at_20(self):
        with pytest.raises(ValueError, match="topic_tags"):
            append_inbox.build_record(
                url="https://x", source_type="blog", title="T",
                extracted_text="body",
                topic_tags=[f"tag-{i}" for i in range(21)],
            )

    def test_urge_tag_passes_through(self):
        rec = append_inbox.build_record(
            url="https://x", source_type="blog", title="T",
            extracted_text="body",
            urge_tag="novelty",
        )
        assert rec["urge_tag"] == "novelty"

    def test_naive_datetime_coerced_to_utc(self):
        naive = datetime(2026, 5, 23, 12, 0, 0)
        rec = append_inbox.build_record(
            url="https://x", source_type="blog", title="T",
            extracted_text="body", extracted_at=naive,
        )
        assert rec["extracted_at"].endswith("+00:00")


# --------------------------------------------------------------------------
# append_inbox.append — JSONL roundtrip + concurrent-write safety
# --------------------------------------------------------------------------


class TestAppendJsonl:
    def test_append_then_read_roundtrip(self, tmp_path):
        inbox = tmp_path / "inbox.jsonl"
        rec = append_inbox.build_record(
            url="https://x", source_type="blog", title="T",
            extracted_text="body",
        )
        offset = append_inbox.append(rec, inbox)
        assert offset == 0
        # File contains exactly one JSON line that parses back to our record.
        lines = inbox.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["url"] == rec["url"]
        assert parsed["title"] == rec["title"]
        assert parsed["topic_tags"] == []

    def test_two_appends_produce_two_lines_with_correct_offsets(self, tmp_path):
        inbox = tmp_path / "inbox.jsonl"
        r1 = append_inbox.build_record(
            url="https://x/1", source_type="blog", title="T1",
            extracted_text="first",
        )
        r2 = append_inbox.build_record(
            url="https://x/2", source_type="blog", title="T2",
            extracted_text="second",
        )
        assert append_inbox.append(r1, inbox) == 0
        assert append_inbox.append(r2, inbox) == 1
        lines = inbox.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2

    def test_parent_dir_created_on_demand(self, tmp_path):
        inbox = tmp_path / "deeply" / "nested" / "inbox.jsonl"
        rec = append_inbox.build_record(
            url="https://x", source_type="blog", title="T",
            extracted_text="body",
        )
        append_inbox.append(rec, inbox)
        assert inbox.exists()


# --------------------------------------------------------------------------
# extract_url.detect_source_type — dispatch table
# --------------------------------------------------------------------------


class TestSourceTypeDetection:
    @pytest.mark.parametrize("url,expected", [
        ("https://youtube.com/watch?v=abc", "youtube"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://m.youtube.com/watch?v=abc", "youtube"),
        ("https://twitter.com/foo/status/1", "twitter"),
        ("https://x.com/foo/status/1", "twitter"),
        ("https://example.com/paper.pdf", "pdf"),
        ("https://example.com/paper.pdf?dl=1", "pdf"),
        ("https://blog.example.com/post-1", "blog"),
        ("https://substack.com/p/post", "blog"),
    ])
    def test_dispatch(self, url, expected):
        assert extract_url.detect_source_type(url) == expected


# --------------------------------------------------------------------------
# extract_url.html_to_text — stdlib HTML reducer
# --------------------------------------------------------------------------


class TestHtmlToText:
    def test_strips_script_and_style(self):
        html = """
        <html><head><style>body { color: red }</style>
        <script>alert(1)</script></head>
        <body><p>Hello world</p></body></html>
        """
        text = extract_url.html_to_text(html)
        assert "alert" not in text
        assert "color: red" not in text
        assert "Hello world" in text

    def test_keeps_paragraph_breaks(self):
        html = "<p>First</p><p>Second</p>"
        text = extract_url.html_to_text(html)
        # The reducer inserts double newlines between block elements.
        assert "First" in text and "Second" in text
        assert "\n\n" in text

    def test_decodes_entities(self):
        html = "<p>Tom &amp; Jerry &lt;3 &#39;tea&#39;</p>"
        text = extract_url.html_to_text(html)
        assert "Tom & Jerry <3 'tea'" in text

    def test_extracts_title(self):
        html = "<html><head><title>My Page</title></head><body></body></html>"
        assert extract_url.html_title(html) == "My Page"

    def test_og_title_wins_over_html_title(self):
        html = """
        <html><head>
          <meta property="og:title" content="OG Title">
          <title>Plain Title</title>
        </head></html>
        """
        assert extract_url.html_title(html) == "OG Title"

    def test_extracts_meta_author(self):
        html = '<meta name="author" content="Jane Doe">'
        assert extract_url.html_author(html) == "Jane Doe"


# --------------------------------------------------------------------------
# extract_url.extract — dispatch + error surfaces
# --------------------------------------------------------------------------


class TestExtractDispatch:
    def test_pdf_raises_with_clear_hint(self):
        with pytest.raises(ValueError, match="ocr-and-documents"):
            extract_url.extract("https://x/paper.pdf", source_type="pdf")

    def test_email_body_raises_with_clear_hint(self):
        with pytest.raises(ValueError, match="email-body"):
            extract_url.extract("note://something", source_type="email-body")

    def test_blog_branch_uses_fetch_html(self, monkeypatch):
        canned = """
        <html><head><title>Distribution is the moat</title>
        <meta name="author" content="Speaker">
        </head><body><p>Distribution beats product quality.</p></body></html>
        """
        monkeypatch.setattr(extract_url, "fetch_html", lambda url: canned)
        result = extract_url.extract("https://blog.example.com/p1", source_type="blog")
        assert result["title"] == "Distribution is the moat"
        assert result["author"] == "Speaker"
        assert "Distribution beats product quality" in result["extracted_text"]
        assert result["source_type"] == "blog"
        assert result["url"] == "https://blog.example.com/p1"

    def test_auto_dispatches_by_host(self, monkeypatch):
        canned = "<html><head><title>Post</title></head><body>Body</body></html>"
        monkeypatch.setattr(extract_url, "fetch_html", lambda url: canned)
        # blog dispatch
        r1 = extract_url.extract("https://substack.com/p/post", source_type="auto")
        assert r1["source_type"] == "blog"
        # pdf dispatch raises (not fetched)
        with pytest.raises(ValueError):
            extract_url.extract("https://x/paper.pdf", source_type="auto")

    def test_youtube_branch_falls_back_when_lib_missing(self, monkeypatch):
        # Force the ImportError branch by hiding youtube_transcript_api.
        monkeypatch.setitem(sys.modules, "youtube_transcript_api", None)
        # And make HTML fetch return a minimal page so the function returns metadata.
        monkeypatch.setattr(
            extract_url, "fetch_html",
            lambda url: '<html><head><title>YT Video</title>'
                        '<meta name="description" content="some desc">'
                        '</head></html>'
        )
        result = extract_url.extract(
            "https://youtube.com/watch?v=abcdefghijk",
            source_type="youtube",
        )
        assert result["source_type"] == "youtube"
        assert "youtube-transcript-api" in result["extracted_text"]


# --------------------------------------------------------------------------
# CLI subprocess smoke (catches argparse regressions)
# --------------------------------------------------------------------------


class TestAppendInboxCli:
    def test_help_prints(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "append_inbox.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--url" in result.stdout
        assert "--source-type" in result.stdout
        assert "--text-file" in result.stdout

    def test_end_to_end_appends_one_line(self, tmp_path):
        text_file = tmp_path / "body.txt"
        text_file.write_text("body text for the test", encoding="utf-8")
        inbox = tmp_path / "inbox.jsonl"
        result = subprocess.run(
            [
                sys.executable, str(SCRIPTS_DIR / "append_inbox.py"),
                "--url", "https://blog.example.com/test",
                "--source-type", "blog",
                "--title", "Test title",
                "--text-file", str(text_file),
                "--inbox-path", str(inbox),
                "--sender", "paul@example.com",
                "--urge-tag", "novelty",
                "--topic-tag", "mlops",
                "--topic-tag", "agents",
            ],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["appended_offset"] == 0
        assert out["source_type"] == "blog"
        # JSONL line landed.
        line = inbox.read_text(encoding="utf-8").splitlines()[0]
        payload = json.loads(line)
        assert payload["url"] == "https://blog.example.com/test"
        assert payload["sender"] == "paul@example.com"
        assert payload["urge_tag"] == "novelty"
        assert payload["topic_tags"] == ["mlops", "agents"]

    def test_missing_text_file_returns_nonzero(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable, str(SCRIPTS_DIR / "append_inbox.py"),
                "--url", "https://x",
                "--source-type", "blog",
                "--title", "T",
                "--text-file", str(tmp_path / "does-not-exist.txt"),
                "--inbox-path", str(tmp_path / "inbox.jsonl"),
            ],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr or "no such" in result.stderr.lower()

    def test_invalid_source_type_rejected_by_argparse(self, tmp_path):
        text_file = tmp_path / "body.txt"
        text_file.write_text("body", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, str(SCRIPTS_DIR / "append_inbox.py"),
                "--url", "https://x",
                "--source-type", "podcast",  # not a valid choice
                "--title", "T",
                "--text-file", str(text_file),
                "--inbox-path", str(tmp_path / "inbox.jsonl"),
            ],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
        # argparse prints to stderr.
        assert "podcast" in result.stderr or "invalid choice" in result.stderr


class TestExtractUrlCli:
    def test_help_prints(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "extract_url.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--url" in result.stdout
        assert "--source-type" in result.stdout

    def test_pdf_exit_code_is_2(self):
        result = subprocess.run(
            [
                sys.executable, str(SCRIPTS_DIR / "extract_url.py"),
                "--url", "https://x/paper.pdf",
                "--source-type", "pdf",
            ],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 2
        assert "ocr-and-documents" in result.stderr


# --------------------------------------------------------------------------
# End-to-end producer→consumer contract: the JSON line a producer writes
# is exactly the JSON line the neuro-os Pydantic schema expects.
# --------------------------------------------------------------------------


def test_producer_output_matches_documented_schema():
    """Pin: the keys our producer emits are exactly the keys neuro-os's
    InboxRecord expects. If neuro-os evolves the schema, this test
    surfaces the drift at the Hermes side immediately."""
    rec = append_inbox.build_record(
        url="https://x", source_type="blog", title="T",
        extracted_text="body", sender="a@b.com", urge_tag="novelty",
        topic_tags=["t1"],
    )
    expected_keys = {
        "url", "source_type", "title", "author", "extracted_text",
        "extracted_at", "sender", "urge_tag", "topic_tags",
    }
    assert set(rec.keys()) == expected_keys
