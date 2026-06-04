"""Tests for the holographic MemoryStore non-destructive supersede feature.

See ~/.hermes/plans/dag-memory-extend-holographic.md for the design.
"""

import sqlite3

import pytest

from plugins.memory.holographic.retrieval import FactRetriever
from plugins.memory.holographic.store import MemoryStore


# Pre-supersede facts schema: the columns that existed before this feature,
# i.e. the current schema minus `superseded_at`. Used to build an "old" DB
# and prove the additive migration upgrades it in place.
_OLD_FACTS_DDL = """
CREATE TABLE facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content         TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'general',
    tags            TEXT DEFAULT '',
    trust_score     REAL DEFAULT 0.5,
    retrieval_count INTEGER DEFAULT 0,
    helpful_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hrr_vector      BLOB
);
"""


def _make_old_db(path: str) -> None:
    """Create a pre-supersede database with one existing fact row."""
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_FACTS_DDL)
    conn.execute(
        "INSERT INTO facts (content, category) VALUES (?, ?)",
        ("legacy fact from before the migration", "general"),
    )
    conn.commit()
    conn.close()


def _columns(store: MemoryStore, table: str) -> set:
    return {row[1] for row in store._conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _tables(store: MemoryStore) -> set:
    rows = store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


class TestSupersedeMigration:
    def test_adds_superseded_at_column(self, tmp_path):
        db = str(tmp_path / "old.db")
        _make_old_db(db)
        store = MemoryStore(db_path=db)
        assert "superseded_at" in _columns(store, "facts")

    def test_creates_fact_supersedes_table(self, tmp_path):
        db = str(tmp_path / "old.db")
        _make_old_db(db)
        store = MemoryStore(db_path=db)
        assert "fact_supersedes" in _tables(store)

    def test_preserves_existing_rows(self, tmp_path):
        db = str(tmp_path / "old.db")
        _make_old_db(db)
        store = MemoryStore(db_path=db)
        row = store._conn.execute(
            "SELECT content, superseded_at FROM facts WHERE fact_id = 1"
        ).fetchone()
        assert row["content"] == "legacy fact from before the migration"
        # Existing rows are live: superseded_at defaults to NULL.
        assert row["superseded_at"] is None


class TestRemoveFactLineageCleanup:
    """remove_fact must not leave dangling fact_supersedes rows."""

    def _seed_lineage(self, store, new_id, old_id):
        store._conn.execute(
            "INSERT INTO fact_supersedes (new_id, old_id) VALUES (?, ?)",
            (new_id, old_id),
        )
        store._conn.commit()

    def test_removing_new_id_clears_lineage(self, tmp_path):
        store = MemoryStore(db_path=str(tmp_path / "m.db"))
        old_id = store.add_fact("old version of the fact")
        new_id = store.add_fact("new version of the fact")
        self._seed_lineage(store, new_id, old_id)

        store.remove_fact(new_id)

        dangling = store._conn.execute(
            "SELECT COUNT(*) FROM fact_supersedes WHERE new_id = ? OR old_id = ?",
            (new_id, new_id),
        ).fetchone()[0]
        assert dangling == 0

    def test_removing_old_id_clears_lineage(self, tmp_path):
        store = MemoryStore(db_path=str(tmp_path / "m.db"))
        old_id = store.add_fact("old version of the fact")
        new_id = store.add_fact("new version of the fact")
        self._seed_lineage(store, new_id, old_id)

        store.remove_fact(old_id)

        dangling = store._conn.execute(
            "SELECT COUNT(*) FROM fact_supersedes WHERE new_id = ? OR old_id = ?",
            (old_id, old_id),
        ).fetchone()[0]
        assert dangling == 0


class TestSupersededRecallFilter:
    """A fact marked superseded must vanish from every default recall path
    and from its category HRR bank, while live versions still surface."""

    def _two_versions(self, tmp_path):
        store = MemoryStore(db_path=str(tmp_path / "m.db"))
        old_id = store.add_fact("Project Hermes runs on the old server alpha")
        new_id = store.add_fact("Project Hermes runs on the new server beta")
        return store, old_id, new_id

    def _mark_superseded(self, store, fact_id):
        store._conn.execute(
            "UPDATE facts SET superseded_at = CURRENT_TIMESTAMP WHERE fact_id = ?",
            (fact_id,),
        )
        store._conn.commit()
        cat = store._conn.execute(
            "SELECT category FROM facts WHERE fact_id = ?", (fact_id,)
        ).fetchone()["category"]
        store._rebuild_bank(cat)

    def test_search_facts_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        ids = [f["fact_id"] for f in store.search_facts("Project Hermes server")]
        assert old_id not in ids
        assert new_id in ids

    def test_list_facts_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        ids = [f["fact_id"] for f in store.list_facts()]
        assert old_id not in ids
        assert new_id in ids

    def test_retriever_search_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        ids = [f["fact_id"] for f in FactRetriever(store).search("Project Hermes server")]
        assert old_id not in ids
        assert new_id in ids

    def test_probe_direct_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        # No category -> hits the direct-SQL path in probe.
        ids = [f["fact_id"] for f in FactRetriever(store).probe("Project Hermes")]
        assert old_id not in ids

    def test_probe_bank_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        # Category -> hits the bank path through _score_facts_by_vector.
        ids = [f["fact_id"]
               for f in FactRetriever(store).probe("Project Hermes", category="general")]
        assert old_id not in ids

    def test_related_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        ids = [f["fact_id"] for f in FactRetriever(store).related("Hermes")]
        assert old_id not in ids

    def test_reason_excludes_superseded(self, tmp_path):
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        ids = [f["fact_id"] for f in FactRetriever(store).reason(["Hermes"])]
        assert old_id not in ids

    def test_rebuild_bank_excludes_superseded(self, tmp_path):
        # Banks only exist when numpy/HRR is available; skip otherwise.
        pytest.importorskip("numpy")
        store, old_id, new_id = self._two_versions(tmp_path)
        self._mark_superseded(store, old_id)
        row = store._conn.execute(
            "SELECT fact_count FROM memory_banks WHERE bank_name = ?", ("cat:general",)
        ).fetchone()
        # Only the live fact contributes to the bundle.
        assert row["fact_count"] == 1
