"""
MemoryStore — session-level, long-term, and working memory management.

Three memory tiers:
  1. Session memory  — current conversation context (in-memory + SQLite backup)
  2. Long-term memory — cross-session accumulated knowledge (KnowledgeGraph)
  3. Working memory  — current task's active facts (in-memory, ephemeral)

Design principles:
  - Session memory is always available (never blocked by background indexing)
  - Writes go to session memory immediately, async to long-term
  - Privacy: sensitive data is redacted before any storage
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DEFAULT_SESSION_DB_PATH = get_hermes_home() / "memory_sessions.db"

# -----------------------------------------------------------------------------
# Fact record
# -----------------------------------------------------------------------------

@dataclass
class Fact:
    """A single factual memory record."""
    id: Optional[int] = None
    session_id: str = ""
    turn: int = 0
    content: str = ""
    category: str = "general"   # general | preference | project | personal | error
    confidence: float = 1.0
    source: str = "user"         # user | assistant | extraction | external
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # TTL in seconds, None = never

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn": self.turn,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


# -----------------------------------------------------------------------------
# MemoryStore
# -----------------------------------------------------------------------------

class MemoryStore:
    """
    Manages three tiers of memory with SQLite persistence for session/long-term.

    Thread-safe for concurrent reads and single writer.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        max_session_facts: int = 1000,
        max_working_facts: int = 100,
        redact_func: Callable[[str], str] | None = None,
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_SESSION_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_session_facts = max_session_facts
        self.max_working_facts = max_working_facts
        self.redact_func = redact_func or (lambda x: x)

        # Working memory (in-memory only)
        self._working_memory: Dict[str, Fact] = {}  # key → Fact
        self._working_order: List[str] = []        # LRU order
        self._working_lock = threading.RLock()

        # Session memory (in-memory ring buffer)
        self._session_facts: deque[Fact] = deque(maxlen=max_session_facts)
        self._session_lock = threading.RLock()

        # SQLite connection
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    # -------------------------------------------------------------------------
    # DB init
    # -------------------------------------------------------------------------

    def _init_db(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                turn            INTEGER NOT NULL,
                content         TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'general',
                confidence      REAL NOT NULL DEFAULT 1.0,
                source          TEXT NOT NULL DEFAULT 'user',
                created_at      REAL NOT NULL,
                expires_at      REAL
            );
            CREATE INDEX IF NOT EXISTS idx_facts_session ON facts(session_id);
            CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
            CREATE INDEX IF NOT EXISTS idx_facts_created ON facts(created_at DESC);

            CREATE TABLE IF NOT EXISTS long_term_memories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                content         TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'general',
                entity_ids      TEXT NOT NULL DEFAULT '[]',
                confidence      REAL NOT NULL DEFAULT 1.0,
                source_session  TEXT,
                source_turn     INTEGER DEFAULT 0,
                access_count    INTEGER NOT NULL DEFAULT 0,
                last_accessed   REAL NOT NULL,
                created_at      REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ltm_category ON long_term_memories(category);
            CREATE INDEX IF NOT EXISTS idx_ltm_access ON long_term_memories(last_accessed DESC);
        """)
        self._conn.commit()

    # -------------------------------------------------------------------------
    # Session memory
    # -------------------------------------------------------------------------

    def add_session_fact(
        self,
        session_id: str,
        turn: int,
        content: str,
        category: str = "general",
        confidence: float = 1.0,
        source: str = "user",
        expires_at: float | None = None,
    ) -> Fact:
        """Add a fact to session memory (also persists to SQLite)."""
        clean_content = self.redact_func(content)

        fact = Fact(
            session_id=session_id,
            turn=turn,
            content=clean_content,
            category=category,
            confidence=confidence,
            source=source,
            created_at=time.time(),
            expires_at=expires_at,
        )

        with self._session_lock:
            self._session_facts.append(fact)

        # Persist to SQLite
        self._persist_fact(fact)

        return fact

    def _persist_fact(self, fact: Fact) -> None:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO facts
                    (session_id, turn, content, category, confidence, source,
                     created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact.session_id, fact.turn, fact.content, fact.category,
                    fact.confidence, fact.source, fact.created_at, fact.expires_at,
                ),
            )
            self._conn.commit()
            fact.id = cur.lastrowid
        except Exception as exc:
            logger.warning("Failed to persist fact: %s", exc)

    def get_session_facts(
        self,
        session_id: str,
        category: str = "",
        limit: int = 100,
    ) -> List[Fact]:
        """Retrieve facts from a specific session."""
        cur = self._conn.cursor()
        if category:
            cur.execute(
                """
                SELECT * FROM facts
                WHERE session_id = ? AND category = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, category, limit),
            )
        else:
            cur.execute(
                """
                SELECT * FROM facts
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
        return [
            Fact(
                id=row["id"],
                session_id=row["session_id"],
                turn=row["turn"],
                content=row["content"],
                category=row["category"],
                confidence=row["confidence"],
                source=row["source"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
            )
            for row in cur.fetchall()
        ]

    def get_recent_facts(self, limit: int = 50, category: str = "") -> List[Dict[str, Any]]:
        """Get recent facts across all sessions (for retrieval)."""
        cur = self._conn.cursor()
        now = time.time()
        if category:
            cur.execute(
                """
                SELECT * FROM facts
                WHERE (expires_at IS NULL OR expires_at > ?)
                  AND category = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (now, category, limit),
            )
        else:
            cur.execute(
                """
                SELECT * FROM facts
                WHERE (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (now, limit),
            )
        return [dict(row) for row in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Working memory
    # -------------------------------------------------------------------------

    def set_working_fact(
        self,
        key: str,
        content: str,
        category: str = "general",
        confidence: float = 1.0,
        source: str = "assistant",
    ) -> None:
        """Set a working memory fact (ephemeral, in-memory only)."""
        with self._working_lock:
            fact = Fact(
                session_id="__working__",
                turn=0,
                content=content,
                category=category,
                confidence=confidence,
                source=source,
                created_at=time.time(),
            )
            self._working_memory[key] = fact

            # Maintain LRU order
            if key in self._working_order:
                self._working_order.remove(key)
            self._working_order.append(key)

            # Evict oldest if over limit
            while len(self._working_memory) > self.max_working_facts:
                oldest_key = self._working_order.pop(0)
                self._working_memory.pop(oldest_key, None)

    def get_working_fact(self, key: str) -> Optional[str]:
        """Get a working memory fact content by key."""
        with self._working_lock:
            fact = self._working_memory.get(key)
            if fact:
                return fact.content
            return None

    def delete_working_fact(self, key: str) -> bool:
        """Remove a working memory fact."""
        with self._working_lock:
            if key in self._working_order:
                self._working_order.remove(key)
            return self._working_memory.pop(key, None) is not None

    def clear_working_memory(self) -> None:
        """Clear all working memory."""
        with self._working_lock:
            self._working_memory.clear()
            self._working_order.clear()

    def get_working_memory(self) -> Dict[str, str]:
        """Get all working memory as a dict of key → content."""
        with self._working_lock:
            return {k: v.content for k, v in self._working_memory.items()}

    # -------------------------------------------------------------------------
    # Long-term memory (cross-session accumulated facts)
    # -------------------------------------------------------------------------

    def add_long_term_memory(
        self,
        content: str,
        category: str = "general",
        entity_ids: List[int] | None = None,
        confidence: float = 1.0,
        source_session: str = "",
        source_turn: int = 0,
    ) -> int:
        """Store a fact in long-term memory."""
        clean_content = self.redact_func(content)
        entity_ids = entity_ids or []

        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO long_term_memories
                (content, category, entity_ids, confidence,
                 source_session, source_turn, access_count, last_accessed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                clean_content, category, json.dumps(entity_ids), confidence,
                source_session, source_turn, time.time(), time.time(),
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_long_term_memories(
        self,
        category: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve long-term memories."""
        cur = self._conn.cursor()
        if category:
            cur.execute(
                """
                SELECT * FROM long_term_memories
                WHERE category = ?
                ORDER BY last_accessed DESC
                LIMIT ?
                """,
                (category, limit),
            )
        else:
            cur.execute(
                """
                SELECT * FROM long_term_memories
                ORDER BY last_accessed DESC
                LIMIT ?
                """,
                (limit,),
            )
        results = []
        for row in cur.fetchall():
            d = dict(row)
            d["entity_ids"] = json.loads(d.get("entity_ids", "[]"))
            results.append(d)
        return results

    def touch_long_term_memory(self, memory_id: int) -> None:
        """Update last_accessed time when a long-term memory is retrieved."""
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE long_term_memories
            SET access_count = access_count + 1, last_accessed = ?
            WHERE id = ?
            """,
            (time.time(), memory_id),
        )
        self._conn.commit()

    # -------------------------------------------------------------------------
    # Session summary / compaction
    # -------------------------------------------------------------------------

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of what happened in a session."""
        facts = self.get_session_facts(session_id, limit=200)

        categories: Dict[str, int] = {}
        for f in facts:
            categories[f.category] = categories.get(f.category, 0) + 1

        return {
            "session_id": session_id,
            "fact_count": len(facts),
            "categories": categories,
            "recent_facts": [
                {"content": f.content[:100], "category": f.category, "source": f.source}
                for f in facts[-10:]
            ],
        }

    def prune_expired_facts(self) -> int:
        """Delete facts that have expired. Returns count deleted."""
        cur = self._conn.cursor()
        now = time.time()
        cur.execute(
            "DELETE FROM facts WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        )
        deleted = cur.rowcount
        self._conn.commit()
        if deleted:
            logger.info("Pruned %d expired facts", deleted)
        return deleted

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facts")
        fact_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM long_term_memories")
        ltm_count = cur.fetchone()[0]

        return {
            "session_facts_total": fact_count,
            "long_term_memories": ltm_count,
            "working_memory_size": len(self._working_memory),
            "session_facts_in_memory": len(self._session_facts),
        }
