"""Regression tests for raw source hashing during ingest/lint."""

from __future__ import annotations

from hermes_wiki.config import WikiConfig
from hermes_wiki.engine import WikiEngine


class DummyLLM:
    def analyze_source(self, **kwargs):
        return {"entities": [], "concepts": [], "key_facts": []}


class DummyIndexer:
    def __init__(self, config):
        self.config = config

    def list_entity_slugs(self):
        return []

    def list_concept_slugs(self):
        return []

    def list_all_slugs(self):
        return []

    def get_all_pages(self):
        return {}

    def list_sources(self):
        return [{"path": "raw/articles/example-source.md"}]

    def read_index(self):
        return ""

    def append_log(self, *args, **kwargs):
        return None


class DummySearch:
    def search(self, *args, **kwargs):
        return []

    def collection_stats(self):
        return {"points": 0}

    def index_page(self, *args, **kwargs):
        return 0

    def index_source(self, *args, **kwargs):
        return 0


def _engine(tmp_path):
    engine = WikiEngine.__new__(WikiEngine)
    engine.config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    engine.llm = DummyLLM()
    engine.indexer = DummyIndexer(engine.config)
    engine.search = DummySearch()
    engine.read_only = False
    return engine


def test_ingested_raw_source_hash_matches_lint_body_hash(tmp_path):
    engine = _engine(tmp_path)

    engine.ingest_text("# Example Source\n\nBody text.\n", "Example Source", dry_run=False)
    report = engine.lint(write_log=False)

    assert not [issue for issue in report.issues if issue.category == "source_drift"]
