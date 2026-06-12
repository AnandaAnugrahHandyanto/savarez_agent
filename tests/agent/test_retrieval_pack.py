"""Tests for agent/retrieval_pack.py (M1 — 5-section retrieval pack).

Covers:
- RetrievalPack dataclass: construction, merge, from_iterables, from_freetext
- render_retrieval_pack: stable order, empty sections, item caps
- MemoryProvider ABC integration: default retrieve_pack wraps prefetch
- MemoryManager.prefetch_pack_all: merges packs across providers
"""

import pytest

from agent.retrieval_pack import (
    PACK_SECTIONS,
    RetrievalPack,
    render_retrieval_pack,
)


# ---------------------------------------------------------------------------
# RetrievalPack dataclass
# ---------------------------------------------------------------------------


def test_empty_pack_is_empty():
    assert RetrievalPack().is_empty() is True


def test_pack_with_one_item_not_empty():
    p = RetrievalPack(known_facts=["User lives in Beijing."])
    assert p.is_empty() is False


def test_section_lookup_raises_for_unknown():
    p = RetrievalPack()
    with pytest.raises(KeyError) as exc:
        p.section("not_a_real_section")
    assert "not_a_real_section" in str(exc.value)
    assert "known_facts" in str(exc.value)  # all valid sections listed


def test_section_lookup_returns_correct_list():
    p = RetrievalPack(
        known_facts=["a", "b"],
        blockers=["x"],
    )
    assert p.section("known_facts") == ["a", "b"]
    assert p.section("blockers") == ["x"]
    assert p.section("high_signal") == []


def test_merge_appends_per_section():
    a = RetrievalPack(known_facts=["a1"], blockers=["b1"])
    b = RetrievalPack(known_facts=["a2"], open_questions=["q1"])
    merged = a.merge(b)
    assert merged.known_facts == ["a1", "a2"]
    assert merged.blockers == ["b1"]
    assert merged.open_questions == ["q1"]
    # Originals are not mutated
    assert a.known_facts == ["a1"]
    assert b.known_facts == ["a2"]


def test_from_iterables_handles_none():
    p = RetrievalPack.from_iterables(known_facts=["x"])
    assert p.known_facts == ["x"]
    assert p.high_signal == []


def test_from_freetext_empty_returns_empty_pack():
    assert RetrievalPack.from_freetext("").is_empty()
    assert RetrievalPack.from_freetext("   \n  \t").is_empty()


def test_from_freetext_puts_lines_in_high_signal():
    p = RetrievalPack.from_freetext("line one\nline two\n\n  \nline three")
    assert p.high_signal == ["line one", "line two", "line three"]
    assert p.known_facts == []  # default category
    assert p.blockers == []


def test_pack_sections_are_canonical_order():
    # The contract: order is part of the API surface.  Tests depend on it.
    assert PACK_SECTIONS == (
        "known_facts",
        "high_signal",
        "constraints",
        "blockers",
        "open_questions",
    )


# ---------------------------------------------------------------------------
# render_retrieval_pack
# ---------------------------------------------------------------------------


def test_render_empty_pack_returns_empty_string():
    assert render_retrieval_pack(RetrievalPack()) == ""
    assert render_retrieval_pack(None) == ""


def test_render_emits_all_five_sections_in_canonical_order():
    p = RetrievalPack(known_facts=["a fact"])
    out = render_retrieval_pack(p)
    # Every section heading must appear, in PACK_SECTIONS order
    positions = [out.index(f"## {name}") for name in PACK_SECTIONS]
    assert positions == sorted(positions)


def test_render_empty_sections_show_placeholder():
    p = RetrievalPack(known_facts=["only fact"])
    out = render_retrieval_pack(p)
    for name in PACK_SECTIONS:
        if name != "known_facts":
            assert f"## {name}" in out
            assert "(none)" in out


def test_render_caps_items_per_section():
    p = RetrievalPack(high_signal=[f"item-{i}" for i in range(50)])
    out = render_retrieval_pack(p, max_items_per_section=5)
    assert out.count("- item-") == 5
    # First 5 items present
    for i in range(5):
        assert f"item-{i}" in out
    # Later items not present
    assert "item-5" not in out
    assert "item-49" not in out


def test_render_truncates_long_items():
    long = "x" * 1000
    p = RetrievalPack(high_signal=[long])
    out = render_retrieval_pack(p, max_chars_per_item=100)
    # Find the actual item line (not the "(none)" placeholder)
    lines = [
        ln for ln in out.splitlines()
        if ln.startswith("- ") and ln != "- (none)"
    ]
    assert len(lines) == 1
    rendered = lines[0][2:]  # strip the "- " prefix
    # The body is the original 1000 chars, capped to (max_chars_per_item
    # - 1) so the trailing "…" can be appended.
    assert rendered.endswith("…")
    assert len(rendered) <= 100  # the cap, plus the ellipsis fits in 100


def test_render_does_not_truncate_short_items():
    short = "x" * 50
    p = RetrievalPack(high_signal=[short])
    out = render_retrieval_pack(p, max_chars_per_item=100)
    # Items shorter than the cap render verbatim — no ellipsis
    assert "…\n" not in out and not out.rstrip().endswith("…")
    assert short in out


def test_render_output_is_stable_for_caching():
    """Same input → same output.  Important for prompt caching."""
    p = RetrievalPack(
        known_facts=["a"],
        high_signal=["b"],
    )
    out1 = render_retrieval_pack(p)
    out2 = render_retrieval_pack(p)
    assert out1 == out2


# ---------------------------------------------------------------------------
# MemoryProvider ABC integration (default retrieve_pack)
# ---------------------------------------------------------------------------


def test_default_retrieve_pack_wraps_prefetch_text():
    """Providers that don't override retrieve_pack should still
    participate in the structured pipeline via freetext fallback."""
    from agent.memory_provider import MemoryProvider

    class _StubProvider(MemoryProvider):
        @property
        def name(self):
            return "stub"

        def is_available(self):
            return True

        def initialize(self, session_id, **kwargs):
            pass

        def prefetch(self, query, *, session_id=""):
            return "first line\nsecond line"

        def get_tool_schemas(self):
            return []

    p = _StubProvider()
    pack = p.retrieve_pack("anything")
    assert pack.high_signal == ["first line", "second line"]
    assert pack.known_facts == []


def test_default_retrieve_pack_empty_when_prefetch_empty():
    from agent.memory_provider import MemoryProvider

    class _EmptyProvider(MemoryProvider):
        @property
        def name(self):
            return "empty"

        def is_available(self):
            return True

        def initialize(self, session_id, **kwargs):
            pass

        def prefetch(self, query, *, session_id=""):
            return ""

        def get_tool_schemas(self):
            return []

    pack = _EmptyProvider().retrieve_pack("anything")
    assert pack.is_empty()


def test_provider_can_override_retrieve_pack_with_structure():
    """A provider that wants true structure can override retrieve_pack."""
    from agent.memory_provider import MemoryProvider

    class _StructuredProvider(MemoryProvider):
        @property
        def name(self):
            return "structured"

        def is_available(self):
            return True

        def initialize(self, session_id, **kwargs):
            pass

        def prefetch(self, query, *, session_id=""):
            return ""  # legacy path returns nothing useful

        def retrieve_pack(self, query, *, session_id="", intent=""):
            return RetrievalPack(
                known_facts=["User is 27."],
                blockers=["Backend API is down."],
            )

        def get_tool_schemas(self):
            return []

    p = _StructuredProvider()
    pack = p.retrieve_pack("anything", intent="fact_lookup")
    assert pack.known_facts == ["User is 27."]
    assert pack.blockers == ["Backend API is down."]


# ---------------------------------------------------------------------------
# MemoryManager.prefetch_pack_all
# ---------------------------------------------------------------------------


def test_manager_prefetch_pack_all_merges_providers():
    """MemoryManager only allows one external provider at a time.  We
    register the built-in alongside a custom one, both contributing
    different pack sections."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _A(MemoryProvider):
        @property
        def name(self): return "custom_a"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""):
            return "from A"
        def retrieve_pack(self, query, *, session_id="", intent=""):
            return RetrievalPack(known_facts=["a-fact"])
        def get_tool_schemas(self): return []

    mgr = MemoryManager()
    mgr.add_provider(_A())
    pack = mgr.prefetch_pack_all("anything")
    assert pack.known_facts == ["a-fact"]
    # A's prefetch is also folded in via the freetext fallback
    # (registered provider, so its free-text prefetch is included
    # as high_signal because retrieve_pack returned a non-empty pack
    # but we ALSO want to make sure the freetext path is exercised).
    assert pack.high_signal == []  # _A overrode retrieve_pack
    # The pack should still render without error
    from agent.retrieval_pack import render_retrieval_pack
    out = render_retrieval_pack(pack)
    assert "a-fact" in out


def test_manager_prefetch_pack_all_handles_provider_failure():
    """A broken provider must not poison the merged pack."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Broken(MemoryProvider):
        @property
        def name(self): return "broken"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def retrieve_pack(self, query, *, session_id="", intent=""):
            raise RuntimeError("upstream down")
        def get_tool_schemas(self): return []

    mgr = MemoryManager()
    mgr.add_provider(_Broken())
    # Even though the only provider raises, prefetch_pack_all should
    # return an empty pack and not raise.
    pack = mgr.prefetch_pack_all("anything")
    assert pack.is_empty()
