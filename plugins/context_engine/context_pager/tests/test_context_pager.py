"""Context Pager — Comprehensive Test Suite

Tier structure (easy → extreme):
  E1-E6:  Pure function unit tests (no I/O)
  M1-M6:  Component integration tests (within-module)
  H1-H6:  Hard scenario tests (cross-module, edge cases)
  X1-X3:  Extreme integration tests (multi-session, concurrency, stress)
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from plugins.context_engine.context_pager.dedup import (
    apply_dedup_compression,
    compute_turn_signature,
    extract_turns,
    find_duplicate_tool_turns,
    hash_tool_content,
    merge_adjacent_turns,
    _merge_two_turns,
    strip_annotations,
    validate_role_alternation,
    _count_msgs_for_turns,
)
from plugins.context_engine.context_pager.store import SQLiteStore, OpenVikingArchiver
from plugins.context_engine.context_pager.engine import ContextPagerEngine
from plugins.context_engine.context_pager import register as plugin_register

# ===================================================================
# EASY — Pure function unit tests (no I/O)
# ===================================================================


class TestE1_HashToolContent:
    """All input types hash deterministically."""

    def test_string_content(self):
        h = hash_tool_content("hello world")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex
        assert h == hash_tool_content("hello world")  # deterministic

    def test_dict_content(self):
        d = {"key": "value", "nested": [1, 2, 3]}
        h = hash_tool_content(d)
        assert isinstance(h, str)
        # Same dict with different key order produces same hash
        assert h == hash_tool_content({"nested": [1, 2, 3], "key": "value"})

    def test_list_content(self):
        h = hash_tool_content([1, "a", {"b": 2}])
        assert isinstance(h, str)

    def test_none_content(self):
        h = hash_tool_content(None)
        assert isinstance(h, str)

    def test_empty_string(self):
        h = hash_tool_content("")
        assert isinstance(h, str)
        # Empty strings hash deterministically
        assert hash_tool_content("") == hash_tool_content("")

    def test_very_large_content(self):
        large = "x" * 100_000
        h = hash_tool_content(large)
        assert len(h) == 64


class TestE2_ExtractTurns:
    """Turn grouping is correct."""

    def test_basic_turn_grouping(self):
        msgs = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "tool", "content": "result_1"},
        ]
        annotated = extract_turns(msgs)
        assert len(annotated) == 4
        # System gets turn -1
        assert annotated[0]["_turn_index"] == -1
        # User starts turn 0
        assert annotated[1]["_turn_index"] == 0
        assert annotated[2]["_turn_index"] == 0  # same turn
        assert annotated[3]["_turn_index"] == 0  # same turn

    def test_multiple_turns(self):
        msgs = [
            {"role": "system", "content": "Bot."},
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]
        annotated = extract_turns(msgs)
        assert annotated[0]["_turn_index"] == -1  # system
        assert annotated[1]["_turn_index"] == 0  # first user turn
        assert annotated[2]["_turn_index"] == 0
        assert annotated[3]["_turn_index"] == 1  # second turn
        assert annotated[4]["_turn_index"] == 1

    def test_function_role_included(self):
        msgs = [
            {"role": "user", "content": "Call function"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "function", "content": "result", "name": "my_func"},
        ]
        annotated = extract_turns(msgs)
        # Function message should be included in the turn
        func_msgs = [m for m in annotated if m.get("role") == "function"]
        assert len(func_msgs) == 1
        assert func_msgs[0]["_turn_index"] == 0

    def test_no_system_message(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        annotated = extract_turns(msgs)
        assert len(annotated) == 2
        assert annotated[0]["_turn_index"] == 0
        assert annotated[1]["_turn_index"] == 0

    def test_empty_message_list(self):
        annotated = extract_turns([])
        assert annotated == []

    def test_only_system(self):
        annotated = extract_turns([{"role": "system", "content": "You are a bot."}])
        assert len(annotated) == 1
        assert annotated[0]["_turn_index"] == -1


class TestE3_StripAnnotations:
    """Internal keys are removed."""

    def test_strips_underscore_keys(self):
        msgs = [
            {"role": "user", "content": "Hi", "_turn_index": 0, "_tool_hashes": ["abc"]},
            {"role": "tool", "content": "data", "_deduped": True},
        ]
        clean = strip_annotations(msgs)
        for msg in clean:
            for key in msg:
                assert not key.startswith("_"), f"Key '{key}' should be stripped"

    def test_preserves_normal_keys(self):
        msgs = [
            {"role": "user", "content": "Hello", "name": "nathan"},
        ]
        clean = strip_annotations(msgs)
        assert clean[0]["role"] == "user"
        assert clean[0]["content"] == "Hello"
        assert clean[0]["name"] == "nathan"

    def test_empty_list(self):
        assert strip_annotations([]) == []


class TestE4_ComputeTurnSignature:
    """Turn signatures are stable and correct."""

    def test_basic_signature(self):
        turn = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "tool", "content": "output_1"},
            {"role": "tool", "content": "output_2"},
        ]
        sig = compute_turn_signature(turn)
        assert isinstance(sig, str)
        assert "+" in sig  # multiple hashes joined
        assert sig == compute_turn_signature(turn)  # deterministic

    def test_no_tool_messages(self):
        turn = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        sig = compute_turn_signature(turn)
        assert sig == ""  # no tools → empty signature

    def test_sorted_hashes(self):
        """Signatures sort hashes so order doesn't matter."""
        turn_a = [
            {"role": "user", "content": "Hi"},
            {"role": "tool", "content": "B"},
            {"role": "tool", "content": "A"},
        ]
        turn_b = [
            {"role": "user", "content": "Hi"},
            {"role": "tool", "content": "A"},
            {"role": "tool", "content": "B"},
        ]
        assert compute_turn_signature(turn_a) == compute_turn_signature(turn_b)


class TestE5_ValidateRoleAlternation:
    """Role alternation is enforced."""

    def test_valid_sequence_unchanged(self):
        msgs = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Q2"},
        ]
        result = validate_role_alternation(msgs)
        assert result == msgs

    def test_injects_filler_for_duplicate_user(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "user", "content": "Wait, actually..."},
        ]
        result = validate_role_alternation(msgs)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"  # injected filler
        assert result[1]["content"] == ""
        assert result[2]["role"] == "user"

    def test_injects_filler_for_duplicate_assistant(self):
        msgs = [
            {"role": "assistant", "content": "First"},
            {"role": "assistant", "content": "Second"},
        ]
        result = validate_role_alternation(msgs)
        assert len(result) == 3
        assert result[1]["role"] == "user"

    def test_tool_messages_dont_trigger_filler(self):
        """Tool messages can follow assistant without filler."""
        msgs = [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "content": "Done"},
        ]
        result = validate_role_alternation(msgs)
        assert result == msgs

    def test_empty_list(self):
        assert validate_role_alternation([]) == []


class TestE6_SQLiteStoreInit:
    """SQLiteStore creates tables on init."""

    def test_creates_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = SQLiteStore(db_path=db_path)
            # Verify tables exist
            conn = sqlite3.connect(db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "tool_outputs" in table_names
            assert "session_metadata" in table_names
            conn.close()
            store.close()
        finally:
            os.unlink(db_path)

    def test_fallback_to_memory_on_failure(self):
        """When path is unwritable, falls back to :memory:."""
        store = SQLiteStore(db_path="/nonexistent/dir/context_pager.db")
        # Should not raise — falls back to :memory:
        store._conn.execute("SELECT 1")
        store.close()


# ===================================================================
# MEDIUM — Component integration tests (within-module)
# ===================================================================


class TestM1_FindDuplicateToolTurns:
    """Dedup detection against an in-memory hash store."""

    def make_hash_lookup(self, hash_to_dup_map: Dict[str, List[Dict]]):
        """Create a hash_lookup_fn for testing."""
        def lookup(content_hash: str, older_than_turn: int) -> List[Dict]:
            dups = hash_to_dup_map.get(content_hash, [])
            return [d for d in dups if d["turn_index"] > older_than_turn]
        return lookup

    def test_finds_duplicate_in_middle(self):
        """Tool output that repeats a more recent one gets stubbed."""
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "abc", "tool_call_id": "c1", "name": "search"},
        ]
        annotated = extract_turns(msgs)
        h_abc = hash_tool_content("abc")
        lookup = self.make_hash_lookup({h_abc: [{"turn_index": 2}]})
        replacements = find_duplicate_tool_turns(
            annotated, 0, len(annotated) - 1,
            total_turns=1,
            hash_lookup_fn=lookup,
        )
        assert len(replacements) == 1
        idx, stub = replacements[0]
        assert "[repeated output" in stub["content"]

    def test_no_duplicate_when_none_exist(self):
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "tool", "content": "unique", "name": "get"},
        ]
        annotated = extract_turns(msgs)
        lookup = self.make_hash_lookup({})
        replacements = find_duplicate_tool_turns(
            annotated, 0, len(annotated) - 1,
            total_turns=1,
            hash_lookup_fn=lookup,
        )
        assert replacements == []

    def test_skips_non_tool_messages(self):
        msgs = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]
        annotated = extract_turns(msgs)
        lookup = self.make_hash_lookup({"anything": [{"turn_index": 5}]})
        replacements = find_duplicate_tool_turns(
            annotated, 0, len(annotated) - 1,
            total_turns=1,
            hash_lookup_fn=lookup,
        )
        assert replacements == []


class TestM2_MergeAdjacentTurns:
    """Adjacent turns with identical signatures merge correctly."""

    def test_merges_identical_tool_outputs(self):
        msgs = []
        # Turn 0
        msgs.append({"role": "user", "content": "Q1", "_turn_index": 0, "_tool_hashes": ["a"]})
        msgs.append({"role": "assistant", "content": "A1", "_turn_index": 0, "_tool_hashes": ["a"]})
        msgs.append({"role": "tool", "content": "same_output", "_turn_index": 0, "_tool_hashes": ["a"]})
        # Turn 1 — same output
        msgs.append({"role": "user", "content": "Q2 (same tool)", "_turn_index": 1, "_tool_hashes": ["a"]})
        msgs.append({"role": "assistant", "content": "A2", "_turn_index": 1, "_tool_hashes": ["a"]})
        msgs.append({"role": "tool", "content": "same_output", "_turn_index": 1, "_tool_hashes": ["a"]})

        merged = merge_adjacent_turns(msgs, 0, len(msgs) - 1)
        # Should be shorter: user from turn 0, assistant from turn 1, tool deduped
        assert len(merged) < len(msgs)
        # Should have exactly one user, one assistant, one(or fewer) tool
        roles = [m["role"] for m in merged]
        assert roles.count("user") == 1
        # The assistant message from turn 1 should be kept
        assert merged[1]["content"] == "A2"

    def test_no_merge_when_signatures_differ(self):
        msgs = [
            {"role": "user", "content": "Q1", "_turn_index": 0, "_tool_hashes": ["aaa"]},
            {"role": "tool", "content": "output_a", "_turn_index": 0, "_tool_hashes": ["aaa"]},
            {"role": "user", "content": "Q2", "_turn_index": 1, "_tool_hashes": ["bbb"]},
            {"role": "tool", "content": "output_b", "_turn_index": 1, "_tool_hashes": ["bbb"]},
        ]
        merged = merge_adjacent_turns(msgs, 0, len(msgs) - 1)
        assert len(merged) == len(msgs)

    def test_single_turn_no_merge(self):
        msgs = [
            {"role": "user", "content": "Q1", "_turn_index": 0, "_tool_hashes": ["a"]},
        ]
        merged = merge_adjacent_turns(msgs, 0, len(msgs) - 1)
        assert merged == msgs

    def test_empty_middle(self):
        merged = merge_adjacent_turns([], 0, -1)
        assert merged == []


class TestM3_ApplyDedupCompression:
    """Full dedup pipeline end-to-end."""

    def hash_lookup_fn(self, content_hash, older_than_turn):
        h_common = hash_tool_content("common_output")
        if content_hash == h_common and older_than_turn < 3:
            return [{"turn_index": 3}]
        return []

    def test_full_pipeline_dedup(self):
        msgs = [
            {"role": "system", "content": "You are a bot."},
            # Turn 0 — protected head
            {"role": "user", "content": "Intro"},
            {"role": "assistant", "content": "Welcome"},
            # Turn 1 — protected head
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "common_output", "tool_call_id": "c1", "name": "search"},
            # Turn 2 — middle, will be deduped
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2"}]},
            {"role": "tool", "content": "common_output", "tool_call_id": "c2", "name": "search"},
            # Turn 3 — protected tail
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "Final answer"},
        ]
        compressed, originals = apply_dedup_compression(
            msgs, protect_first_n=1, protect_last_n=1,
            hash_lookup_fn=self.hash_lookup_fn,
        )
        # No messages should have annotations
        for msg in compressed:
            for key in msg:
                assert not key.startswith("_")
        # Should still be a valid sequence
        assert len(compressed) >= 3  # at minimum sys + head + tail

    def test_few_messages_noop(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        compressed, originals = apply_dedup_compression(
            msgs, protect_first_n=3, protect_last_n=6,
            hash_lookup_fn=lambda h, t: [],
        )
        assert compressed == msgs

    def test_empty_input(self):
        compressed, originals = apply_dedup_compression(
            [], 3, 6, lambda h, t: [],
        )
        assert compressed == []
        assert originals == []


class TestM4_EngineABCCompliance:
    """ContextPagerEngine satisfies the ContextEngine ABC."""

    def test_name(self):
        engine = ContextPagerEngine()
        assert engine.name == "context_pager"

    def test_implements_required_methods(self):
        engine = ContextPagerEngine()
        assert hasattr(engine, "update_from_response")
        assert hasattr(engine, "should_compress")
        assert hasattr(engine, "compress")

    def test_default_values(self):
        engine = ContextPagerEngine()
        assert engine.protect_first_n == 3
        assert engine.protect_last_n == 6
        assert engine.threshold_percent == 0.75
        assert engine.context_length == 128_000

    def test_threshold_tokens_calculation(self):
        engine = ContextPagerEngine(context_length=100_000, threshold_percent=0.50)
        assert engine.threshold_tokens == 50_000


class TestM5_CompressionGates:
    """should_compress and has_content_to_compress."""

    def test_should_compress_above_threshold(self):
        engine = ContextPagerEngine(context_length=100_000, threshold_percent=0.50)
        assert engine.should_compress(60_000) is True

    def test_should_compress_below_threshold(self):
        engine = ContextPagerEngine(context_length=100_000, threshold_percent=0.50)
        assert engine.should_compress(40_000) is False

    def test_should_compress_zero_tokens(self):
        engine = ContextPagerEngine()
        assert engine.should_compress(0) is False

    def test_has_content_to_compress_enough(self):
        engine = ContextPagerEngine(protect_first_n=1, protect_last_n=1)
        msgs = [
            {"role": "system", "content": "x"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "2"},
            {"role": "assistant", "content": "b"},
        ]
        assert engine.has_content_to_compress(msgs) is True

    def test_has_content_to_compress_not_enough(self):
        engine = ContextPagerEngine(protect_first_n=3, protect_last_n=6)
        msgs = [
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "a"},
        ]
        assert engine.has_content_to_compress(msgs) is False

    def test_has_content_to_compress_uses_non_system_count(self):
        """System prompt is excluded from the non-system count."""
        engine = ContextPagerEngine(protect_first_n=1, protect_last_n=0)
        msgs = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "a"},
        ]
        # non-system = 2, protect_first_n + protect_last_n = 1 → 2 > 1 → True
        assert engine.has_content_to_compress(msgs) is True


class TestM6_SQLiteRoundTrip:
    """Store and retrieve tool hashes."""

    def test_store_and_find(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = SQLiteStore(db_path=db_path)
            store.store_tool_hash("session1", 0, 0, "hash_abc", "content_abc", "search")
            store.store_tool_hash("session1", 5, 0, "hash_abc", "content_abc", "search")

            # Look for duplicates of hash_abc older than turn 2
            dups = store.find_tool_duplicates("session1", "hash_abc", older_than_turn=2)
            assert len(dups) == 1
            assert dups[0]["turn_index"] == 5  # the more recent one

            store.close()
        finally:
            os.unlink(db_path)

    def test_no_duplicates(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = SQLiteStore(db_path=db_path)
            store.store_tool_hash("session1", 0, 0, "hash_abc", "data", "search")
            dups = store.find_tool_duplicates("session1", "hash_xyz", older_than_turn=0)
            assert dups == []
            store.close()
        finally:
            os.unlink(db_path)

    def test_session_isolation(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = SQLiteStore(db_path=db_path)
            store.store_tool_hash("session_a", 0, 0, "same_hash", "data", "search")
            dups = store.find_tool_duplicates("session_b", "same_hash", older_than_turn=0)
            assert dups == []  # isolated by session_id
            store.close()
        finally:
            os.unlink(db_path)


# ===================================================================
# HARD — Complex scenario tests (cross-module, edge cases)
# ===================================================================


class TestH1_NoOpScenarios:
    """apply_dedup_compression handles edge cases gracefully."""

    def test_only_system_message(self):
        compressed, originals = apply_dedup_compression(
            [{"role": "system", "content": "Bot"}],
            3, 6, lambda h, t: [],
        )
        assert len(compressed) == 1

    def test_exactly_head_plus_tail_no_middle(self):
        msgs = [
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "2"},
            {"role": "assistant", "content": "b"},
        ]
        compressed, originals = apply_dedup_compression(
            msgs, protect_first_n=1, protect_last_n=1,
            hash_lookup_fn=lambda h, t: [],
        )
        # protect_first_n=1 (1 turn = user+assistant=2 msgs)
        # protect_last_n=1 (1 turn = user+assistant=2 msgs)
        # total turns = 2, head=1, tail=1 → no middle
        assert len(compressed) == len(msgs)


class TestH2_FunctionRoleDedup:
    """Repeated tool outputs across turns get deduped."""

    def hash_lookup_fn(self, content_hash, older_than_turn):
        h = hash_tool_content("repeated_data")
        if content_hash == h and older_than_turn < 5:
            return [{"turn_index": 5}]
        return []

    def test_messages_deduped_across_turns(self):
        msgs = [
            # Turn 0 — protected
            {"role": "user", "content": "First call"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "repeated_data", "tool_call_id": "c1", "name": "get"},
            # Turn 1 — protected
            {"role": "user", "content": "Second call"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2"}]},
            {"role": "tool", "content": "repeated_data", "tool_call_id": "c2", "name": "get"},
            # Turn 2 — middle, should be stubbed
            {"role": "user", "content": "Third call"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c3"}]},
            {"role": "tool", "content": "repeated_data", "tool_call_id": "c3", "name": "get"},
            # Turn 3 — middle, should be stubbed
            {"role": "user", "content": "Fourth call"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c4"}]},
            {"role": "tool", "content": "repeated_data", "tool_call_id": "c4", "name": "get"},
            # Turn 4 — middle, should be stubbed
            {"role": "user", "content": "Fifth call"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c5"}]},
            {"role": "tool", "content": "repeated_data", "tool_call_id": "c5", "name": "get"},
            # Turn 5 — tail, kept as reference
            {"role": "user", "content": "Done"},
            {"role": "assistant", "content": "All set"},
        ]
        compressed, _ = apply_dedup_compression(
            msgs, protect_first_n=1, protect_last_n=1,
            hash_lookup_fn=self.hash_lookup_fn,
        )
        # Middle turns (2,3,4) tool outputs should be stubbed
        stubs = [m for m in compressed if isinstance(m.get("content"), str)
                 and m["content"].startswith("[repeated")]
        assert len(stubs) >= 1
        stub_refs = [s["content"] for s in stubs]
        assert any("turn 5" in s for s in stub_refs)


class TestH3_MergeWithMixedContent:
    """Merging preserves correct messages from each turn."""

    def test_merge_keeps_correct_assistant(self):
        """When merging, assistant from most recent turn is kept."""
        msgs = [
            {"role": "user", "content": "Old query", "_turn_index": 0, "_tool_hashes": ["a"]},
            {"role": "assistant", "content": "Old answer", "_turn_index": 0, "_tool_hashes": ["a"]},
            {"role": "tool", "content": "same", "_turn_index": 0, "_tool_hashes": ["a"]},
            {"role": "user", "content": "New query", "_turn_index": 1, "_tool_hashes": ["a"]},
            {"role": "assistant", "content": "New answer", "_turn_index": 1, "_tool_hashes": ["a"]},
            {"role": "tool", "content": "same", "_turn_index": 1, "_tool_hashes": ["a"]},
        ]
        merged = merge_adjacent_turns(msgs, 0, len(msgs) - 1)
        # Should keep user from turn 0, assistant from turn 1
        user_msgs = [m for m in merged if m["role"] == "user"]
        asst_msgs = [m for m in merged if m["role"] == "assistant"]
        assert len(user_msgs) == 1
        assert user_msgs[0]["content"] == "Old query"
        assert len(asst_msgs) == 1
        assert asst_msgs[0]["content"] == "New answer"


class TestH4_EngineCompressLifecycle:
    """Engine.compress works end-to-end without crashing."""

    def test_compress_on_fresh_db(self):
        """Compress with no pre-existing hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=1, protect_last_n=1,
                threshold_percent=0.50, context_length=100_000,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("test_session")

            msgs = [
                {"role": "system", "content": "You are a bot."},
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
                {"role": "user", "content": "Q2"},
                {"role": "assistant", "content": "A2"},
                {"role": "user", "content": "Q3"},
                {"role": "assistant", "content": "A3"},
            ]

            result = engine.compress(msgs)
            # Should still return valid messages
            assert len(result) > 0
            assert result[0]["role"] == "system"
            assert engine.compression_count >= 0

    def test_compress_preserves_system_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=1, protect_last_n=1,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("test_session")
            msgs = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Q1"},
                {"role": "assistant", "content": "A1"},
                {"role": "user", "content": "Q2"},
                {"role": "assistant", "content": "A2"},
            ]
            result = engine.compress(msgs)
            assert result[0]["role"] == "system"
            assert result[0]["content"] == "You are a helpful assistant."


class TestH5_IdenticalToolOutputs:
    """Multiple identical tool outputs in the same session."""

    def test_duplicates_across_turns(self):
        """Same tool output 3 times — first 2 get deduped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=1, protect_last_n=1,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("test_session")

            # Build session state: pre-populate with first occurrence
            engine._sqlite.store_tool_hash(
                "test_session", 1, 0,
                hash_tool_content("identical_data"),
                "identical_data", "get_info",
            )

            msgs = [
                {"role": "system", "content": "Bot."},
                # Turn 0 — protected
                {"role": "user", "content": "First"},
                {"role": "assistant", "content": "Done", "tool_calls": [{"id": "c0"}]},
                {"role": "tool", "content": "unique_data", "tool_call_id": "c0", "name": "get_info"},
                # Turn 1 — should be kept (already stored, and in protected tail)
                {"role": "user", "content": "Second"},
                {"role": "assistant", "content": "Done", "tool_calls": [{"id": "c1"}]},
                {"role": "tool", "content": "identical_data", "tool_call_id": "c1", "name": "get_info"},
            ]

            result = engine.compress(msgs)
            unique_tool_contents = [
                m["content"] for m in result
                if m.get("role") == "tool" and m.get("name") == "get_info"
            ]
            # The "identical_data" in turn 1 (tail) is protected, so it stays verbatim
            assert "identical_data" in unique_tool_contents


class TestH6_SessionLifecycle:
    """Full session lifecycle: start → compress → end → start again."""

    def test_start_end_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                sqlite_path=db_path,
                openviking_enabled=False,
            )

            # Session 1
            engine.on_session_start("session_1")
            assert engine._session_id == "session_1"
            engine.on_session_end("session_1", [{"role": "user", "content": "bye"}])
            assert engine._session_id == ""

            # Session 2
            engine.on_session_start("session_2")
            assert engine._session_id == "session_2"
            assert engine.compression_count == 0


# ===================================================================
# EXTREME — Full integration tests
# ===================================================================


class TestX1_MultiSessionDedup:
    """Same content across sessions is NOT deduped (session isolation)."""

    def test_cross_session_no_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=0, protect_last_n=0,
                sqlite_path=db_path,
                openviking_enabled=False,
            )

            # Session A: store a hash
            engine.on_session_start("session_a")
            engine._sqlite.store_tool_hash(
                "session_a", 0, 0,
                hash_tool_content("cross_data"),
                "cross_data", "search",
            )
            engine.on_session_end("session_a", [])

            # Session B: same content should NOT find duplicates
            # The hash_lookup_fn queries by session_id — cross-session queries
            # won't match since we use session_id as a filter.
            engine.on_session_start("session_b")
            h = hash_tool_content("cross_data")
            dups = engine._sqlite.find_tool_duplicates("session_b", h, older_than_turn=0)
            assert dups == []  # isolated per session

            engine.on_session_end("session_b", [])


class TestX2_LargeMessageList:
    """Compress a list of 50+ messages with many duplicates."""

    def test_many_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=2, protect_last_n=3,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("large_test")

            # Pre-populate with the "common" hash at several turns
            common_hash = hash_tool_content("common_tool_output")
            for t in range(1, 20):
                engine._sqlite.store_tool_hash(
                    "large_test", t, 0, common_hash, "common_tool_output", "search",
                )

            # Build a 50-message list
            msgs = [{"role": "system", "content": "Bot."}]
            for i in range(24):
                msgs.append({"role": "user", "content": f"Q{i}"})
                msgs.append(
                    {"role": "assistant", "content": "Processing...",
                     "tool_calls": [{"id": f"c{i}"}]}
                )
                msgs.append(
                    {"role": "tool", "content": "common_tool_output",
                     "tool_call_id": f"c{i}", "name": "search"}
                )

            # Remove tool_call_id from last tool for variety
            msgs[-1]["tool_call_id"] = "c-last"

            result = engine.compress(msgs)
            assert len(result) > 0
            assert result[0]["role"] == "system"

            # Count stubs
            stubs = [m for m in result if isinstance(m.get("content"), str)
                     and m["content"].startswith("[repeated")]
            unique_tools = [m for m in result if m.get("role") == "tool"
                            and not (isinstance(m.get("content"), str)
                                     and m["content"].startswith("[repeated]"))]

            # With protect_first_n=2 (sys+2 user/assistant/tool turns = ~6msgs),
            # protect_last_n=3 (~9msgs), that's ~15 protected out of ~73.
            # The remaining ~58 are middle — many duplicate tools get stubbed.
            # Not asserting exact count (depends on turn boundary math) but:
            assert len(stubs) >= 5  # substantial dedup happened

    def test_no_duplicates_stress(self):
        """50 messages, all unique content — no dedup, no crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=2, protect_last_n=3,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("unique_test")

            msgs = [{"role": "system", "content": "Bot."}]
            for i in range(24):
                msgs.append({"role": "user", "content": f"Unique Q{i}"})
                msgs.append(
                    {"role": "assistant", "content": f"Unique A{i}"}
                )

            result = engine.compress(msgs)
            # With all unique content, shouldn't reduce much
            assert len(result) >= len(msgs) * 0.5  # not aggressively trimmed


class TestX3_ConcurrentCompression:
    """Multiple threads calling compress simultaneously on the same engine."""

    def test_concurrent_compress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            engine = ContextPagerEngine(
                protect_first_n=1, protect_last_n=1,
                sqlite_path=db_path,
                openviking_enabled=False,
            )
            engine.on_session_start("concurrent_test")

            def compress_thread(thread_id: int):
                """Each thread compresses its own message list."""
                msgs = [
                    {"role": "system", "content": "Bot."},
                    {"role": "user", "content": f"Q from thread {thread_id}"},
                    {"role": "assistant", "content": f"A from thread {thread_id}"},
                ]
                try:
                    result = engine.compress(msgs)
                    assert len(result) > 0
                    return True
                except Exception:
                    return False

            threads = []
            results = []
            for i in range(10):
                t = threading.Thread(
                    target=lambda idx=i: results.append(compress_thread(idx))
                )
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert all(results), "All threads should complete without error"
            # Session ID should still be intact
            assert engine._session_id == "concurrent_test"


# ===================================================================
# Plugin registration test
# ===================================================================


class TestPluginRegistration:
    """The register() function works with a mock plugin context."""

    def test_register_creates_engine(self):
        class MockCtx:
            config = {}
            registered_engine = None
            def register_context_engine(self, engine):
                self.registered_engine = engine

        ctx = MockCtx()
        plugin_register(ctx)
        assert ctx.registered_engine is not None
        assert ctx.registered_engine.name == "context_pager"

    def test_register_passes_config(self):
        class MockCtx:
            config = {
                "context_pager": {
                    "protect_first_n": 5,
                    "protect_last_n": 10,
                    "threshold_percent": 0.80,
                }
            }
            registered_engine = None
            def register_context_engine(self, engine):
                self.registered_engine = engine

        ctx = MockCtx()
        plugin_register(ctx)
        engine = ctx.registered_engine
        assert engine.protect_first_n == 5
        assert engine.protect_last_n == 10
        assert engine.threshold_percent == 0.80


# ===================================================================
# Run configuration
# ===================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
