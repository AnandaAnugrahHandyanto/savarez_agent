"""Semantic vector search for the enhanced-memory plugin.

Provides KNN vector search using sqlite-vec. Embedding generation is
delegated to pluggable providers (Gemini, OpenAI, local sentence-transformers).

The user configures which provider to use in config.yaml:

  plugins:
    enhanced-memory:
      embedding_provider: gemini        # "gemini", "openai", "local", "none"
      embedding_model: gemini-embedding-001
      embedding_dims: 3072
"""

from __future__ import annotations

import logging
import sqlite3
import struct
from datetime import datetime, timezone
from typing import Any

from .embedding_providers import EmbeddingProvider, create_embedding_provider

logger = logging.getLogger(__name__)

# Condensed-table IDs are mapped to negative space to avoid PK collisions
_CONDENSED_ID_OFFSET = 10_000


def _serialize_f32(vec: list[float]) -> bytes:
    """Pack a list of floats into a compact little-endian binary blob."""
    return struct.pack(f"<{len(vec)}f", *vec)


def _load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Attempt to load the sqlite-vec extension. Returns True on success."""
    try:
        import sqlite_vec  # type: ignore[import-untyped]
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except (ImportError, OSError, sqlite3.OperationalError) as exc:
        logger.debug("sqlite-vec not available: %s", exc)
        return False


class SemanticSearch:
    """Semantic vector search backed by configurable embedding providers + sqlite-vec.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database for the vec0 virtual table.
    config : dict
        Plugin config dict (used to create the embedding provider).
    provider : EmbeddingProvider | None
        Explicit provider instance (overrides config-based creation).
    """

    def __init__(
        self,
        db_path: str,
        config: dict[str, Any] | None = None,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self._db_path = db_path
        self._vec_available = False
        self._conn: sqlite3.Connection | None = None

        # Create or use provided embedding provider
        if provider is not None:
            self._provider = provider
        elif config:
            self._provider = create_embedding_provider(config)
        else:
            # Legacy: default to Gemini
            from .embedding_providers import GeminiEmbedding
            self._provider = GeminiEmbedding()

        # Open dedicated connection for vec operations
        try:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._vec_available = _load_sqlite_vec(self._conn)
        except sqlite3.Error as exc:
            logger.error("Failed to open vec database: %s", exc)
            return

        if self._vec_available and self._provider:
            self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create the vec0 virtual table and index-tracking table if needed."""
        dims = self._provider.dims if self._provider else 3072
        cur = self._conn.cursor()
        try:
            cur.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory
                USING vec0(
                    fact_id INTEGER PRIMARY KEY,
                    embedding float[{dims}]
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS vec_index_log (
                    fact_id      INTEGER PRIMARY KEY,
                    source_table TEXT NOT NULL,
                    indexed_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to create vec tables: %s", exc)
            self._vec_available = False

    def is_available(self) -> bool:
        """Return True when sqlite-vec is loaded AND embedding provider is ready."""
        return (
            self._vec_available
            and self._provider is not None
            and self._provider.is_available()
        )

    @property
    def provider_name(self) -> str:
        """Name of the active embedding provider."""
        return self._provider.name if self._provider else "none"

    @property
    def dims(self) -> int:
        """Embedding dimensions from the active provider."""
        return self._provider.dims if self._provider else 0

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_facts(self, facts: list[dict[str, Any]], source_table: str) -> int:
        """Embed facts and insert into the vec_memory table.

        Parameters
        ----------
        facts : list of dicts with 'id' (int) and 'content' (str)
        source_table : "raw_facts" or "condensed"

        Returns
        -------
        int : number of facts successfully indexed
        """
        if not facts or not self.is_available():
            return 0

        texts = [f["content"] for f in facts]
        try:
            embeddings = self._provider.embed_texts(texts)
        except Exception as exc:
            logger.error("Embedding failed during indexing: %s", exc)
            return 0

        indexed = 0
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()

        for fact, emb in zip(facts, embeddings):
            raw_id: int = fact["id"]
            vec_id = -(raw_id + _CONDENSED_ID_OFFSET) if source_table == "condensed" else raw_id
            blob = _serialize_f32(emb)

            try:
                cur.execute(
                    "INSERT OR REPLACE INTO vec_memory(fact_id, embedding) VALUES (?, ?)",
                    (vec_id, blob),
                )
                cur.execute(
                    "INSERT OR REPLACE INTO vec_index_log(fact_id, source_table, indexed_at) "
                    "VALUES (?, ?, ?)",
                    (vec_id, source_table, now),
                )
                indexed += 1
            except sqlite3.Error as exc:
                logger.warning("Failed to index fact %d (vec_id=%d): %s", raw_id, vec_id, exc)

        self._conn.commit()
        logger.info("Indexed %d/%d facts from %s", indexed, len(facts), source_table)
        return indexed

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Run a KNN vector search.

        Returns list of {fact_id, distance, similarity} sorted by distance.
        """
        if not self.is_available():
            return []

        try:
            emb = self._provider.embed_single(query)
        except Exception as exc:
            logger.error("Embedding failed during search: %s", exc)
            return []

        blob = _serialize_f32(emb)
        try:
            rows = self._conn.execute(
                "SELECT fact_id, distance FROM vec_memory "
                "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (blob, k),
            ).fetchall()
        except sqlite3.Error as exc:
            logger.error("Vec search failed: %s", exc)
            return []

        return [
            {
                "fact_id": row["fact_id"],
                "distance": row["distance"],
                "similarity": 1.0 - row["distance"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Unindexed discovery
    # ------------------------------------------------------------------

    def get_unindexed(self, conn_or_store: Any) -> dict[str, list[dict[str, Any]]]:
        """Find facts not yet indexed in vec_memory.

        Parameters
        ----------
        conn_or_store : sqlite3.Connection or object with .conn property
        """
        result: dict[str, list[dict[str, Any]]] = {"raw_facts": [], "condensed": []}
        if not self._vec_available:
            return result

        mem_conn = conn_or_store.conn if hasattr(conn_or_store, "conn") else conn_or_store

        # Collect already-indexed IDs
        indexed_raw: set[int] = set()
        indexed_condensed: set[int] = set()
        try:
            for row in self._conn.execute("SELECT fact_id, source_table FROM vec_index_log"):
                if row["source_table"] == "condensed":
                    indexed_condensed.add(row["fact_id"])
                else:
                    indexed_raw.add(row["fact_id"])
        except sqlite3.Error:
            pass

        # Raw facts
        try:
            for row in mem_conn.execute("SELECT id, content FROM raw_facts"):
                fid = row[0] if isinstance(row, (tuple, list)) else row["id"]
                content = row[1] if isinstance(row, (tuple, list)) else row["content"]
                if fid not in indexed_raw:
                    result["raw_facts"].append({"id": fid, "content": content})
        except sqlite3.Error:
            pass

        # Condensed
        try:
            for row in mem_conn.execute("SELECT id, summary FROM condensed"):
                fid = row[0] if isinstance(row, (tuple, list)) else row["id"]
                content = row[1] if isinstance(row, (tuple, list)) else row["summary"]
                vec_id = -(fid + _CONDENSED_ID_OFFSET)
                if vec_id not in indexed_condensed:
                    result["condensed"].append({"id": fid, "content": content})
        except sqlite3.Error:
            pass

        return result

    # ------------------------------------------------------------------
    # Reindex
    # ------------------------------------------------------------------

    def reindex(self, conn_or_store: Any | None = None) -> dict[str, int]:
        """Drop and rebuild the entire vector index."""
        counts: dict[str, int] = {"raw_facts": 0, "condensed": 0}
        if not self.is_available():
            return counts

        try:
            self._conn.execute("DELETE FROM vec_memory")
            self._conn.execute("DELETE FROM vec_index_log")
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.error("Failed to clear vec tables: %s", exc)
            return counts

        if conn_or_store is None:
            return counts

        mem_conn = conn_or_store.conn if hasattr(conn_or_store, "conn") else conn_or_store

        # Re-index raw facts
        try:
            rows = mem_conn.execute("SELECT id, content FROM raw_facts").fetchall()
            raw_facts = [
                {"id": r[0] if isinstance(r, (tuple, list)) else r["id"],
                 "content": r[1] if isinstance(r, (tuple, list)) else r["content"]}
                for r in rows
            ]
            if raw_facts:
                counts["raw_facts"] = self.index_facts(raw_facts, "raw_facts")
        except sqlite3.Error:
            pass

        # Re-index condensed
        try:
            rows = mem_conn.execute("SELECT id, summary FROM condensed").fetchall()
            condensed = [
                {"id": r[0] if isinstance(r, (tuple, list)) else r["id"],
                 "content": r[1] if isinstance(r, (tuple, list)) else r["summary"]}
                for r in rows
            ]
            if condensed:
                counts["condensed"] = self.index_facts(condensed, "condensed")
        except sqlite3.Error:
            pass

        return counts

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        result: dict[str, Any] = {
            "available": self.is_available(),
            "vec_loaded": self._vec_available,
            "provider": self.provider_name,
            "provider_available": self._provider.is_available() if self._provider else False,
            "embedding_dims": self.dims,
            "total_indexed": 0,
            "by_source": {},
        }

        if not self._vec_available or not self._conn:
            return result

        try:
            row = self._conn.execute("SELECT COUNT(*) FROM vec_index_log").fetchone()
            result["total_indexed"] = row[0]
        except sqlite3.Error:
            pass

        try:
            for row in self._conn.execute(
                "SELECT source_table, COUNT(*) as cnt FROM vec_index_log GROUP BY source_table"
            ):
                result["by_source"][row["source_table"]] = row["cnt"]
        except sqlite3.Error:
            pass

        return result
