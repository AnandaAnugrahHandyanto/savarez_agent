"""Tests for dialectical memory belief structures and algorithms."""

import json
import time
import pytest
from pathlib import Path

from tools.memory_beliefs import (
    EntryMeta, ContradictionEdge, MetaStore,
    MaturityLevel, BeliefStatus, KnowledgeType, SourceKind, ContradictionMode,
    DECAY_CONFIG, MATURITY_CONFIDENCE_FLOOR, SOURCE_AUTHORITY_DEFAULT,
    text_hash,
    compute_decayed_confidence, compute_effective_score,
    evaluate_promotion, promote_entry, resolve_contradiction,
    record_hit, record_surface, record_ignore, record_observed_behavior,
    check_validation_decay,
)


# --- Fixtures ---

@pytest.fixture
def fresh_meta():
    return EntryMeta()


@pytest.fixture
def aged_meta():
    return EntryMeta(
        created_at=time.time() - 30 * 86400,
        updated_at=time.time() - 30 * 86400,
        last_validated_at=time.time() - 30 * 86400,
    )


@pytest.fixture
def meta_store_with_entries():
    store = MetaStore()
    a = EntryMeta(entry_id="aaa", maturity=MaturityLevel.INCIDENT)
    b = EntryMeta(entry_id="bbb", maturity=MaturityLevel.INCIDENT)
    c = EntryMeta(entry_id="ccc", maturity=MaturityLevel.PATTERN)
    store.entries = {"aaa": a, "bbb": b, "ccc": c}
    store.contradictions = [
        ContradictionEdge(from_id="aaa", to_id="bbb", reason="test conflict")
    ]
    return store


# --- EntryMeta Tests ---

class TestEntryMeta:
    def test_defaults(self, fresh_meta):
        assert fresh_meta.maturity == MaturityLevel.INCIDENT
        assert fresh_meta.knowledge_type == KnowledgeType.BELIEF
        assert fresh_meta.source_kind == SourceKind.USER_EXPLICIT
        assert fresh_meta.status == BeliefStatus.ACTIVE
        assert fresh_meta.confidence == 0.7
        assert fresh_meta.hit_count == 0

    def test_to_dict_roundtrip(self, fresh_meta):
        d = fresh_meta.to_dict()
        restored = EntryMeta.from_dict(d)
        assert restored.entry_id == fresh_meta.entry_id
        assert restored.maturity == fresh_meta.maturity
        assert restored.status == fresh_meta.status
        assert restored.confidence == fresh_meta.confidence

    def test_from_dict_forward_compat(self):
        d = {"entry_id": "test", "maturity": 0, "unknown_future_field": 42}
        meta = EntryMeta.from_dict(d)
        assert meta.entry_id == "test"
        assert meta.maturity == MaturityLevel.INCIDENT

    def test_maturity_enum_serialization(self):
        assert MaturityLevel.INCIDENT.value == 0
        assert MaturityLevel.WISDOM.value == 3


# --- MetaStore Tests ---

class TestMetaStore:
    def test_empty_store(self):
        store = MetaStore()
        assert len(store.entries) == 0
        assert len(store.contradictions) == 0

    def test_roundtrip(self, meta_store_with_entries):
        d = meta_store_with_entries.to_dict()
        restored = MetaStore.from_dict(d)
        assert len(restored.entries) == 3
        assert "aaa" in restored.entries
        assert len(restored.contradictions) == 1

    def test_text_to_id_mapping(self):
        store = MetaStore()
        h = text_hash("hello world")
        store.text_to_id[h] = "test_id"
        assert store.text_to_id[h] == "test_id"


# --- Decay Tests ---

class TestConfidenceDecay:
    def test_facts_never_decay(self, fresh_meta):
        fresh_meta.knowledge_type = KnowledgeType.FACT
        fresh_meta.confidence = 0.9
        fresh_meta.updated_at = time.time() - 365 * 86400
        assert compute_decayed_confidence(fresh_meta) == 0.9

    def test_state_decays_fast(self, aged_meta):
        aged_meta.knowledge_type = KnowledgeType.STATE
        aged_meta.confidence = 0.9
        decayed = compute_decayed_confidence(aged_meta)
        assert decayed < 0.9
        assert decayed >= DECAY_CONFIG[KnowledgeType.STATE]["floor"]

    def test_recent_validation_skips_decay(self, fresh_meta):
        fresh_meta.knowledge_type = KnowledgeType.STATE
        fresh_meta.confidence = 0.9
        fresh_meta.updated_at = time.time() - 30 * 86400
        fresh_meta.last_validated_at = time.time() - 0.5 * 86400
        assert compute_decayed_confidence(fresh_meta) == 0.9

    def test_observed_behavior_decays_slower(self):
        base = EntryMeta(
            confidence=0.9, knowledge_type=KnowledgeType.BELIEF,
            updated_at=time.time() - 60 * 86400,
            last_validated_at=time.time() - 60 * 86400,
        )
        observed = EntryMeta(
            confidence=0.9, knowledge_type=KnowledgeType.BELIEF,
            source_kind=SourceKind.OBSERVED, observed_behavior_count=3,
            updated_at=time.time() - 60 * 86400,
            last_validated_at=time.time() - 60 * 86400,
        )
        assert compute_decayed_confidence(observed) > compute_decayed_confidence(base)

    def test_maturity_floor_overrides_type_floor(self):
        meta = EntryMeta(
            maturity=MaturityLevel.PRINCIPLE,
            knowledge_type=KnowledgeType.STATE,
            confidence=0.9,
            updated_at=time.time() - 200 * 86400,
            last_validated_at=time.time() - 200 * 86400,
        )
        decayed = compute_decayed_confidence(meta)
        assert decayed >= MATURITY_CONFIDENCE_FLOOR[MaturityLevel.PRINCIPLE]


# --- Promotion Tests ---

class TestPromotion:
    def test_incident_promotes_to_pattern(self, fresh_meta):
        fresh_meta.hit_count = 3
        fresh_meta.confidence = 0.6
        fresh_meta.created_at = time.time() - 5 * 86400
        assert evaluate_promotion(fresh_meta) == MaturityLevel.PATTERN

    def test_insufficient_hits(self, fresh_meta):
        fresh_meta.hit_count = 1
        fresh_meta.created_at = time.time() - 10 * 86400
        assert evaluate_promotion(fresh_meta) is None

    def test_too_young(self, fresh_meta):
        fresh_meta.hit_count = 5
        fresh_meta.created_at = time.time() - 1 * 86400
        assert evaluate_promotion(fresh_meta) is None

    def test_wisdom_never_promotes(self):
        meta = EntryMeta(maturity=MaturityLevel.WISDOM)
        assert evaluate_promotion(meta) is None

    def test_behavior_counts_double(self):
        meta = EntryMeta(
            hit_count=1, observed_behavior_count=1,
            confidence=0.6, created_at=time.time() - 5 * 86400,
        )
        assert evaluate_promotion(meta) == MaturityLevel.PATTERN


# --- Behavioral Signal Tests ---

class TestBehavioralSignals:
    def test_hit_increments(self, fresh_meta):
        record_hit(fresh_meta)
        assert fresh_meta.hit_count == 1
        assert fresh_meta.last_validated_at > 0

    def test_ignore_capped_at_50(self, fresh_meta):
        for i in range(60):
            record_ignore(fresh_meta, {}, f"reason_{i}")
        assert len(fresh_meta.noise_context) == 50

    def test_observed_behavior_boosts_authority(self, fresh_meta):
        fresh_meta.authority = 0.5
        record_observed_behavior(fresh_meta)
        assert fresh_meta.authority > 0.5


# --- Validation Decay Tests ---

class TestValidationDecay:
    def test_active_below_threshold_decays(self):
        meta = EntryMeta(
            status=BeliefStatus.ACTIVE, confidence=0.15,
            knowledge_type=KnowledgeType.STATE,
            updated_at=time.time() - 100 * 86400,
            last_validated_at=time.time() - 100 * 86400,
        )
        assert check_validation_decay(meta) == BeliefStatus.DECAYED

    def test_healthy_stays_active(self, fresh_meta):
        assert check_validation_decay(fresh_meta) is None

    def test_non_active_ignored(self, fresh_meta):
        fresh_meta.status = BeliefStatus.SUPERSEDED
        assert check_validation_decay(fresh_meta) is None


# --- Contradiction Tests ---

class TestContradiction:
    def test_synthesis_creates_child_links(self):
        a = EntryMeta(entry_id="aaa", authority=0.6)
        b = EntryMeta(entry_id="bbb", authority=0.8)
        synthesis, _ = resolve_contradiction(a, b, "a", "b", "s")
        assert synthesis.parent_ids == ["aaa", "bbb"]
        assert a.synthesis_id == synthesis.entry_id
        assert a.status == BeliefStatus.SYNTHESIZED

    def test_synthesis_inherits_max_authority(self):
        a = EntryMeta(authority=0.5)
        b = EntryMeta(authority=0.9)
        synthesis, _ = resolve_contradiction(a, b, "a", "b", "s")
        assert synthesis.authority == 0.9

    def test_synthesis_merges_scopes(self):
        a = EntryMeta(scope={"lang": "python", "project": "foo"})
        b = EntryMeta(scope={"lang": "python", "project": "bar"})
        synthesis, _ = resolve_contradiction(a, b, "a", "b", "s")
        assert synthesis.scope["lang"] == "python"
        assert synthesis.scope["project"] == "any"


# --- Serialization Tests ---

class TestSerialization:
    def test_entry_meta_roundtrip(self, fresh_meta):
        d = fresh_meta.to_dict()
        restored = EntryMeta.from_dict(d)
        assert restored.entry_id == fresh_meta.entry_id

    def test_meta_store_roundtrip(self, meta_store_with_entries):
        d = meta_store_with_entries.to_dict()
        restored = MetaStore.from_dict(d)
        assert len(restored.entries) == 3

    def test_contradiction_edge_roundtrip(self):
        edge = ContradictionEdge(from_id="a", to_id="b", reason="conflict")
        d = edge.to_dict()
        restored = ContradictionEdge.from_dict(d)
        assert restored.from_id == "a"
        assert restored.reason == "conflict"


# --- Integration Tests ---

class TestMemoryStoreIntegration:
    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        from tools.memory_tool import MemoryStore
        monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
        s = MemoryStore(memory_char_limit=2000, user_char_limit=1000)
        s.load_from_disk()
        return s

    def test_add_creates_meta(self, store):
        store.add("memory", "Python 3.12 is preferred")
        meta = store.get_entry_meta("memory", "Python 3.12 is preferred")
        assert meta is not None
        assert meta.source_kind == SourceKind.USER_EXPLICIT

    def test_meta_survives_reload(self, store, tmp_path, monkeypatch):
        store.add("memory", "test entry")
        from tools.memory_tool import MemoryStore
        store2 = MemoryStore(memory_char_limit=2000, user_char_limit=1000)
        store2.load_from_disk()
        meta = store2.get_entry_meta("memory", "test entry")
        assert meta is not None

    def test_get_contradictions_empty(self, store):
        store.add("memory", "test")
        assert store.get_contradictions("memory") == []

    def test_run_maintenance(self, store):
        store.add("memory", "stale fact")
        meta = store.get_entry_meta("memory", "stale fact")
        meta.knowledge_type = KnowledgeType.STATE
        meta.confidence = 0.15
        meta.updated_at = time.time() - 200 * 86400
        meta.last_validated_at = time.time() - 200 * 86400
        store._save_meta_to_disk("memory")
        actions = store.run_maintenance("memory")
        assert actions["decayed"] >= 1

    def test_add_with_source_kind(self, store):
        store.add("memory", "observed behavior", source_kind=SourceKind.OBSERVED)
        meta = store.get_entry_meta("memory", "observed behavior")
        assert meta.source_kind == SourceKind.OBSERVED
        assert meta.authority == SOURCE_AUTHORITY_DEFAULT[SourceKind.OBSERVED]
