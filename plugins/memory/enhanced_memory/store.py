"""Enhanced Memory Store — two-tier SQLite backend with FTS5 full-text search.

Provides a durable, thread-safe storage layer for the Hermes Agent enhanced-memory
plugin.  Raw conversational facts are stored in ``raw_facts`` and periodically
condensed into higher-level summaries in ``condensed``.  Both tables are backed by
FTS5 virtual tables with automatic trigger-based synchronisation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES: set[str] = {
    "user_pref",
    "project",
    "tool",
    "env",
    "decision",
    "security",
    "general",
}

_DEFAULT_DB_NAME = "memory_store.db"


def _default_db_path() -> str:
    """Return the default database path, preferring hermes_constants if available."""
    try:
        from hermes_constants import get_hermes_home  # type: ignore[import-untyped]

        base = get_hermes_home()
    except Exception:
        base = os.path.join(Path.home(), ".hermes")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _DEFAULT_DB_NAME)


# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

_SCHEMA_RAW_FACTS = """\
CREATE TABLE IF NOT EXISTS raw_facts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT    NOT NULL,
    category   TEXT    NOT NULL DEFAULT 'general',
    source     TEXT    NOT NULL DEFAULT '',
    session_id TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL,
    condensed  INTEGER NOT NULL DEFAULT 0
);
"""

_SCHEMA_CONDENSED = """\
CREATE TABLE IF NOT EXISTS condensed (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    topic      TEXT    NOT NULL,
    summary    TEXT    NOT NULL,
    category   TEXT    NOT NULL DEFAULT 'general',
    priority   INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    source_ids TEXT    NOT NULL DEFAULT '[]',
    fact_count INTEGER NOT NULL DEFAULT 0,
    version    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);
"""

_SCHEMA_FTS_RAW = """\
CREATE VIRTUAL TABLE IF NOT EXISTS raw_facts_fts
USING fts5(content, category, source, content=raw_facts, content_rowid=id);
"""

_SCHEMA_FTS_CONDENSED = """\
CREATE VIRTUAL TABLE IF NOT EXISTS condensed_fts
USING fts5(topic, summary, category, content=condensed, content_rowid=id);
"""

# Triggers keep FTS tables in sync with content tables.
# We use the recommended "external content" approach from the SQLite FTS5 docs.

_TRIGGERS_RAW = [
    """\
CREATE TRIGGER IF NOT EXISTS raw_facts_ai AFTER INSERT ON raw_facts BEGIN
    INSERT INTO raw_facts_fts(rowid, content, category, source)
    VALUES (new.id, new.content, new.category, new.source);
END;
""",
    """\
CREATE TRIGGER IF NOT EXISTS raw_facts_ad AFTER DELETE ON raw_facts BEGIN
    INSERT INTO raw_facts_fts(raw_facts_fts, rowid, content, category, source)
    VALUES ('delete', old.id, old.content, old.category, old.source);
END;
""",
    """\
CREATE TRIGGER IF NOT EXISTS raw_facts_au AFTER UPDATE ON raw_facts BEGIN
    INSERT INTO raw_facts_fts(raw_facts_fts, rowid, content, category, source)
    VALUES ('delete', old.id, old.content, old.category, old.source);
    INSERT INTO raw_facts_fts(rowid, content, category, source)
    VALUES (new.id, new.content, new.category, new.source);
END;
""",
]

_TRIGGERS_CONDENSED = [
    """\
CREATE TRIGGER IF NOT EXISTS condensed_ai AFTER INSERT ON condensed BEGIN
    INSERT INTO condensed_fts(rowid, topic, summary, category)
    VALUES (new.id, new.topic, new.summary, new.category);
END;
""",
    """\
CREATE TRIGGER IF NOT EXISTS condensed_ad AFTER DELETE ON condensed BEGIN
    INSERT INTO condensed_fts(condensed_fts, rowid, topic, summary, category)
    VALUES ('delete', old.id, old.topic, old.summary, old.category);
END;
""",
    """\
CREATE TRIGGER IF NOT EXISTS condensed_au AFTER UPDATE ON condensed BEGIN
    INSERT INTO condensed_fts(condensed_fts, rowid, topic, summary, category)
    VALUES ('delete', old.id, old.topic, old.summary, old.category);
    INSERT INTO condensed_fts(rowid, topic, summary, category)
    VALUES (new.id, new.topic, new.summary, new.category);
END;
""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_raw_facts_category ON raw_facts(category);",
    "CREATE INDEX IF NOT EXISTS idx_raw_facts_condensed ON raw_facts(condensed);",
    "CREATE INDEX IF NOT EXISTS idx_raw_facts_session ON raw_facts(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_facts_created ON raw_facts(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_condensed_category ON condensed(category);",
    "CREATE INDEX IF NOT EXISTS idx_condensed_topic ON condensed(topic);",
    "CREATE INDEX IF NOT EXISTS idx_condensed_priority ON condensed(priority DESC);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_condensed_topic_cat ON condensed(topic, category);",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    """ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_category(category: str) -> str:
    """Return *category* if valid, else fall back to ``'general'``."""
    if category in VALID_CATEGORIES:
        return category
    logger.warning("Invalid category %r, falling back to 'general'", category)
    return "general"


def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class EnhancedMemoryStore:
    """Two-tier SQLite memory store with FTS5 full-text search.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  When *None* the default path
        derived from ``hermes_constants.get_hermes_home()`` (or
        ``~/.hermes/memory_store.db``) is used.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path: str = db_path or _default_db_path()
        self._lock = threading.Lock()
        self._local = threading.local()
        logger.info("EnhancedMemoryStore using db: %s", self._db_path)
        # Ensure schema exists on construction.
        self._init_schema()

    # -- connection helpers -------------------------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """Public access to the per-thread connection (used by condenser/embeddings)."""
        return self._get_conn()

    @property
    def conn(self) -> sqlite3.Connection:
        """Property alias for get_connection (used by embeddings module)."""
        return self._get_conn()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a per-thread connection (created lazily)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    @contextmanager
    def _write_tx(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that serialises writes and wraps them in a transaction."""
        conn = self._get_conn()
        with self._lock:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def _read_tx(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for read-only access (no lock required with WAL)."""
        conn = self._get_conn()
        yield conn

    # -- schema -------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create tables, FTS virtual tables, triggers, and indexes if missing."""
        with self._write_tx() as conn:
            # Core tables
            conn.execute(_SCHEMA_RAW_FACTS)
            conn.execute(_SCHEMA_CONDENSED)
            # FTS5 virtual tables
            conn.execute(_SCHEMA_FTS_RAW)
            conn.execute(_SCHEMA_FTS_CONDENSED)
            # Triggers
            for trigger_sql in _TRIGGERS_RAW + _TRIGGERS_CONDENSED:
                conn.execute(trigger_sql)
            # Indexes
            for idx_sql in _INDEXES:
                conn.execute(idx_sql)
        logger.debug("Schema initialisation complete.")

    # -- raw_facts CRUD -----------------------------------------------------

    def add_raw_fact(
        self,
        content: str,
        category: str = "general",
        source: str = "",
        session_id: str = "",
    ) -> int:
        """Insert a single raw fact and return its id.

        Parameters
        ----------
        content:   The fact text.
        category:  One of :data:`VALID_CATEGORIES`.
        source:    Free-form provenance string (e.g. ``"chat"``).
        session_id: Identifier for the originating session.

        Returns
        -------
        int
            The ``rowid`` of the newly inserted fact.
        """
        category = _validate_category(category)
        now = _utcnow()
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO raw_facts (content, category, source, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?);",
                (content, category, source, session_id, now),
            )
            rowid = cur.lastrowid
        logger.debug("Added raw fact id=%s category=%s", rowid, category)
        return rowid  # type: ignore[return-value]

    def add_raw_facts_batch(self, facts: list[dict[str, Any]]) -> list[int]:
        """Insert multiple raw facts in a single transaction.

        Each dict in *facts* may contain keys: ``content`` (required),
        ``category``, ``source``, ``session_id``.

        Returns
        -------
        list[int]
            The list of inserted rowids, in the same order as *facts*.
        """
        if not facts:
            return []
        now = _utcnow()
        ids: list[int] = []
        with self._write_tx() as conn:
            for fact in facts:
                content = fact.get("content")
                if not content:
                    logger.warning("Skipping fact with empty content: %s", fact)
                    continue
                category = _validate_category(fact.get("category", "general"))
                source = fact.get("source", "")
                session_id = fact.get("session_id", "")
                cur = conn.execute(
                    "INSERT INTO raw_facts (content, category, source, session_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (content, category, source, session_id, now),
                )
                ids.append(cur.lastrowid)  # type: ignore[arg-type]
        logger.debug("Batch-inserted %d raw facts", len(ids))
        return ids

    def get_raw_by_id(self, fact_id: int) -> dict[str, Any] | None:
        """Retrieve a single raw fact by ID."""
        with self._read_tx() as conn:
            row = conn.execute(
                "SELECT id, content, category, source, session_id, created_at, condensed "
                "FROM raw_facts WHERE id = ?",
                (fact_id,),
            ).fetchone()
        if not row:
            return None
        return dict(zip(
            ("id", "content", "category", "source", "session_id", "created_at", "condensed"),
            row,
        ))

    def get_condensed_by_id(self, condensed_id: int) -> dict[str, Any] | None:
        """Retrieve a single condensed entry by ID."""
        with self._read_tx() as conn:
            row = conn.execute(
                "SELECT id, topic, summary, category, priority, source_ids, "
                "fact_count, version, created_at, updated_at "
                "FROM condensed WHERE id = ?",
                (condensed_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(zip(
            ("id", "topic", "summary", "category", "priority", "source_ids",
             "fact_count", "version", "created_at", "updated_at"),
            row,
        ))
        try:
            d["source_ids"] = json.loads(d["source_ids"]) if d["source_ids"] else []
        except (json.JSONDecodeError, TypeError):
            d["source_ids"] = []
        return d

    def search_raw(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search over raw facts.

        Parameters
        ----------
        query:  FTS5 match expression (e.g. ``"python OR rust"``).
        limit:  Maximum number of results.

        Returns
        -------
        list[dict]
            Matching rows ordered by FTS5 rank (best first).
        """
        if not query or not query.strip():
            return []
        with self._read_tx() as conn:
            cur = conn.execute(
                "SELECT rf.* FROM raw_facts rf "
                "JOIN raw_facts_fts fts ON rf.id = fts.rowid "
                "WHERE raw_facts_fts MATCH ? "
                "ORDER BY fts.rank "
                "LIMIT ?;",
                (query, limit),
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def list_uncondensed(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return raw facts that have not yet been condensed.

        Results are ordered oldest-first so the condenser processes them
        chronologically.
        """
        with self._read_tx() as conn:
            cur = conn.execute(
                "SELECT * FROM raw_facts WHERE condensed = 0 "
                "ORDER BY created_at ASC LIMIT ?;",
                (limit,),
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def mark_condensed(self, fact_ids: list[int]) -> None:
        """Mark the given raw fact ids as condensed.

        Parameters
        ----------
        fact_ids:
            List of ``raw_facts.id`` values to mark.
        """
        if not fact_ids:
            return
        placeholders = ",".join("?" for _ in fact_ids)
        with self._write_tx() as conn:
            conn.execute(
                f"UPDATE raw_facts SET condensed = 1 WHERE id IN ({placeholders});",
                fact_ids,
            )
        logger.debug("Marked %d facts as condensed", len(fact_ids))

    # -- condensed CRUD -----------------------------------------------------

    def add_condensed(
        self,
        topic: str,
        summary: str,
        category: str = "general",
        priority: int = 5,
        source_ids: list[int] | None = None,
        fact_count: int = 0,
    ) -> int:
        """Insert a new condensed summary.

        Parameters
        ----------
        topic:      Short topic label (should be unique per category).
        summary:    The condensed summary text.
        category:   One of :data:`VALID_CATEGORIES`.
        priority:   Importance ranking 1-10 (10 = highest).
        source_ids: Raw-fact ids that contributed to this summary.
        fact_count: Number of raw facts that were condensed.

        Returns
        -------
        int
            The ``rowid`` of the inserted summary.
        """
        category = _validate_category(category)
        priority = max(1, min(10, priority))
        now = _utcnow()
        source_ids_json = json.dumps(source_ids or [])
        with self._write_tx() as conn:
            cur = conn.execute(
                "INSERT INTO condensed "
                "(topic, summary, category, priority, source_ids, fact_count, version, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?);",
                (topic, summary, category, priority, source_ids_json, fact_count, now, now),
            )
            rowid = cur.lastrowid
        logger.debug("Added condensed id=%s topic=%r", rowid, topic)
        return rowid  # type: ignore[return-value]

    def update_condensed(
        self,
        id: int,
        summary: str,
        source_ids: list[int] | None = None,
        fact_count: int | None = None,
        priority: int | None = None,
    ) -> None:
        """Update an existing condensed summary in-place.

        Only the provided non-``None`` fields are changed.  The ``version``
        counter is automatically incremented and ``updated_at`` refreshed.

        Parameters
        ----------
        id:         Row id of the condensed record.
        summary:    New summary text.
        source_ids: Updated list of contributing raw-fact ids.
        fact_count: Updated count.
        priority:   Updated priority (clamped 1-10).
        """
        now = _utcnow()
        sets: list[str] = ["summary = ?", "updated_at = ?", "version = version + 1"]
        params: list[Any] = [summary, now]

        if source_ids is not None:
            sets.append("source_ids = ?")
            params.append(json.dumps(source_ids))
        if fact_count is not None:
            sets.append("fact_count = ?")
            params.append(fact_count)
        if priority is not None:
            sets.append("priority = ?")
            params.append(max(1, min(10, priority)))

        params.append(id)
        sql = f"UPDATE condensed SET {', '.join(sets)} WHERE id = ?;"
        with self._write_tx() as conn:
            conn.execute(sql, params)
        logger.debug("Updated condensed id=%s", id)

    def get_condensed(self, topic: str, category: str = "general") -> dict[str, Any] | None:
        """Retrieve a single condensed record by topic and category.

        Returns
        -------
        dict or None
            The matching row, or ``None`` if not found.
        """
        category = _validate_category(category)
        with self._read_tx() as conn:
            cur = conn.execute(
                "SELECT * FROM condensed WHERE topic = ? AND category = ? LIMIT 1;",
                (topic, category),
            )
            row = cur.fetchone()
            if row is None:
                return None
            result = _row_to_dict(cur, row)
            # Deserialise source_ids for the caller.
            result["source_ids"] = json.loads(result.get("source_ids", "[]"))
            return result

    def search_condensed(
        self,
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search condensed summaries with optional FTS and/or category filter.

        Parameters
        ----------
        query:    FTS5 match expression (optional).
        category: Filter by category (optional).
        limit:    Maximum results.

        Returns
        -------
        list[dict]
            Matching rows ordered by priority DESC then FTS rank.
        """
        conditions: list[str] = []
        params: list[Any] = []

        use_fts = bool(query and query.strip())

        if use_fts:
            base = (
                "SELECT c.* FROM condensed c "
                "JOIN condensed_fts fts ON c.id = fts.rowid "
                "WHERE condensed_fts MATCH ?"
            )
            params.append(query)
        else:
            base = "SELECT * FROM condensed c WHERE 1=1"

        if category:
            category = _validate_category(category)
            conditions.append("c.category = ?")
            params.append(category)

        where_extra = (" AND " + " AND ".join(conditions)) if conditions else ""
        order = "ORDER BY c.priority DESC" + (", fts.rank" if use_fts else ", c.updated_at DESC")
        sql = f"{base}{where_extra} {order} LIMIT ?;"
        params.append(limit)

        with self._read_tx() as conn:
            cur = conn.execute(sql, params)
            results = []
            for row in cur.fetchall():
                d = _row_to_dict(cur, row)
                d["source_ids"] = json.loads(d.get("source_ids", "[]"))
                results.append(d)
            return results

    def list_condensed(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return condensed summaries sorted by priority (highest first).

        Parameters
        ----------
        limit: Maximum number of results.
        """
        with self._read_tx() as conn:
            cur = conn.execute(
                "SELECT * FROM condensed ORDER BY priority DESC, updated_at DESC LIMIT ?;",
                (limit,),
            )
            results = []
            for row in cur.fetchall():
                d = _row_to_dict(cur, row)
                d["source_ids"] = json.loads(d.get("source_ids", "[]"))
                results.append(d)
            return results

    # -- statistics ---------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the memory store.

        Returns
        -------
        dict
            Keys: ``raw_total``, ``raw_uncondensed``, ``condensed_total``,
            ``categories`` (dict of category → count for raw facts),
            ``db_path``, ``db_size_bytes``.
        """
        with self._read_tx() as conn:
            raw_total = conn.execute("SELECT COUNT(*) FROM raw_facts;").fetchone()[0]
            raw_uncondensed = conn.execute(
                "SELECT COUNT(*) FROM raw_facts WHERE condensed = 0;"
            ).fetchone()[0]
            condensed_total = conn.execute("SELECT COUNT(*) FROM condensed;").fetchone()[0]

            cat_rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM raw_facts GROUP BY category;"
            ).fetchall()
            categories = {row["category"]: row["cnt"] for row in cat_rows}

        db_size: int = 0
        try:
            db_size = os.path.getsize(self._db_path)
        except OSError:
            pass

        return {
            "raw_total": raw_total,
            "raw_uncondensed": raw_uncondensed,
            "condensed_total": condensed_total,
            "categories": categories,
            "db_path": self._db_path,
            "db_size_bytes": db_size,
        }

    # -- housekeeping -------------------------------------------------------

    def close(self) -> None:
        """Close the current thread's database connection if open."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    def __repr__(self) -> str:
        return f"<EnhancedMemoryStore db={self._db_path!r}>"
