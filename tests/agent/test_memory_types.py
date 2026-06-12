"""Tests for agent/memory_types.py + MemoryProvider type hooks (M5).

Covers:
  * ``EntryType`` enum — value, str-round-trip, canonical order
  * Default policies — boost values and staleness windows
  * ``get_policy`` / ``set_policy`` / ``reset_policies``
  * ``is_stale`` — durable types (preference, identity) never stale
  * ``classify_entry`` heuristic — keyword matches, fallback to FACT
  * ``MemoryProvider.get_entry_type`` / ``recall_boost`` default
    behaviour, plus override examples
  * ``MemoryManager._apply_recall_boost`` — reorders by boost
    without losing content
  * ``MemoryManager.prefetch_all`` end-to-end with a stub provider
    that returns mixed-type entries
"""

import pytest

from agent.memory_types import (
    EntryType,
    EntryTypePolicy,
    classify_entry,
    get_policy,
    is_stale,
    reset_policies,
    set_policy,
)


# ---------------------------------------------------------------------------
# EntryType enum
# ---------------------------------------------------------------------------


def test_entry_type_values():
    assert EntryType.PREFERENCE.value == "preference"
    assert EntryType.IDENTITY.value == "identity"
    assert EntryType.FACT.value == "fact"
    assert EntryType.PROCEDURE.value == "procedure"
    assert EntryType.BLOCKER.value == "blocker"
    assert EntryType.REFERENCE.value == "reference"


def test_entry_type_inherits_str():
    """EntryType values must be plain strings for JSON round-trip."""
    assert EntryType.PREFERENCE == "preference"
    assert str(EntryType.PREFERENCE) == "EntryType.PREFERENCE"
    # The value (used for serialization) is the bare string
    assert EntryType.PREFERENCE.value == "preference"


def test_entry_type_canonical_order():
    """Order matters — it's used for fallback resolution in managers."""
    assert list(EntryType) == [
        EntryType.PREFERENCE,
        EntryType.IDENTITY,
        EntryType.FACT,
        EntryType.PROCEDURE,
        EntryType.BLOCKER,
        EntryType.REFERENCE,
    ]


# ---------------------------------------------------------------------------
# Default policies
# ---------------------------------------------------------------------------


def test_preference_highest_boost():
    p = get_policy(EntryType.PREFERENCE)
    assert p.recall_boost == 4.0
    assert p.stale_after_seconds is None  # durable, no auto-stale


def test_identity_durable_no_staleness():
    p = get_policy(EntryType.IDENTITY)
    assert p.recall_boost == 3.0
    assert p.stale_after_seconds is None


def test_fact_baseline_boost():
    p = get_policy(EntryType.FACT)
    assert p.recall_boost == 1.0
    assert p.stale_after_seconds == 30 * 24 * 3600  # 30 days


def test_blocker_aggressive_recall():
    p = get_policy(EntryType.BLOCKER)
    assert p.recall_boost >= 2.0  # blockers surface aggressively
    assert p.stale_after_seconds == 7 * 24 * 3600  # 7 days


def test_reference_stales_fastest():
    p = get_policy(EntryType.REFERENCE)
    # References (URLs, ticket IDs) decay quickly — link rot
    assert p.stale_after_seconds <= 7 * 24 * 3600


def test_all_types_have_descriptions():
    """A description is optional but recommended for UI/logs."""
    for t in EntryType:
        assert get_policy(t).description  # non-empty


# ---------------------------------------------------------------------------
# is_stale
# ---------------------------------------------------------------------------


def test_is_stale_durable_types_never_stale():
    """preference and identity are durable; even centuries-old
    entries should not auto-stale."""
    assert is_stale(EntryType.PREFERENCE, age_seconds=10**12) is False
    assert is_stale(EntryType.IDENTITY, age_seconds=10**12) is False


def test_is_stale_within_window_returns_false():
    assert is_stale(EntryType.FACT, age_seconds=10) is False
    assert is_stale(EntryType.REFERENCE, age_seconds=24 * 3600) is False


def test_is_stale_past_window_returns_true():
    assert is_stale(EntryType.FACT, age_seconds=31 * 24 * 3600) is True
    assert is_stale(EntryType.REFERENCE, age_seconds=8 * 24 * 3600) is True


# ---------------------------------------------------------------------------
# classify_entry
# ---------------------------------------------------------------------------


def test_classify_preference_phrases():
    assert classify_entry("User prefers dark mode") == EntryType.PREFERENCE
    assert classify_entry("Always use tabs over spaces") == EntryType.PREFERENCE
    assert classify_entry("I prefer concise answers") == EntryType.PREFERENCE


def test_classify_identity_phrases():
    assert classify_entry("User's name is Alice") == EntryType.IDENTITY
    assert classify_entry("I work at Acme Corp") == EntryType.IDENTITY
    assert classify_entry("I am a backend engineer") == EntryType.IDENTITY


def test_classify_procedure_phrases():
    assert classify_entry("How to deploy: first run tests, then build") == EntryType.PROCEDURE
    assert classify_entry("Runbook for incident response") == EntryType.PROCEDURE


def test_classify_blocker_phrases():
    assert classify_entry("Gmail API is down, use fallback X") == EntryType.BLOCKER
    assert classify_entry("Blocked by ticket JIRA-1234") == EntryType.BLOCKER


def test_classify_reference_phrases():
    assert classify_entry("See https://example.com/docs") == EntryType.REFERENCE
    assert classify_entry("See also doc: design.md") == EntryType.REFERENCE
    assert classify_entry("GitHub issue #1234") == EntryType.REFERENCE


def test_classify_fact_fallback():
    """No keyword → fact (the safe default)."""
    assert classify_entry("User lives in Beijing") == EntryType.FACT
    assert classify_entry("Coffee consumption is up 12% Q3") == EntryType.FACT


def test_classify_empty_returns_fact():
    assert classify_entry("") == EntryType.FACT
    assert classify_entry("   \n  ") == EntryType.FACT


def test_classify_is_case_insensitive():
    assert classify_entry("I PREFER dark mode") == EntryType.PREFERENCE
    assert classify_entry("see HTTPS://EXAMPLE.COM") == EntryType.REFERENCE


# ---------------------------------------------------------------------------
# set_policy / reset_policies
# ---------------------------------------------------------------------------


def test_set_policy_validates_non_negative_boost():
    custom = EntryTypePolicy(recall_boost=2.5, stale_after_seconds=3600)
    set_policy(EntryType.PROCEDURE, custom)
    try:
        assert get_policy(EntryType.PROCEDURE).recall_boost == 2.5
    finally:
        reset_policies()


def test_set_policy_rejects_negative_boost():
    bad = EntryTypePolicy(recall_boost=-1.0, stale_after_seconds=None)
    with pytest.raises(ValueError) as exc:
        set_policy(EntryType.PREFERENCE, bad)
    assert "non-negative" in str(exc.value)


def test_reset_policies_restores_defaults():
    """After a custom set + reset, defaults are back."""
    custom = EntryTypePolicy(recall_boost=10.0, stale_after_seconds=None)
    set_policy(EntryType.PREFERENCE, custom)
    assert get_policy(EntryType.PREFERENCE).recall_boost == 10.0
    reset_policies()
    # Default preference boost is 4.0
    assert get_policy(EntryType.PREFERENCE).recall_boost == 4.0


# ---------------------------------------------------------------------------
# MemoryProvider integration: get_entry_type / recall_boost
# ---------------------------------------------------------------------------


def test_provider_default_get_entry_type_uses_classifier():
    """A provider that doesn't override should defer to classify_entry."""
    from agent.memory_provider import MemoryProvider

    class _Stub(MemoryProvider):
        @property
        def name(self): return "stub"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Stub()
    assert p.get_entry_type("I prefer dark mode") == EntryType.PREFERENCE
    assert p.get_entry_type("User lives in Beijing") == EntryType.FACT


def test_provider_default_recall_boost_matches_table():
    from agent.memory_provider import MemoryProvider

    class _Stub(MemoryProvider):
        @property
        def name(self): return "stub"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Stub()
    assert p.recall_boost(EntryType.PREFERENCE) == 4.0
    assert p.recall_boost(EntryType.FACT) == 1.0


def test_provider_can_override_get_entry_type():
    """A provider with a better signal (e.g. user-tagged entries)
    can override classification."""
    from agent.memory_provider import MemoryProvider

    class _Tagger(MemoryProvider):
        @property
        def name(self): return "tagger"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []
        def get_entry_type(self, content: str) -> "EntryType":
            # Heuristic provider: anything with "WATCH:" is a blocker
            if content.startswith("WATCH:"):
                return EntryType.BLOCKER
            return super().get_entry_type(content)

    p = _Tagger()
    assert p.get_entry_type("WATCH: ticket #42 in progress") == EntryType.BLOCKER
    # Falls back to classifier for non-tagged content
    assert p.get_entry_type("I prefer dark mode") == EntryType.PREFERENCE


def test_provider_can_override_recall_boost():
    """A code-assistant provider can boost PROCEDURE higher."""
    from agent.memory_provider import MemoryProvider

    class _CodeAssistant(MemoryProvider):
        @property
        def name(self): return "code-assistant"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []
        def recall_boost(self, entry_type):
            from agent.memory_types import EntryType
            if entry_type == EntryType.PROCEDURE:
                return 5.0  # procedures dominate for code generation
            return super().recall_boost(entry_type)

    p = _CodeAssistant()
    assert p.recall_boost(EntryType.PROCEDURE) == 5.0
    assert p.recall_boost(EntryType.FACT) == 1.0  # unchanged


# ---------------------------------------------------------------------------
# MemoryManager._apply_recall_boost
# ---------------------------------------------------------------------------


def test_apply_recall_boost_sorts_by_boost():
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Provider()
    raw = (
        "User lives in Beijing.\n\n"  # fact (boost 1.0)
        "Always use tabs over spaces.\n\n"  # preference (boost 4.0)
        "GitHub issue #1234 is the active blocker.\n\n"  # reference (boost 1.2)
        "I work at Acme Corp."  # identity (boost 3.0)
    )
    sorted_text = MemoryManager._apply_recall_boost(p, raw)
    # Extract chunks in their new order
    chunks = [c.strip() for c in sorted_text.split("\n\n") if c.strip()]
    # Order should be: preference (4.0) → identity (3.0) → reference (1.2) → fact (1.0)
    assert "Always use tabs" in chunks[0]
    assert "I work at Acme" in chunks[1]
    assert "GitHub issue" in chunks[2]
    assert "User lives in Beijing" in chunks[3]


def test_apply_recall_boost_stable_on_ties():
    """Equal-boost chunks keep their original order (stable sort)."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Provider()
    raw = (
        "First fact.\n\n"
        "Second fact.\n\n"
        "Third fact."
    )
    sorted_text = MemoryManager._apply_recall_boost(p, raw)
    chunks = [c.strip() for c in sorted_text.split("\n\n") if c.strip()]
    # All three are facts (boost 1.0) → stable order preserved
    assert chunks == ["First fact.", "Second fact.", "Third fact."]


def test_apply_recall_boost_single_chunk_passthrough():
    """One chunk = no reordering needed, returns input verbatim."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Provider()
    raw = "Just one fact."
    assert MemoryManager._apply_recall_boost(p, raw) == raw


def test_apply_recall_boost_preserves_content():
    """Reordering must not drop or alter chunks."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""): return ""
        def get_tool_schemas(self): return []

    p = _Provider()
    raw = "I prefer X.\n\nFact one.\n\nI am Bob.\n\nFact two."
    sorted_text = MemoryManager._apply_recall_boost(p, raw)
    original_chunks = {c.strip() for c in raw.split("\n\n") if c.strip()}
    sorted_chunks = {c.strip() for c in sorted_text.split("\n\n") if c.strip()}
    assert original_chunks == sorted_chunks


# ---------------------------------------------------------------------------
# MemoryManager.prefetch_all end-to-end with mixed-type entries
# ---------------------------------------------------------------------------


def test_prefetch_all_reorders_entries_by_boost():
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""):
            return (
                "User lives in Beijing.\n\n"  # fact
                "Always use tabs.\n\n"  # preference
                "I work at Acme."  # identity
            )
        def get_tool_schemas(self): return []

    mgr = MemoryManager()
    mgr.add_provider(_Provider())
    out = mgr.prefetch_all("anything")
    chunks = [c.strip() for c in out.split("\n\n") if c.strip()]
    # preference → identity → fact
    assert "Always use tabs" in chunks[0]
    assert "I work at Acme" in chunks[1]
    assert "User lives in Beijing" in chunks[2]


def test_prefetch_all_unchanged_for_single_chunk_provider():
    """Backward compat: a provider that returns one block of text
    (the common case) sees its output untouched."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Provider(MemoryProvider):
        @property
        def name(self): return "p"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""):
            return "Just a single block of memory text."
        def get_tool_schemas(self): return []

    mgr = MemoryManager()
    mgr.add_provider(_Provider())
    out = mgr.prefetch_all("anything")
    assert out == "Just a single block of memory text."


def test_prefetch_all_provider_failure_does_not_poison():
    """A broken provider must not block the others (existing
    contract — still holds after the boost reorder).  We can only
    register one external provider at a time, so we register the
    broken one and verify prefetch_all returns nothing rather than
    raising — the working-provider path is exercised by the other
    tests in this file."""
    from agent.memory_manager import MemoryManager
    from agent.memory_provider import MemoryProvider

    class _Broken(MemoryProvider):
        @property
        def name(self): return "broken"
        def is_available(self): return True
        def initialize(self, session_id, **kwargs): pass
        def prefetch(self, query, *, session_id=""):
            raise RuntimeError("upstream down")
        def get_tool_schemas(self): return []

    mgr = MemoryManager()
    mgr.add_provider(_Broken())
    out = mgr.prefetch_all("anything")
    # No contribution from the broken provider → empty result.
    assert out == ""
