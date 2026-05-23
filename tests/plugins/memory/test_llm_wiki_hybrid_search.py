from types import SimpleNamespace

from hermes_wiki.config import WikiConfig
from hermes_wiki.search import WikiSearch, WikiSearchResult


def _result(page_path, *, score, chunk_index=0, title=None, page_type="concept", text="", tags=None):
    return WikiSearchResult(
        page_path=page_path,
        title=title or page_path.rsplit("/", 1)[-1].removesuffix(".md"),
        page_type=page_type,
        chunk_index=chunk_index,
        text=text,
        score=score,
        tags=tags or [],
    )


class FakeScrollClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.scroll_calls = []

    def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return [SimpleNamespace(payload=payload) for payload in self.payloads], None


class FakeDenseSearch(WikiSearch):
    def __init__(self, dense_results, lexical_payloads):
        self.config = WikiConfig(wiki_name="test")
        self._dense_results = dense_results
        self._client = FakeScrollClient(lexical_payloads)

    def _dense_search(self, query, *, limit, page_type=None, tags=None, exclude_sources=False):
        return self._dense_results[:limit]


def test_literal_tokenizer_is_imported_from_vector_core():
    from vector_core.search import tokenize_literal_query

    from hermes_wiki.search import tokenize_for_sparse_search

    assert tokenize_for_sparse_search is tokenize_literal_query


def test_tokenize_for_sparse_search_keeps_paths_ids_and_acronyms():
    from hermes_wiki.search import tokenize_for_sparse_search

    assert tokenize_for_sparse_search("Exact-Identifier-8B concepts/foo_bar.md GPT-5.5") == [
        "exact",
        "identifier",
        "8b",
        "concepts",
        "foo_bar",
        "md",
        "gpt",
        "5",
        "5",
    ]


def test_reciprocal_rank_fusion_promotes_results_seen_by_both_rankers():
    from hermes_wiki.search import reciprocal_rank_fusion

    dense = [
        _result("concepts/dense-only.md", score=0.99),
        _result("concepts/shared.md", score=0.90),
    ]
    sparse = [
        _result("concepts/shared.md", score=4.0),
        _result("concepts/sparse-only.md", score=3.0),
    ]

    fused = reciprocal_rank_fusion([dense, sparse], limit=3, k=10)

    assert [r.page_path for r in fused] == [
        "concepts/shared.md",
        "concepts/dense-only.md",
        "concepts/sparse-only.md",
    ]
    assert fused[0].score > fused[1].score


def test_sparse_search_scores_literal_query_terms_from_payloads():
    searcher = WikiSearch.__new__(WikiSearch)
    searcher.config = WikiConfig(wiki_name="test")
    searcher._client = FakeScrollClient([
        {
            "page_path": "concepts/random.md",
            "title": "Random",
            "page_type": "concept",
            "chunk_index": 0,
            "text": "semantic discussion without the literal token",
            "tags": [],
        },
        {
            "page_path": "entities/exact-embedding-8b.md",
            "title": "Exact3 Embedding 8B",
            "page_type": "entity",
            "chunk_index": 0,
            "text": "Local embedding endpoint for Exact-Identifier-8B",
            "tags": ["embedding"],
        },
    ])

    results = searcher.sparse_search("Exact-Identifier-8B", limit=2)

    assert [r.page_path for r in results] == ["entities/exact-embedding-8b.md"]
    assert results[0].score > 0
    assert searcher._client.scroll_calls[0]["collection_name"] == "llm_wiki_test"


def test_sparse_search_honors_filters_and_exclude_sources():
    searcher = WikiSearch.__new__(WikiSearch)
    searcher.config = WikiConfig(wiki_name="test")
    searcher._client = FakeScrollClient([
        {
            "page_path": "raw/articles/exact.md",
            "title": "Exact Source",
            "page_type": "source",
            "chunk_index": 0,
            "text": "Exact-Identifier-8B",
            "tags": [],
        },
        {
            "page_path": "entities/exact.md",
            "title": "Exact Entity",
            "page_type": "entity",
            "chunk_index": 0,
            "text": "Exact-Identifier-8B",
            "tags": ["embedding"],
        },
        {
            "page_path": "concepts/exact.md",
            "title": "Exact Concept",
            "page_type": "concept",
            "chunk_index": 0,
            "text": "Exact-Identifier-8B",
            "tags": ["embedding"],
        },
    ])

    results = searcher.sparse_search(
        "Exact-Identifier-8B",
        limit=5,
        page_type="entity",
        tags=["embedding"],
        exclude_sources=True,
    )

    assert [r.page_path for r in results] == ["entities/exact.md"]


def test_hybrid_search_fuses_dense_and_sparse_results():
    searcher = FakeDenseSearch(
        dense_results=[
            _result("concepts/semantic.md", score=0.99),
            _result("entities/exact-embedding-8b.md", score=0.60),
        ],
        lexical_payloads=[
            {
                "page_path": "entities/exact-embedding-8b.md",
                "title": "Exact3 Embedding 8B",
                "page_type": "entity",
                "chunk_index": 0,
                "text": "Exact-Identifier-8B literal config key",
                "tags": ["embedding"],
            },
            {
                "page_path": "concepts/path-only.md",
                "title": "Path Only",
                "page_type": "concept",
                "chunk_index": 0,
                "text": "Exact-Identifier-8B appears here too",
                "tags": [],
            },
        ],
    )

    results = searcher.search("Exact-Identifier-8B", limit=3, search_mode="hybrid")

    assert [r.page_path for r in results] == [
        "entities/exact-embedding-8b.md",
        "concepts/semantic.md",
        "concepts/path-only.md",
    ]


def test_search_defaults_to_dense_mode_for_backward_compatibility():
    searcher = FakeDenseSearch(
        dense_results=[_result("concepts/semantic.md", score=0.99)],
        lexical_payloads=[
            {
                "page_path": "entities/exact-embedding-8b.md",
                "title": "Exact3 Embedding 8B",
                "page_type": "entity",
                "chunk_index": 0,
                "text": "Exact-Identifier-8B",
                "tags": [],
            }
        ],
    )

    results = searcher.search("Exact-Identifier-8B", limit=2)

    assert [r.page_path for r in results] == ["concepts/semantic.md"]
    assert searcher._client.scroll_calls == []


def test_search_supports_sparse_only_mode():
    searcher = FakeDenseSearch(
        dense_results=[_result("concepts/semantic.md", score=0.99)],
        lexical_payloads=[
            {
                "page_path": "entities/exact-embedding-8b.md",
                "title": "Exact3 Embedding 8B",
                "page_type": "entity",
                "chunk_index": 0,
                "text": "Exact-Identifier-8B",
                "tags": [],
            }
        ],
    )

    results = searcher.search("Exact-Identifier-8B", limit=2, search_mode="sparse")

    assert [r.page_path for r in results] == ["entities/exact-embedding-8b.md"]


class AutoSyncSearch(WikiSearch):
    def __init__(self, tmp_path):
        wiki_path = tmp_path / "wiki"
        for subdir in ["concepts", "entities", "comparisons", "queries", "raw/articles"]:
            (wiki_path / subdir).mkdir(parents=True, exist_ok=True)
        self.config = WikiConfig(wiki_path=wiki_path, wiki_name="test")
        self.read_only = False
        self._client = FakeScrollClient([
            {
                "page_path": "concepts/changed.md",
                "content_hash": "old-hash",
                "mtime": 1.0,
                "size": 1,
            },
            {
                "page_path": "concepts/deleted.md",
                "content_hash": "deleted-hash",
                "mtime": 1.0,
                "size": 1,
            },
        ])
        self.indexed_pages = []
        self.indexed_sources = []
        self.deleted_paths = []

    def _ensure_collection(self):
        pass

    def _dense_search(self, query, *, limit, page_type=None, tags=None, exclude_sources=False):
        return [_result("concepts/changed.md", score=0.9)]

    def index_page(self, page_path):
        self.indexed_pages.append(str(page_path.relative_to(self.config.wiki_path)))
        return 1

    def index_source(self, source_path):
        self.indexed_sources.append(str(source_path.relative_to(self.config.wiki_path)))
        return 1

    def _delete_page_chunks(self, rel_path):
        self.deleted_paths.append(rel_path)


def test_search_auto_syncs_incremental_wiki_index_before_retrieval(tmp_path):
    searcher = AutoSyncSearch(tmp_path)
    (searcher.config.wiki_path / "concepts/changed.md").write_text(
        "---\ntitle: Changed\ntype: concept\n---\n\nChanged body", encoding="utf-8"
    )
    (searcher.config.wiki_path / "concepts/new.md").write_text(
        "---\ntitle: New\ntype: concept\n---\n\nNew body", encoding="utf-8"
    )
    (searcher.config.wiki_path / "raw/articles/source.md").write_text(
        "---\ningested: 2026-05-22\n---\n\nSource body", encoding="utf-8"
    )
    for ignored in ["SCHEMA.md", "index.md", "log.md"]:
        (searcher.config.wiki_path / ignored).write_text("ignored", encoding="utf-8")

    results = searcher.search("changed", limit=1)

    assert [result.page_path for result in results] == ["concepts/changed.md"]
    assert searcher.indexed_pages == ["concepts/changed.md", "concepts/new.md"]
    assert searcher.indexed_sources == ["raw/articles/source.md"]
    assert searcher.deleted_paths == ["concepts/deleted.md"]
