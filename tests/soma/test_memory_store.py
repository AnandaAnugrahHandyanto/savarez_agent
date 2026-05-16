"""Tests for soma.memory_store — write, fuse, prune, immortals, scoring."""

from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from soma.memory_store import (
    IMMORTAL_TAGS,
    MemoryStore,
    RECENCY_HALF_LIFE_SECS,
    TYPE_WEIGHTS,
    score_record,
)


class DictEmbedder:
    """Deterministic embedder: lookup table from text → vector.

    Anything not in the table maps to a zero vector with a single 1.0 at a
    hashed slot so distinct strings get orthogonal-ish vectors. The fuse
    logic is exercised by giving deliberately-similar texts the same vector.
    """

    def __init__(self, mapping: dict | None = None, dim: int = 16):
        self.mapping = mapping or {}
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        if text in self.mapping:
            return list(self.mapping[text])
        slot = abs(hash(text)) % self.dim
        vec = [0.0] * self.dim
        vec[slot] = 1.0
        return vec


class MemoryStoreBasicsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.addCleanup(lambda: os.path.exists(self.tmp.name) and os.unlink(self.tmp.name))

    def _store(self, embedder=None, **kw):
        return MemoryStore(self.tmp.name, embedder or DictEmbedder(), **kw)

    def test_write_and_read_back(self):
        store = self._store()
        rec = store.write("User works at Supermicro", type="semantic", tags=["domain"])
        self.assertTrue(rec.id.startswith("mem_"))
        self.assertEqual(rec.content, "User works at Supermicro")
        self.assertEqual(rec.use_count, 1)

        # Persists across new instances.
        store2 = self._store()
        records = store2.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].content, "User works at Supermicro")

    def test_invalid_type_rejected(self):
        store = self._store()
        with self.assertRaises(ValueError):
            store.write("x", type="not-a-real-type")

    def test_empty_content_rejected(self):
        store = self._store()
        with self.assertRaises(ValueError):
            store.write("   ")


class MemoryStoreFuseTest(unittest.TestCase):
    """Cosine > dup_threshold → fuse (bump use_count, refresh last_seen_at)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.addCleanup(lambda: os.path.exists(self.tmp.name) and os.unlink(self.tmp.name))

    def test_identical_text_fuses(self):
        embedder = DictEmbedder({"X": [1.0, 0.0, 0.0]})
        store = MemoryStore(self.tmp.name, embedder, dup_threshold=0.80)
        a = store.write("X", now=1000.0)
        b = store.write("X", now=2000.0)
        self.assertEqual(a.id, b.id, "fused record must reuse the original id")
        self.assertEqual(b.use_count, 2)
        self.assertEqual(b.last_seen_at, 2000.0)
        self.assertEqual(len(store.all()), 1)

    def test_cross_language_near_duplicate_fuses(self):
        # Same vector simulates a cross-language semantic match.
        shared = [1.0, 0.0, 0.0]
        embedder = DictEmbedder({
            "User spricht Deutsch": shared,
            "User communicates in German": shared,
        })
        store = MemoryStore(self.tmp.name, embedder, dup_threshold=0.80)
        store.write("User spricht Deutsch", now=1000.0)
        store.write("User communicates in German", now=2000.0)
        records = store.all()
        self.assertEqual(len(records), 1)
        # Newer content wins on conflict.
        self.assertEqual(records[0].content, "User communicates in German")
        self.assertEqual(records[0].use_count, 2)

    def test_distinct_embeddings_do_not_fuse(self):
        embedder = DictEmbedder({
            "A": [1.0, 0.0, 0.0],
            "B": [0.0, 1.0, 0.0],
        })
        store = MemoryStore(self.tmp.name, embedder, dup_threshold=0.80)
        store.write("A")
        store.write("B")
        self.assertEqual(len(store.all()), 2)

    def test_below_threshold_does_not_fuse(self):
        # cos([1,0],[0.5,0.5]) ≈ 0.707 < 0.80
        embedder = DictEmbedder({
            "first":  [1.0, 0.0],
            "second": [0.5, 0.5],
        })
        store = MemoryStore(self.tmp.name, embedder, dup_threshold=0.80)
        store.write("first")
        store.write("second")
        self.assertEqual(len(store.all()), 2)

    def test_tags_merge_on_fuse(self):
        embedder = DictEmbedder({"X": [1.0, 0.0]})
        store = MemoryStore(self.tmp.name, embedder, dup_threshold=0.80)
        store.write("X", tags=["domain"])
        store.write("X", tags=["preference"])
        records = store.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(set(records[0].tags), {"domain", "preference"})


class MemoryStorePruneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.addCleanup(lambda: os.path.exists(self.tmp.name) and os.unlink(self.tmp.name))

    def _orthogonal_embedder(self, n: int) -> DictEmbedder:
        # Each text "t<i>" gets a unit vector along axis i — fully orthogonal,
        # so nothing fuses regardless of dup_threshold.
        mapping = {}
        for i in range(n):
            vec = [0.0] * n
            vec[i] = 1.0
            mapping[f"t{i}"] = vec
        return DictEmbedder(mapping, dim=n)

    def test_auto_prune_keeps_target_count_of_mortals(self):
        store = MemoryStore(
            self.tmp.name,
            self._orthogonal_embedder(12),
            max_memories=10,
            prune_target=5,
        )
        now = 1000.0
        for i in range(12):
            store.write(f"t{i}", now=now + i)
        # After breaching max=10 mid-loop, store prunes to prune_target=5.
        # Subsequent writes restore growth until next breach.
        self.assertLessEqual(len(store.all()), 10)

    def test_immortals_survive_force_prune(self):
        # max_memories large enough to avoid auto-prune during writes;
        # force-prune then has the full set to work on.
        embedder = self._orthogonal_embedder(8)
        store = MemoryStore(
            self.tmp.name,
            embedder,
            max_memories=100,
            prune_target=2,
        )
        # Two immortal, six mortal.
        for i, tag in enumerate(["identity", "domain"]):
            store.write(f"t{i}", tags=[tag])
        for i in range(2, 8):
            store.write(f"t{i}")
        removed = store.prune()
        kept = store.all()
        self.assertGreaterEqual(removed, 1, "force prune should drop at least one mortal")
        immortals_kept = [r for r in kept if r.is_immortal()]
        self.assertEqual(len(immortals_kept), 2)
        immortal_tags = {tag for r in immortals_kept for tag in r.tags}
        self.assertEqual(immortal_tags, {"identity", "domain"})

    def test_prune_keeps_higher_scoring_mortals(self):
        # Same vector dim for all — but distinct slots → no fuse.
        embedder = self._orthogonal_embedder(5)
        store = MemoryStore(
            self.tmp.name,
            embedder,
            max_memories=4,
            prune_target=2,
        )
        # Write 5 mortals; older ones score lower (recency decay).
        now = 10_000_000.0
        store.write("t0", now=now - 3 * RECENCY_HALF_LIFE_SECS)  # very old
        store.write("t1", now=now - 2 * RECENCY_HALF_LIFE_SECS)
        store.write("t2", now=now - 1 * RECENCY_HALF_LIFE_SECS)
        store.write("t3", now=now)
        store.write("t4", now=now)
        store.prune(now=now)
        kept_contents = {r.content for r in store.all()}
        # Newest two must be kept; oldest must be gone.
        self.assertIn("t3", kept_contents)
        self.assertIn("t4", kept_contents)
        self.assertNotIn("t0", kept_contents)


class ScoreRecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.addCleanup(lambda: os.path.exists(self.tmp.name) and os.unlink(self.tmp.name))

    _slot_counter = 0

    def _record(self, content="x", **kw):
        # Each call gets a unique orthogonal slot so writes never fuse
        # across calls within a test method.
        ScoreRecordTest._slot_counter += 1
        slot = ScoreRecordTest._slot_counter
        vec = [0.0] * 32
        vec[slot % 32] = 1.0
        embedder = DictEmbedder({content: vec})
        store = MemoryStore(self.tmp.name, embedder)
        return store.write(content, now=kw.pop("now", 1000.0), **kw)

    def test_immortal_score_is_inf(self):
        rec = self._record(tags=["identity"])
        self.assertEqual(score_record(rec, now=1000.0), math.inf)

    def test_recency_decay_halves_at_half_life(self):
        rec = self._record(now=0.0)
        rec.use_count = 1
        s_now = score_record(rec, now=0.0)
        s_one_half_life = score_record(rec, now=RECENCY_HALF_LIFE_SECS)
        # Recency factor halves; frequency & type-weight constant.
        self.assertAlmostEqual(s_one_half_life / s_now, 0.5, places=5)

    def test_procedural_outweighs_episodic(self):
        # Distinct content → distinct embedding slots → no fuse.
        proc = self._record(content="proc-text", type="procedural", now=1000.0)
        epi = self._record(content="epi-text", type="episodic", now=1000.0)
        self.assertGreater(TYPE_WEIGHTS["procedural"], TYPE_WEIGHTS["episodic"])
        self.assertGreater(
            score_record(proc, now=1000.0),
            score_record(epi, now=1000.0),
        )


class ImmortalTagsTest(unittest.TestCase):
    def test_set_matches_plan(self):
        self.assertEqual(
            IMMORTAL_TAGS,
            frozenset({"domain", "role", "identity", "preference", "behavior"}),
        )


if __name__ == "__main__":
    unittest.main()
