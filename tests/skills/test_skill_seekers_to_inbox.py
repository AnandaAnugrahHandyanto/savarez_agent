"""Tests for skills/research/skill-seekers-to-inbox/scripts/flush_references.py.

Strategy: build a fake ``references/`` directory mimicking skill-seekers'
output (a mix of front-matter + plain markdown), then drive the
``flush`` function against it and assert on the inbox JSONL.

We don't shell out to skill-seekers itself — it's a heavy dependency
(network, optional API key) — and that boundary is already covered by
skill-seekers's own 3194+ tests.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "research" / "skill-seekers-to-inbox"
SCRIPTS_DIR = SKILL_ROOT / "scripts"

# Add the SIBLING url-to-inbox scripts to sys.path FIRST so the
# bridge's `import append_inbox` resolves.
SIBLING = SKILL_ROOT.parent / "url-to-inbox" / "scripts"
sys.path.insert(0, str(SIBLING))
sys.path.insert(0, str(SCRIPTS_DIR))

# Now import the module under test. We use importlib so that re-running
# the test file in the same session picks up edits.
flush_module = importlib.import_module("flush_references")


NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)


def _make_fake_seeker_output(root: Path) -> Path:
    """Build a directory that mimics ``skill-seekers create --output ...``:

        root/
          SKILL.md                  ← wrapper, ignored
          references/
            index.md                ← skipped (navigation file)
            section_01.md           ← full front-matter + body
            section_02.md           ← no front-matter, has H1
            section_03.md           ← no front-matter, no H1
            empty.md                ← empty body → skipped
    """
    refs = root / "references"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_text("# wrapper\n", encoding="utf-8")
    (refs / "index.md").write_text("# Index\n- section_01\n", encoding="utf-8")
    (refs / "section_01.md").write_text(
        "---\n"
        "source_url: https://docs.example.com/getting-started\n"
        "title: Getting Started\n"
        "author: Docs Team\n"
        "---\n"
        "# Getting Started\n\n"
        "Install with pip. Then run it.\n",
        encoding="utf-8",
    )
    (refs / "section_02.md").write_text(
        "# Advanced Configuration\n\n"
        "Configure foo. Then bar.\n",
        encoding="utf-8",
    )
    (refs / "section_03.md").write_text(
        "Plain prose with no heading at all. Just some body text.\n",
        encoding="utf-8",
    )
    (refs / "empty.md").write_text("\n   \n", encoding="utf-8")
    return refs


# --------------------------------------------------------------------------
# Front-matter parsing
# --------------------------------------------------------------------------


class TestFrontMatter:
    def test_parses_clean_front_matter(self):
        text = (
            "---\n"
            "title: Hello\n"
            "source_url: https://x.com/a\n"
            "---\n"
            "body content"
        )
        meta, body = flush_module._parse_front_matter(text)
        assert meta == {"title": "Hello", "source_url": "https://x.com/a"}
        assert body == "body content"

    def test_no_front_matter_passes_through(self):
        text = "just body"
        meta, body = flush_module._parse_front_matter(text)
        assert meta == {}
        assert body == "just body"

    def test_strips_quotes_in_values(self):
        text = '---\ntitle: "Quoted Title"\n---\nbody'
        meta, _ = flush_module._parse_front_matter(text)
        assert meta["title"] == "Quoted Title"


class TestDeriveUrl:
    def test_front_matter_source_url_wins(self):
        url = flush_module._derive_url(
            {"source_url": "https://x.com/page", "url": "https://y.com/other"},
            "https://base.example.com",
            "section_01.md",
        )
        assert url == "https://x.com/page"

    def test_fallback_to_base_url_plus_slug(self):
        url = flush_module._derive_url({}, "https://docs.example.com", "getting-started.md")
        assert url == "https://docs.example.com/getting-started"

    def test_final_fallback_is_synthetic_scheme(self):
        url = flush_module._derive_url({}, None, "loose-file.md")
        assert url == "skill-seekers://loose-file.md"


class TestDeriveTitle:
    def test_front_matter_title_wins(self):
        t = flush_module._derive_title({"title": "FM Title"}, "foo.md", "# Body Heading")
        assert t == "FM Title"

    def test_fallback_to_first_h1(self):
        t = flush_module._derive_title({}, "foo.md", "intro\n# Real Title\n\nbody")
        assert t == "Real Title"

    def test_fallback_to_humanized_filename(self):
        t = flush_module._derive_title({}, "advanced-configuration.md", "no heading")
        assert t == "Advanced Configuration"


# --------------------------------------------------------------------------
# End-to-end flush against a faked skill-seekers output
# --------------------------------------------------------------------------


class TestFlushEndToEnd:
    def test_appends_one_record_per_md_skipping_index_and_empty(self, tmp_path):
        refs = _make_fake_seeker_output(tmp_path / "seeker-out")
        inbox = tmp_path / "inbox.jsonl"

        summary = flush_module.flush(
            references_dir=refs,
            base_url="https://docs.example.com",
            inbox_path=inbox,
            source_type="blog",
            sender="paul@example.com",
            urge_tag="novelty",
            topic_tags=["docs", "import"],
            now=NOW,
        )

        # index.md skipped, empty.md skipped (empty body), 3 content files attempted.
        assert summary["records_attempted"] == 4  # section_01, _02, _03, empty
        # empty.md gets caught as "schema" skip OR "empty body" skip (we check both).
        assert summary["records_appended"] == 3
        assert any(
            s["file"] == "empty.md" for s in summary["records_skipped"]
        )
        assert summary["errors"] == []

        # Inbox file has exactly 3 lines.
        lines = inbox.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        records = [json.loads(line) for line in lines]
        urls = {r["url"] for r in records}
        titles = {r["title"] for r in records}

        # section_01 had explicit front-matter url + title:
        assert "https://docs.example.com/getting-started" in urls
        assert "Getting Started" in titles
        # section_02 had no front-matter — title from H1, url from base_url + slug:
        assert "Advanced Configuration" in titles
        assert "https://docs.example.com/section_02" in urls
        # section_03 had no front-matter and no H1 — title humanized from filename:
        assert "Section 03" in titles or "Section_03" in titles

        # Every record carries the bridge's metadata.
        for r in records:
            assert r["sender"] == "paul@example.com"
            assert r["urge_tag"] == "novelty"
            assert r["topic_tags"] == ["docs", "import"]
            assert r["source_type"] == "blog"

    def test_dry_run_does_not_write_inbox(self, tmp_path):
        refs = _make_fake_seeker_output(tmp_path / "seeker-out")
        inbox = tmp_path / "inbox.jsonl"

        summary = flush_module.flush(
            references_dir=refs,
            base_url="https://docs.example.com",
            inbox_path=inbox,
            dry_run=True,
            now=NOW,
        )

        assert summary["dry_run"] is True
        assert summary["records_appended"] == 3   # WOULD have been
        assert not inbox.exists()  # NO writes happened

    def test_max_records_caps_processing(self, tmp_path):
        refs = _make_fake_seeker_output(tmp_path / "seeker-out")
        inbox = tmp_path / "inbox.jsonl"

        summary = flush_module.flush(
            references_dir=refs,
            base_url=None,
            inbox_path=inbox,
            max_records=2,
            now=NOW,
        )

        assert summary["records_attempted"] == 2  # cap honored
        # And at most 2 records appear in inbox.
        if inbox.exists():
            lines = inbox.read_text(encoding="utf-8").splitlines()
            assert len(lines) <= 2

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            flush_module.flush(
                references_dir=tmp_path / "does-not-exist",
                base_url=None,
                inbox_path=tmp_path / "inbox.jsonl",
            )

    def test_uses_sibling_append_inbox_schema(self, tmp_path):
        """Sanity check that our records match what the url-to-inbox
        sibling validates against. If neuro-os ever evolves the
        InboxRecord schema, this test will fail at the bridge layer
        too."""
        refs = _make_fake_seeker_output(tmp_path / "seeker-out")
        inbox = tmp_path / "inbox.jsonl"
        summary = flush_module.flush(
            references_dir=refs,
            base_url="https://docs.example.com",
            inbox_path=inbox,
            now=NOW,
        )
        assert summary["records_appended"] >= 1
        line = inbox.read_text(encoding="utf-8").splitlines()[0]
        rec = json.loads(line)
        expected_keys = {
            "url", "source_type", "title", "author", "extracted_text",
            "extracted_at", "sender", "urge_tag", "topic_tags",
        }
        assert set(rec.keys()) == expected_keys
