"""Local SQLite backing store for the LangMem memory provider.

Hermes owns persistence; LangMem only does extraction/consolidation.

Schema:
  memories      — primary row store, soft-delete via ``deleted_at``
  memories_fts  — FTS5 virtual table mirroring ``content`` column

Conservative reconciliation rules:
  - upsert whatever LangMem returns as inserts/updates
  - only soft-delete rows when LangMem explicitly marks them for deletion
  - NEVER infer deletion from omission (no replace_all)
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def _score_row(row: dict) -> float:
    """Score a retrieved memory row using lightweight local metadata."""
    try:
        meta = json.loads(row.get("metadata_json") or "{}")
    except Exception:
        meta = {}
    try:
        confirmations = float(meta.get("confirmation_count", 1))
    except Exception:
        confirmations = 1.0
    try:
        updated_at = float(row.get("updated_at") or 0)
    except Exception:
        updated_at = 0.0
    recency_hours = max((time.time() - updated_at) / 3600.0, 0.0)
    recency_bonus = max(0.0, 48.0 - recency_hours) / 48.0
    return confirmations + recency_bonus


def _merge_metadata(existing_json: Optional[str], incoming: dict, *, session_id: Optional[str]) -> dict:
    """Merge provenance metadata conservatively across updates."""
    try:
        existing = json.loads(existing_json) if existing_json else {}
    except Exception:
        existing = {}

    merged = dict(existing)
    merged.update(incoming or {})

    first_seen = existing.get("first_seen_session_id") or session_id
    if first_seen:
        merged["first_seen_session_id"] = first_seen

    if session_id:
        merged["last_seen_session_id"] = session_id

    prior_count = existing.get("confirmation_count", 0)
    try:
        prior_count = int(prior_count)
    except Exception:
        prior_count = 0
    merged["confirmation_count"] = max(prior_count, 0) + 1

    return merged


class LangMemStore:
    """Thread-compatible SQLite store for durable memories.

    Uses WAL mode for concurrent readers.  All operations are synchronous
    (called from background threads by the provider).
    """

    # DDL split into individual statements — triggers use BEGIN...END
    # which contain semicolons, so we can't do a simple split(";").
    _DDL_STATEMENTS = [
        """
        CREATE TABLE IF NOT EXISTS memories (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            kind          TEXT NOT NULL DEFAULT 'memory',
            content       TEXT NOT NULL,
            source        TEXT NOT NULL DEFAULT 'langmem',
            created_at    REAL NOT NULL,
            updated_at    REAL NOT NULL,
            deleted_at    REAL,
            last_session_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """,
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content,
            content=memories,
            content_rowid=rowid
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES ('delete', old.rowid, old.content);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES ('delete', old.rowid, old.content);
            INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
        END
        """,
    ]

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        for stmt in self._DDL_STATEMENTS:
            self._conn.execute(stmt)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_many(
        self,
        user_id: str,
        items: List[Dict[str, Any]],
        *,
        session_id: Optional[str] = None,
    ) -> None:
        """Insert or update memory rows.

        Each item must have at minimum a ``content`` key.
        If ``id`` is absent, a new UUID is generated.
        """
        now = time.time()
        for item in items:
            mem_id = item.get("id") or str(uuid.uuid4())
            content = item.get("content", "")
            kind = item.get("kind", "memory")
            source = item.get("source", "langmem")
            existing_row = self.get_memory(user_id, mem_id)
            merged_metadata = _merge_metadata(
                existing_row.get("metadata_json") if existing_row else None,
                item.get("metadata", {}),
                session_id=session_id,
            )
            metadata = json.dumps(merged_metadata, sort_keys=True)

            self._conn.execute(
                """
                INSERT INTO memories
                    (id, user_id, kind, content, source,
                     created_at, updated_at, deleted_at, last_session_id, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content         = excluded.content,
                    kind            = excluded.kind,
                    updated_at      = excluded.updated_at,
                    deleted_at      = NULL,
                    last_session_id = excluded.last_session_id,
                    metadata_json   = excluded.metadata_json
                """,
                (mem_id, user_id, kind, content, source, now, now, session_id, metadata),
            )
        self._conn.commit()

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Soft-delete a single memory row by ID (user-scoped)."""
        now = time.time()
        cur = self._conn.execute(
            "UPDATE memories SET deleted_at = ? WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (now, memory_id, user_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def reconcile_many(
        self,
        user_id: str,
        upserts: List[Dict[str, Any]],
        delete_ids: List[str],
        *,
        session_id: Optional[str] = None,
    ) -> None:
        """Apply a set of LangMem extraction decisions conservatively.

        - upserts: rows to insert or update (from LangMem insert/update actions)
        - delete_ids: IDs to soft-delete (from LangMem explicit delete actions ONLY)

        Never infers deletion from omission — only rows in ``delete_ids`` are
        soft-deleted.  This preserves memories from older sessions even when
        LangMem doesn't echo them back.
        """
        if upserts:
            self.upsert_many(user_id, upserts, session_id=session_id)
        now = time.time()
        for mem_id in delete_ids:
            self._conn.execute(
                "UPDATE memories SET deleted_at = ? "
                "WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
                (now, mem_id, user_id),
            )
        if delete_ids:
            self._conn.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_memories(
        self,
        user_id: str,
        *,
        limit: int = 200,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return all (non-deleted) memories for a user, newest-first."""
        if include_deleted:
            cur = self._conn.execute(
                "SELECT * FROM memories WHERE user_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM memories WHERE user_id = ? AND deleted_at IS NULL "
                "ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            )
        return [dict(row) for row in cur.fetchall()]

    def search_memories(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """FTS5 search over non-deleted memories for a user.

        Falls back to LIKE if the FTS query cannot be tokenized safely
        (e.g. single-character queries or special-character terms).
        """
        if not query or not query.strip():
            return []

        # Sanitize for FTS5 — remove characters that cause parse errors
        fts_query = _sanitize_fts_query(query)

        if fts_query:
            try:
                cur = self._conn.execute(
                    """
                    SELECT m.*
                    FROM memories m
                    JOIN memories_fts f ON m.rowid = f.rowid
                    WHERE f.content MATCH ?
                      AND m.user_id = ?
                      AND m.deleted_at IS NULL
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, user_id, limit),
                )
                rows = [dict(row) for row in cur.fetchall()]
                rows.sort(key=_score_row, reverse=True)
                if rows:
                    return rows[:limit]
            except sqlite3.OperationalError:
                pass  # fall through to LIKE

        # LIKE fallback
        pattern = f"%{query}%"
        cur = self._conn.execute(
            "SELECT * FROM memories "
            "WHERE user_id = ? AND deleted_at IS NULL AND content LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (user_id, pattern, limit),
        )
        rows = [dict(row) for row in cur.fetchall()]
        rows.sort(key=_score_row, reverse=True)
        return rows[:limit]

    def get_memory(self, user_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single memory row (non-deleted) by ID."""
        cur = self._conn.execute(
            "SELECT * FROM memories WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (memory_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_profile(self, user_id: str) -> Optional[dict]:
        """Fetch the structured per-user profile if present."""
        row = self.get_memory(user_id, f"profile:{user_id}")
        if not row:
            return None
        try:
            return json.loads(row["content"])
        except Exception:
            return None

    def upsert_profile(self, user_id: str, profile: dict, *, session_id: str = "") -> None:
        """Store a single structured profile document for a user."""
        self.upsert_many(
            user_id,
            [{
                "id": f"profile:{user_id}",
                "kind": "profile",
                "content": json.dumps(profile, sort_keys=True),
                "source": "langmem-profile",
                "metadata": {
                    "lane": "profile",
                    "source_type": "profile_sync",
                    "first_seen_session_id": session_id,
                    "last_seen_session_id": session_id,
                    "confirmation_count": 1,
                    "tags": ["profile"],
                },
            }],
            session_id=session_id,
        )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_fts_query(query: str) -> str:
    """Return an FTS5-safe query string, or empty string if not usable.

    FTS5 is finicky about: single characters, special chars, leading AND/OR/NOT,
    mismatched quotes.  We keep it simple: strip obvious special chars and bail
    if what's left is too short.
    """
    import re
    # Remove FTS5 special characters except spaces
    cleaned = re.sub(r'["\'^*(){}[\]<>=!|&]', " ", query).strip()
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    # If only 1 char or empty, FTS5 won't help
    if len(cleaned) < 2:
        return ""
    # Multi-word: use AND so all terms must appear (avoids single-common-word false positives)
    if " " in cleaned:
        terms = [t for t in cleaned.split() if len(t) >= 2]
        if not terms:
            return ""
        return " AND ".join(terms)
    return cleaned
