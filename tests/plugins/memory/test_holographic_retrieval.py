"""Regression tests for the holographic FactRetriever.

Pinned bugs:

* hermes-web-ui#395 — FTS5 ``unicode61`` tokenizer collapses runs of CJK
  characters into a single token, so substring queries like ``浅瀬記憶``
  silently return zero candidates against text like ``浅瀬記憶のメモ``.
  ``_fts_candidates`` now detects CJK in the query and falls back to a
  ``LIKE`` scan, and ``_tokenize`` emits CJK character bigrams so the
  Jaccard rerank stage actually scores overlap.
"""

from __future__ import annotations

import pytest

from plugins.memory.holographic.retrieval import (
    FactRetriever,
    _CJK_RE,
    _escape_like,
    _split_query_terms,
)
from plugins.memory.holographic.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(db_path=str(tmp_path / "test.db"))
    yield s
    s._conn.close()


@pytest.fixture
def populated_store(store):
    # Mix of English and CJK content. Trust scores tweaked so we can verify
    # ordering downstream of the Jaccard rerank.
    facts = [
        "hello world memory tool",
        "about 承認フロー approval flow at the office",
        "浅瀬記憶のメモ",
        "英語の memory についての日本語",
        "购物清单：买苹果和橙子",  # zh-CN: shopping list
        "한국어 메모리 시스템",  # ko: korean memory system
    ]
    for content in facts:
        store.add_fact(content, category="general", tags="")
    return store


# ---------------------------------------------------------------------------
# CJK detection helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("memory tool", False),
        ("memory_tool", False),
        ("español", False),
        ("foo bar baz", False),
        ("承認フロー", True),
        ("浅瀬記憶", True),
        ("about 承認フロー", True),  # mixed
        ("日本語", True),
        ("한국어 메모리", True),
        ("购物清单", True),
        ("ｶﾀｶﾅ", True),  # halfwidth katakana
    ],
)
def test_cjk_re_detects(query, expected):
    assert bool(_CJK_RE.search(query)) is expected


def test_split_query_terms_basic():
    assert _split_query_terms("Memory Tool") == ["memory", "tool"]
    assert _split_query_terms("foo, bar; baz!") == ["foo", "bar", "baz"]


def test_split_query_terms_keeps_cjk_intact():
    # CJK terms must survive the splitter unchanged so the LIKE pattern
    # matches the in-store substring directly.
    assert _split_query_terms("承認フロー approval") == ["承認フロー", "approval"]


def test_escape_like_neutralizes_metacharacters():
    assert _escape_like("50%_off") == r"50\%\_off"
    assert _escape_like("a\\b") == r"a\\b"
    # No metachars: unchanged.
    assert _escape_like("hello") == "hello"


# ---------------------------------------------------------------------------
# Jaccard tokenizer — CJK bigrams
# ---------------------------------------------------------------------------


def test_tokenize_ascii_unchanged():
    # Existing behaviour for English / Latin content must not regress.
    assert FactRetriever._tokenize("Hello, World!") == {"hello", "world"}


def test_tokenize_emits_cjk_bigrams():
    tokens = FactRetriever._tokenize("浅瀬記憶")
    # Whole word + the three character bigrams.
    assert "浅瀬記憶" in tokens
    assert "浅瀬" in tokens
    assert "瀬記" in tokens
    assert "記憶" in tokens


def test_tokenize_cjk_overlap_drives_jaccard():
    # The crux of the rerank fix: a CJK query and a stored sentence that
    # contains it as a substring share at least one bigram.
    q = FactRetriever._tokenize("承認フロー")
    doc = FactRetriever._tokenize("承認フローについて議論")
    assert q & doc, "expected overlapping CJK bigrams"


def test_tokenize_handles_mixed_runs():
    # Words that mix CJK with ASCII still emit bigrams from the CJK span only.
    tokens = FactRetriever._tokenize("foo承認認可bar")
    assert "承認" in tokens
    assert "認認" in tokens
    assert "認可" in tokens
    # Original word is preserved too.
    assert "foo承認認可bar" in tokens


# ---------------------------------------------------------------------------
# End-to-end retrieval — the user-visible bug
# ---------------------------------------------------------------------------


def test_english_query_still_works(populated_store):
    """Regression guard: ASCII queries must still reach the FTS5 path."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("memory tool", limit=5)
    assert any("memory tool" in r["content"] for r in results)


def test_cjk_query_finds_substring_match(populated_store):
    """Without the fix this returns []; with the fix the LIKE fallback hits."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("浅瀬記憶", limit=5)
    contents = [r["content"] for r in results]
    assert any("浅瀬記憶" in c for c in contents), (
        f"expected to find '浅瀬記憶のメモ', got {contents}"
    )


def test_cjk_query_finds_embedded_phrase(populated_store):
    """``日本語`` is embedded mid-sentence — unicode61 tokenizes the whole
    run into one token so vanilla MATCH misses it."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("日本語", limit=5)
    contents = [r["content"] for r in results]
    assert any("日本語" in c for c in contents), contents


def test_cjk_query_partial_phrase(populated_store):
    """A 2-char query against a longer stored phrase must still match."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("記憶", limit=5)
    contents = [r["content"] for r in results]
    assert any("記憶" in c for c in contents), contents


def test_chinese_query(populated_store):
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("购物", limit=5)
    contents = [r["content"] for r in results]
    assert any("购物" in c for c in contents), contents


def test_korean_query(populated_store):
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    results = retriever.search("메모리", limit=5)
    contents = [r["content"] for r in results]
    assert any("메모리" in c for c in contents), contents


def test_cjk_query_with_no_matches_returns_empty(populated_store):
    """LIKE fallback must not invent matches — a CJK query absent from the
    store still yields []."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    assert retriever.search("龍が如く", limit=5) == []


def test_cjk_query_respects_category_filter(populated_store):
    """Category filter on the LIKE path must still apply."""
    populated_store.add_fact("秘密の事実", category="private", tags="")
    retriever = FactRetriever(populated_store, hrr_weight=0.0)

    # Without the filter, the secret fact is discoverable.
    open_results = retriever.search("秘密", limit=5)
    assert any("秘密の事実" in r["content"] for r in open_results)

    # Constrained to the wrong category, it is not.
    filtered = retriever.search("秘密", category="general", limit=5)
    assert all(r["content"] != "秘密の事実" for r in filtered)


def test_cjk_query_respects_min_trust(populated_store):
    """Trust threshold on the LIKE path must still apply."""
    retriever = FactRetriever(populated_store, hrr_weight=0.0)
    # All seed facts get the default trust (0.5). Demand higher → empty.
    assert retriever.search("浅瀬記憶", min_trust=0.99, limit=5) == []


def test_like_escaping_blocks_wildcard_injection(store):
    """``%`` and ``_`` in a CJK-tagged query must be treated literally."""
    store.add_fact("legitimate 承認 record", category="general", tags="")
    store.add_fact("would-be wildcard target", category="general", tags="")
    retriever = FactRetriever(store, hrr_weight=0.0)

    # CJK forces the LIKE branch. The ``%`` sandwiched in the middle of the
    # query must NOT expand into a wildcard — the literal substring
    # ``承認%target`` is absent from every stored row.
    results = retriever.search("承認%target", limit=5)
    assert results == []
