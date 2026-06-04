"""Tests for the holographic MemoryStore non-destructive supersede feature.

See ~/.hermes/plans/dag-memory-extend-holographic.md for the design.
"""

import sqlite3

import pytest

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
