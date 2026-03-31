"""
Hermes Memory Engine V2 — SQLite-backed memory with FTS5 search and tiered lifecycle.

Cannibalized from:
- HiveMind (memory.rs): schema, hybrid search, tiers, power-law decay, strength model
- Claude Code (memdir/): type taxonomy, consolidation patterns

Design principles:
- Zero new dependencies (sqlite3 is stdlib, FTS5 is built-in)
- Backward-compatible with flat-file MemoryStore
- Frozen snapshot pattern preserved (no mid-session prompt changes)
- WAL mode for concurrent access (CLI + gateway + cron)
"""

import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_TYPES = ("general", "preference", "correction", "project", "reference")
MEMORY_TIERS = ("active", "archived", "consolidated", "superseded")
MEMORY_TARGETS = ("memory", "user")

TIER_WEIGHTS = {"active": 1.0, "archived": 0.5, "consolidated": 0.3, "superseded": 0.2}
TYPE_BOOSTS = {
    "preference": 1.2,
    "correction": 1.3,
    "project": 1.0,
    "reference": 0.8,
    "general": 1.0,
}

# Power-law decay exponent (from HiveMind memory.rs)
RECENCY_DECAY_EXPONENT = -0.3

# Minimum BM25 score to include in results
DEFAULT_MIN_RELEVANCE = 0.1

# Stale threshold for archival (days)
ARCHIVE_STALE_DAYS = 90
ARCHIVE_MIN_STRENGTH = 1.1

# Near-duplicate threshold (raw BM25 score — higher = stricter)
# Exact duplicates score 10+. Topically similar but different content scores 1-3.
# We want to catch near-exact rephrases (score ~5+) but not topical overlap.
DEDUP_THRESHOLD = 5.0

SCHEMA_VERSION = 1

# Type tag prefixes for prompt rendering
TYPE_TAGS = {
    "preference": "pref",
    "correction": "corr",
    "project": "proj",
    "reference": "ref",
    "general": "gen",
}

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    target          TEXT NOT NULL DEFAULT 'memory',
    type            TEXT NOT NULL DEFAULT 'general',
    source          TEXT NOT NULL DEFAULT 'agent',
    tags            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_accessed   TEXT,
    access_count    INTEGER NOT NULL DEFAULT 0,
    strength        REAL NOT NULL DEFAULT 1.0,
    tier            TEXT NOT NULL DEFAULT 'active',
    superseded_by   TEXT,
    session_id      TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, tags, type,
    content='memories', content_rowid='rowid',
    tokenize='porter unicode61'
);

-- FTS sync triggers
CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags, type)
    VALUES (new.rowid, new.content, new.tags, new.type);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, type)
    VALUES ('delete', old.rowid, old.content, old.tags, old.type);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE OF content, tags, type ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, type)
    VALUES ('delete', old.rowid, old.content, old.tags, old.type);
    INSERT INTO memories_fts(rowid, content, tags, type)
    VALUES (new.rowid, new.content, new.tags, new.type);
END;

CREATE TABLE IF NOT EXISTS memory_meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

_META_DEFAULTS = {
    "schema_version": str(SCHEMA_VERSION),
    "migrated_from_flat": "0",
    "last_consolidation": "",
    "consolidation_session_count": "0",
}


# ---------------------------------------------------------------------------
# MemoryEngine
# ---------------------------------------------------------------------------


class MemoryEngine:
    """SQLite-backed memory store with FTS5 search and tiered lifecycle.

    Thread-safe via per-thread connections and WAL mode.
    """

    def __init__(self, db_path: Optional[Path] = None, config: Optional[dict] = None):
        config = config or {}
        if db_path is None:
            from hermes_cli.config import get_hermes_home

            db_path = get_hermes_home() / "memories" / "memory.db"

        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._config = config
        self._local = threading.local()
        self._lock = threading.Lock()

        # Snapshot for prompt injection (frozen at session start)
        self._snapshot: Optional[dict] = None

        # Initialize schema
        self._init_db()

    # -- Connection management -----------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                str(self._db_path),
                timeout=10.0,
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self):
        """Create tables and seed metadata."""
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        for key, default in _META_DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO memory_meta (key, value) VALUES (?, ?)",
                (key, default),
            )
        conn.commit()

    def close(self):
        """Close the thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

    # -- Meta ----------------------------------------------------------------

    def _get_meta(self, key: str) -> Optional[str]:
        row = self._get_conn().execute(
            "SELECT value FROM memory_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def _set_meta(self, key: str, value: str):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO memory_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    # -- Core CRUD -----------------------------------------------------------

    def add(
        self,
        content: str,
        target: str = "memory",
        type: str = "general",
        tags: str = "",
        source: str = "agent",
        session_id: str = None,
    ) -> dict:
        """Add a new memory. Returns {success, id, ...} or {error}."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}
        if target not in MEMORY_TARGETS:
            return {"success": False, "error": f"Invalid target: {target}. Use: {MEMORY_TARGETS}"}
        if type not in MEMORY_TYPES:
            type = "general"

        # Exact duplicate check (fast, reliable)
        conn = self._get_conn()
        exact = conn.execute(
            "SELECT id, content FROM memories WHERE target = ? AND tier = 'active' AND content = ?",
            (target, content),
        ).fetchone()
        if exact:
            return {
                "success": False,
                "error": f"Exact duplicate exists: {exact['content'][:80]}...",
                "duplicate_id": exact["id"],
            }

        now = datetime.now(timezone.utc).isoformat()
        memory_id = str(uuid.uuid4())

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO memories (id, content, target, type, source, tags,
               created_at, updated_at, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, content, target, type, source, tags, now, now, session_id),
        )
        conn.commit()

        # Check for supersession candidates
        self._check_supersession(memory_id, content, target)

        logger.debug("Memory added: %s [%s/%s] %s", memory_id[:8], target, type, content[:60])
        return {"success": True, "id": memory_id, "target": target, "type": type}

    def replace(self, memory_id: str, new_content: str) -> dict:
        """Update a memory's content."""
        new_content = new_content.strip()
        if not new_content:
            return {"success": False, "error": "Content cannot be empty."}

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
            (new_content, now, memory_id),
        )
        conn.commit()

        if cur.rowcount == 0:
            return {"success": False, "error": f"Memory {memory_id} not found."}
        return {"success": True, "id": memory_id}

    def remove(self, memory_id: str) -> dict:
        """Delete a memory."""
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()

        if cur.rowcount == 0:
            return {"success": False, "error": f"Memory {memory_id} not found."}
        return {"success": True, "id": memory_id}

    def get(self, memory_id: str) -> Optional[dict]:
        """Get a single memory by ID."""
        row = self._get_conn().execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    # -- Search --------------------------------------------------------------

    def search_fts(self, query: str, target: str = None, limit: int = 20) -> list:
        """BM25 full-text search. Returns memories ranked by relevance."""
        query = query.strip()
        if not query:
            return []

        conn = self._get_conn()
        # Build FTS5 query — tokenize for safety
        fts_query = " OR ".join(
            f'"{w}"' for w in query.split() if w and len(w) > 1
        )
        if not fts_query:
            fts_query = f'"{query}"'

        sql = """
            SELECT m.*, bm25(memories_fts) AS bm25_rank
            FROM memories m
            JOIN memories_fts ON memories_fts.rowid = m.rowid
            WHERE memories_fts MATCH ?
        """
        params = [fts_query]

        if target:
            sql += " AND m.target = ?"
            params.append(target)

        sql += " ORDER BY bm25_rank LIMIT ?"
        params.append(limit)

        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning("FTS5 query failed: %s (query=%r)", e, fts_query)
            return []

        results = []
        for row in rows:
            d = dict(row)
            # FTS5 bm25() returns negative values (more negative = better match).
            # We negate to get positive scores. Do NOT normalize to 0-1 across
            # the result set — that makes the best match always 1.0 regardless
            # of actual relevance. Raw magnitude is more useful for thresholding.
            raw = -d.pop("bm25_rank", 0)
            d["bm25_score"] = max(raw, 0.0)
            results.append(d)

        return results

    def search(
        self,
        query: str,
        target: str = None,
        limit: int = 10,
        min_relevance: float = DEFAULT_MIN_RELEVANCE,
    ) -> list:
        """Hybrid search: FTS5 BM25 + recency + strength + tier weighting.

        Adapted from HiveMind memory.rs score_memory().
        """
        candidates = self.search_fts(query, target=target, limit=limit * 3)
        if not candidates:
            return []

        now = datetime.now(timezone.utc)

        scored = []
        for mem in candidates:
            bm25 = mem.get("bm25_score", 0)

            # Recency decay (power-law, from HiveMind)
            try:
                updated = datetime.fromisoformat(mem["updated_at"])
                hours = max((now - updated).total_seconds() / 3600, 0)
            except (ValueError, TypeError):
                hours = 0
            recency = (1 + hours) ** RECENCY_DECAY_EXPONENT

            # Strength (logarithmic reinforcement, from HiveMind)
            access_count = mem.get("access_count", 0)
            strength = 1.0 + 0.1 * math.log(1 + access_count)

            # Tier weight
            tier_w = TIER_WEIGHTS.get(mem.get("tier", "active"), 0.5)

            # Type boost
            type_w = TYPE_BOOSTS.get(mem.get("type", "general"), 1.0)

            score = bm25 * recency * strength * tier_w * type_w
            if score >= min_relevance:
                mem["relevance_score"] = round(score, 4)
                scored.append(mem)

        scored.sort(key=lambda m: m["relevance_score"], reverse=True)
        return scored[:limit]

    # -- Lifecycle -----------------------------------------------------------

    def reinforce(self, memory_id: str):
        """Increment access count and update strength. Called on search hit."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE memories
               SET access_count = access_count + 1,
                   strength = 1.0 + 0.1 * ln(1 + access_count + 1),
                   last_accessed = ?
               WHERE id = ?""",
            (now, memory_id),
        )
        conn.commit()

    def archive_stale(self, days: int = ARCHIVE_STALE_DAYS, min_strength: float = ARCHIVE_MIN_STRENGTH) -> int:
        """Archive memories that are old and weak. Returns count archived."""
        conn = self._get_conn()
        cutoff = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """UPDATE memories
               SET tier = 'archived', updated_at = ?
               WHERE tier = 'active'
                 AND strength < ?
                 AND julianday(?) - julianday(updated_at) > ?""",
            (cutoff, min_strength, cutoff, days),
        )
        conn.commit()
        count = cur.rowcount
        if count:
            logger.info("Archived %d stale memories (>%d days, strength<%.1f)", count, days, min_strength)
        return count

    def supersede(self, old_id: str, new_id: str):
        """Mark old memory as superseded by new one."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE memories SET tier = 'superseded', superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_id, now, old_id),
        )
        conn.commit()

    def _check_supersession(self, new_id: str, content: str, target: str):
        """Check if this new memory supersedes an existing one.

        From HiveMind: cosine > 0.85 + same topic -> supersede.
        We approximate with FTS5 BM25 since we don't have embeddings yet.
        """
        candidates = self.search_fts(content, target=target, limit=5)
        for c in candidates:
            if c["id"] == new_id:
                continue
            if c.get("bm25_score", 0) > DEDUP_THRESHOLD and c.get("tier") == "active":
                self.supersede(c["id"], new_id)
                logger.debug(
                    "Memory %s superseded by %s (score=%.2f)",
                    c["id"][:8], new_id[:8], c["bm25_score"],
                )

    # -- Retrieval for prompts -----------------------------------------------

    def get_active_memories(self, target: str, limit: int = None) -> list:
        """Get all active memories for a target, ordered by strength desc."""
        conn = self._get_conn()
        sql = "SELECT * FROM memories WHERE target = ? AND tier = 'active' ORDER BY strength DESC"
        params = [target]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def format_for_prompt(self, target: str, char_budget: int = None) -> Optional[str]:
        """Format memories for system prompt injection.

        Adds type tags, respects budget, returns None if empty.
        """
        memories = self.get_active_memories(target)
        if not memories:
            return None

        lines = []
        total_chars = 0
        for mem in memories:
            tag = TYPE_TAGS.get(mem.get("type", "general"), "gen")
            line = f"[{tag}] {mem['content']}"
            if char_budget and total_chars + len(line) + 3 > char_budget:
                break
            lines.append(line)
            total_chars += len(line) + 3  # +3 for delimiter

        if not lines:
            return None

        content = "\n§\n".join(lines)
        total = self.count_active(target)
        shown = len(lines)
        budget_str = f"{total_chars}" if not char_budget else f"{total_chars}/{char_budget}"

        header_name = "MEMORY (your personal notes)" if target == "memory" else "USER PROFILE (who the user is)"
        header = f"{'═' * 46}\n{header_name} [{shown}/{total} entries — {budget_str} chars]\n{'═' * 46}"

        return f"{header}\n{content}\n"

    # -- Snapshot (frozen at session start) ----------------------------------

    def snapshot(self) -> dict:
        """Capture current state as frozen snapshot for prompt caching."""
        self._snapshot = {
            "memory": self.format_for_prompt("memory"),
            "user": self.format_for_prompt("user"),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._snapshot

    def get_snapshot(self, target: str) -> Optional[str]:
        """Get frozen snapshot for a target. Returns None if not captured or empty."""
        if self._snapshot is None:
            self.snapshot()
        return self._snapshot.get(target)

    # -- Stats ---------------------------------------------------------------

    def count_active(self, target: str = None) -> int:
        """Count active memories, optionally filtered by target."""
        conn = self._get_conn()
        if target:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE target = ? AND tier = 'active'",
                (target,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE tier = 'active'"
            ).fetchone()
        return row["c"] if row else 0

    def stats(self) -> dict:
        """Memory statistics."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT target, tier, type, COUNT(*) as count FROM memories GROUP BY target, tier, type"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]

        by_target = {}
        by_tier = {}
        by_type = {}
        for r in rows:
            by_target[r["target"]] = by_target.get(r["target"], 0) + r["count"]
            by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + r["count"]
            by_type[r["type"]] = by_type.get(r["type"], 0) + r["count"]

        return {
            "total": total,
            "by_target": by_target,
            "by_tier": by_tier,
            "by_type": by_type,
            "schema_version": self._get_meta("schema_version"),
        }

    # -- Migration from flat files -------------------------------------------

    def migrate_from_flat_files(self, memory_dir: Path = None) -> dict:
        """Import entries from MEMORY.md and USER.md into SQLite.

        Preserves flat files as .bak. Idempotent (skips if already migrated).
        """
        if self._get_meta("migrated_from_flat") == "1":
            return {"migrated": False, "reason": "Already migrated."}

        if memory_dir is None:
            from hermes_cli.config import get_hermes_home
            memory_dir = get_hermes_home() / "memories"

        count = 0
        for target, filename in [("memory", "MEMORY.md"), ("user", "USER.md")]:
            filepath = memory_dir / filename
            if not filepath.exists():
                continue

            text = filepath.read_text(encoding="utf-8").strip()
            if not text:
                continue

            entries = [e.strip() for e in text.split("\n§\n") if e.strip()]
            for entry in entries:
                self.add(
                    content=entry,
                    target=target,
                    type="general",
                    source="migration",
                )
                count += 1

            # Backup flat file
            bak = filepath.with_suffix(".md.bak")
            if not bak.exists():
                filepath.rename(bak)
                logger.info("Backed up %s -> %s", filepath.name, bak.name)

        self._set_meta("migrated_from_flat", "1")
        logger.info("Migrated %d entries from flat files to SQLite", count)
        return {"migrated": True, "count": count}

    # -- Manifest for extraction dedup (from Claude Code pattern) -----------

    def get_manifest(self, target: str = None) -> str:
        """Return a compact manifest of all active memories for dedup checking.

        Used by the auto-extractor to avoid duplicating existing memories.
        """
        memories = []
        for t in ([target] if target else list(MEMORY_TARGETS)):
            for mem in self.get_active_memories(t):
                memories.append(f"[{mem['id'][:8]}|{mem.get('type','gen')}|{mem['target']}] {mem['content'][:120]}")
        return "\n".join(memories) if memories else "(no memories yet)"
