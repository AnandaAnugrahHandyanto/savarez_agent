import json
import math
from types import SimpleNamespace

import pytest

from hermes_wiki.search import WikiSearchResult


class FakeSearcher:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, limit=5, **kwargs):
        self.calls.append({"query": query, "limit": limit, **kwargs})
        return self.results[:limit]


def _hit(page_path, *, score=0.5, chunk_index=0, page_type="concept", title=None, text="body text"):
    return WikiSearchResult(
        page_path=page_path,
        title=title or page_path.rsplit("/", 1)[-1].removesuffix(".md"),
        page_type=page_type,
        chunk_index=chunk_index,
        text=text,
        score=score,
        tags=["memory"],
    )


def test_introspection_config_loader_rejects_nonscalar_path():
    from hermes_wiki.retrieval_introspection import _load_explicit_wiki_config

    with pytest.raises(ValueError, match="config_path"):
        _load_explicit_wiki_config({"path": "config.yaml"})  # type: ignore[arg-type]


def test_introspect_retrieval_reports_ranked_chunks_and_page_coverage():
    from hermes_wiki.retrieval_introspection import introspect_retrieval, introspection_to_dict

    searcher = FakeSearcher([
        _hit("concepts/memory.md", score=0.91, chunk_index=0, text="First memory chunk"),
        _hit("concepts/memory.md", score=0.83, chunk_index=1, text="Second memory chunk"),
        _hit("entities/hermes.md", score=0.77, page_type="entity", text="Hermes entity chunk"),
    ])

    report = introspect_retrieval(
        searcher,
        "How should Hermes use memory?",
        top_k=3,
        expected_pages={"concepts/memory.md", "entities/missing.md"},
    )
    data = introspection_to_dict(report)

    assert searcher.calls == [{"query": "How should Hermes use memory?", "limit": 3}]
    assert data["query"] == "How should Hermes use memory?"
    assert data["search_mode"] == "dense"
    assert data["top_k"] == 3
    assert [hit["rank"] for hit in data["hits"]] == [1, 2, 3]
    assert data["hits"][0] == {
        "rank": 1,
        "page_path": "concepts/memory.md",
        "title": "memory",
        "page_type": "concept",
        "chunk_index": 0,
        "score": 0.91,
        "tags": ["memory"],
        "text_preview": "First memory chunk",
    }
    assert data["pages"] == [
        {"page_path": "concepts/memory.md", "best_rank": 1, "best_score": 0.91, "hit_count": 2},
        {"page_path": "entities/hermes.md", "best_rank": 3, "best_score": 0.77, "hit_count": 1},
    ]
    assert data["expected_pages"] == ["concepts/memory.md", "entities/missing.md"]
    assert data["missing_expected_pages"] == ["entities/missing.md"]
    assert not data["passed_expected_pages"]


def test_introspection_serializes_non_finite_scores_as_null():
    from hermes_wiki.retrieval_introspection import introspect_retrieval, introspection_to_dict

    report = introspect_retrieval(
        FakeSearcher([
            SimpleNamespace(
                page_path="concepts/nan.md",
                title="nan",
                page_type="concept",
                chunk_index=0,
                text="body",
                score=math.nan,
                tags=["memory"],
            ),
            SimpleNamespace(
                page_path="concepts/inf.md",
                title="inf",
                page_type="concept",
                chunk_index=0,
                text="body",
                score=math.inf,
                tags=["memory"],
            ),
            SimpleNamespace(
                page_path="concepts/neg-inf.md",
                title="neg-inf",
                page_type="concept",
                chunk_index=0,
                text="body",
                score=-math.inf,
                tags=["memory"],
            ),
        ]),
        "score query",
        top_k=3,
    )
    data = introspection_to_dict(report)

    assert [hit["score"] for hit in data["hits"]] == [None, None, None]
    assert [page["best_score"] for page in data["pages"]] == [None, None, None]
    json.dumps(data, allow_nan=False)


def test_introspect_retrieval_passes_page_type_and_exclude_source_filters():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    searcher = FakeSearcher([_hit("entities/hermes.md", page_type="entity")])

    introspect_retrieval(
        searcher,
        "Hermes",
        top_k=1,
        page_type="entity",
        exclude_sources=True,
        search_mode="hybrid",
    )

    assert searcher.calls == [
        {"query": "Hermes", "limit": 1, "page_type": "entity", "exclude_sources": True, "search_mode": "hybrid"}
    ]


def test_introspect_retrieval_clamps_top_k_to_bounded_range():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    searcher = FakeSearcher([_hit(f"concepts/{idx}.md") for idx in range(30)])
    report = introspect_retrieval(searcher, "memory", top_k=999999)

    assert searcher.calls[0] == {"query": "memory", "limit": 20}
    assert report.top_k == 20


def test_introspect_retrieval_rejects_invalid_top_k():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    for top_k in (math.inf, math.nan, 2.5, "2.5", {"limit": 2}, True):
        with pytest.raises(ValueError, match="top_k"):
            introspect_retrieval(FakeSearcher([]), "memory", top_k=top_k)  # type: ignore[arg-type]


def test_introspect_retrieval_rejects_unsafe_expected_pages():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    with pytest.raises(ValueError, match="expected_pages"):
        introspect_retrieval(FakeSearcher([]), "query", expected_pages={"../secrets.md"})


def test_introspect_retrieval_rejects_nonscalar_expected_pages():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    for expected_pages in ({}, {"concepts/ok.md", ("concepts/nested.md",)}, {"concepts/ok.md", 42}):
        with pytest.raises(ValueError, match="expected_pages"):
            introspect_retrieval(FakeSearcher([]), "query", expected_pages=expected_pages)  # type: ignore[arg-type]


def test_introspect_retrieval_rejects_nonscalar_query_and_search_mode():
    from hermes_wiki.retrieval_introspection import introspect_retrieval

    with pytest.raises(ValueError, match="query"):
        introspect_retrieval(FakeSearcher([]), {"text": "query"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="search_mode"):
        introspect_retrieval(FakeSearcher([]), "query", search_mode={"mode": "dense"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="page_type"):
        introspect_retrieval(FakeSearcher([]), "query", page_type={"type": "concept"})  # type: ignore[arg-type]


def test_retrieval_introspection_rejects_nonbool_exclude_sources():
    from hermes_wiki.retrieval_introspection import (
        compare_retrieval_introspection,
        introspect_retrieval,
    )

    for exclude_sources in ({"enabled": True}, [True], "false", 1):
        with pytest.raises(ValueError, match="exclude_sources"):
            introspect_retrieval(FakeSearcher([]), "query", exclude_sources=exclude_sources)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="exclude_sources"):
            compare_retrieval_introspection(FakeSearcher([]), "query", exclude_sources=exclude_sources)  # type: ignore[arg-type]


def test_introspect_retrieval_normalizes_malformed_hit_fields():
    from types import SimpleNamespace

    from hermes_wiki.retrieval_introspection import introspect_retrieval, introspection_to_dict

    report = introspect_retrieval(
        FakeSearcher([
            SimpleNamespace(
                page_path="concepts/malformed.md",
                title={"bad": "title"},
                page_type=["concept"],
                chunk_index=2.5,
                score=float("nan"),
                tags="not-a-list",
                text={"body": "bad"},
            )
        ]),
        "query",
        expected_pages={"concepts/malformed.md"},
    )
    payload = introspection_to_dict(report)

    assert payload["hits"][0]["page_path"] == "concepts/malformed.md"
    assert payload["hits"][0]["title"] == ""
    assert payload["hits"][0]["page_type"] == ""
    assert payload["hits"][0]["chunk_index"] == 0
    assert payload["hits"][0]["score"] is None
    assert payload["hits"][0]["tags"] == ["not-a-list"]
    assert payload["hits"][0]["text_preview"] == ""


def test_render_introspection_markdown_is_agent_readable():
    from hermes_wiki.retrieval_introspection import (
        introspect_retrieval,
        render_introspection_markdown,
    )

    report = introspect_retrieval(
        FakeSearcher([_hit("concepts/memory.md", score=0.91, text="A" * 300)]),
        "memory query",
        expected_pages={"concepts/memory.md"},
    )

    markdown = render_introspection_markdown(report)

    assert "# LLM Wiki Retrieval Introspection" in markdown
    assert "Query: `memory query`" in markdown
    assert "- ✅ Expected page coverage passed" in markdown
    assert "| 1 | `concepts/memory.md` | 0.91 | concept | 0 |" in markdown
    assert "A" * 220 not in markdown


def test_cli_json_uses_explicit_config_and_prints_stable_shape(tmp_path, monkeypatch, capsys):
    from hermes_wiki import retrieval_introspection

    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    class FakeWikiSearch:
        def __init__(self, config, ensure_collection=False):
            self.config = config
            self.ensure_collection = ensure_collection

        def search(self, query, limit=5, **kwargs):
            return [_hit("concepts/memory.md", score=0.99)]

    monkeypatch.setattr(retrieval_introspection, "WikiSearch", FakeWikiSearch)

    rc = retrieval_introspection.main([
        "memory query",
        "--config",
        str(config_path),
        "--expected-page",
        "concepts/memory.md",
        "--json",
    ])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["query"] == "memory query"
    assert out["hits"][0]["page_path"] == "concepts/memory.md"
    assert out["passed_expected_pages"] is True


def test_cli_returns_nonzero_when_expected_pages_are_missing(tmp_path, monkeypatch, capsys):
    from hermes_wiki import retrieval_introspection

    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"wiki:\n  path: {tmp_path / 'wiki'}\n  name: test\n", encoding="utf-8")

    class FakeWikiSearch:
        def __init__(self, config, ensure_collection=False):
            pass

        def search(self, query, limit=5, **kwargs):
            return [_hit("entities/hermes.md")]

    monkeypatch.setattr(retrieval_introspection, "WikiSearch", FakeWikiSearch)

    rc = retrieval_introspection.main([
        "memory query",
        "--config",
        str(config_path),
        "--expected-page",
        "concepts/missing.md",
        "--json",
    ])
    out = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert out["missing_expected_pages"] == ["concepts/missing.md"]


def test_cli_requires_explicit_config_when_requested_path_is_missing(tmp_path):
    from hermes_wiki.retrieval_introspection import main

    with pytest.raises(SystemExit):
        main(["query", "--config", str(tmp_path / "missing.yaml")])


def test_compare_retrieval_introspection_summarizes_modes():
    from hermes_wiki.retrieval_introspection import compare_retrieval_introspection

    class ModeAwareSearcher:
        def __init__(self):
            self.calls = []

        def search(self, query, limit=5, **kwargs):
            self.calls.append({"query": query, "limit": limit, **kwargs})
            if kwargs.get("search_mode") == "sparse":
                return [_hit("concepts/noise.md")]
            return [_hit("concepts/memory.md")]

    searcher = ModeAwareSearcher()
    payload = compare_retrieval_introspection(
        searcher,
        "memory query",
        top_k=2,
        expected_pages={"concepts/memory.md"},
    )

    assert payload["passed"] is False
    assert payload["failed_modes"] == ["sparse"]
    assert payload["summary"] == {
        "dense": {"passed_expected_pages": True, "missing_expected_pages": []},
        "sparse": {"passed_expected_pages": False, "missing_expected_pages": ["concepts/memory.md"]},
        "hybrid": {"passed_expected_pages": True, "missing_expected_pages": []},
    }
    assert searcher.calls == [
        {"query": "memory query", "limit": 2},
        {"query": "memory query", "limit": 2, "search_mode": "sparse"},
        {"query": "memory query", "limit": 2, "search_mode": "hybrid"},
    ]


def test_cli_compare_modes_json_outputs_summary(tmp_path, monkeypatch, capsys):
    from hermes_wiki import retrieval_introspection

    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"wiki:\n  path: {tmp_path / 'wiki'}\n  name: test\n", encoding="utf-8")

    class FakeWikiSearch:
        def __init__(self, config, ensure_collection=False):
            pass

        def search(self, query, limit=5, **kwargs):
            if kwargs.get("search_mode") == "sparse":
                return [_hit("concepts/noise.md")]
            return [_hit("concepts/memory.md")]

    monkeypatch.setattr(retrieval_introspection, "WikiSearch", FakeWikiSearch)

    rc = retrieval_introspection.main([
        "memory query",
        "--config",
        str(config_path),
        "--expected-page",
        "concepts/memory.md",
        "--compare-modes",
        "--json",
    ])
    out = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert out["failed_modes"] == ["sparse"]
    assert out["modes"]["hybrid"]["passed_expected_pages"] is True


def test_cli_compare_modes_rejects_search_mode(tmp_path):
    from hermes_wiki.retrieval_introspection import main

    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"wiki:\n  path: {tmp_path / 'wiki'}\n  name: test\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        main([
            "memory query",
            "--config",
            str(config_path),
            "--compare-modes",
            "--search-mode",
            "hybrid",
        ])
