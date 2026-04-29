"""
KnowledgeGraph — SQLite-backed knowledge graph for Hermes.

Nodes = entities (people, concepts, facts, projects, etc.)
Edges = relationships between entities
Both carry confidence scores and source session metadata.

Design goals:
  - Incremental writes (never full rebuild)
  - WAL mode for concurrent readers + one writer
  - Cross-session knowledge accumulation
  - Privacy-first: sensitive data redacted before storage
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_KG_PATH = get_hermes_home() / "knowledge.db"
SCHEMA_VERSION = 1

# -----------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    entity_type     TEXT NOT NULL DEFAULT 'concept',
    alias           TEXT,
    properties      TEXT NOT NULL DEFAULT '{}',
    confidence      REAL NOT NULL DEFAULT 1.0,
    source_session  TEXT,
    source_turn     INTEGER DEFAULT 0,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    UNIQUE(name, entity_type)
);

CREATE TABLE IF NOT EXISTS relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id    INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    properties      TEXT NOT NULL DEFAULT '{}',
    confidence      REAL NOT NULL DEFAULT 1.0,
    source_session  TEXT,
    source_turn     INTEGER DEFAULT 0,
    created_at      REAL NOT NULL,
    UNIQUE(from_entity_id, to_entity_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_name    ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type    ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_relations_from  ON relations(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_to     ON relations(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_type   ON relations(relation_type);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    name,
    alias,
    content=entities,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS entities_fts_insert AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, name, alias)
        VALUES (new.id, new.name, new.alias);
END;

CREATE TRIGGER IF NOT EXISTS entities_fts_delete AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, alias)
        VALUES('delete', old.id, old.name, old.alias);
END;

CREATE TRIGGER IF NOT EXISTS entities_fts_update AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, alias)
        VALUES('delete', old.id, old.name, old.alias);
    INSERT INTO entities_fts(rowid, name, alias)
        VALUES (new.id, new.name, new.alias);
END;
"""

# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------

@dataclass
class Entity:
    """A node in the knowledge graph."""
    id: Optional[int] = None
    name: str = ""
    entity_type: str = "concept"
    alias: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_session: str = ""
    source_turn: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Entity":
        props = json.loads(row["properties"]) if row["properties"] else {}
        return cls(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            alias=row["alias"] or "",
            properties=props,
            confidence=row["confidence"],
            source_session=row["source_session"] or "",
            source_turn=row["source_turn"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "alias": self.alias,
            "properties": self.properties,
            "confidence": self.confidence,
            "source_session": self.source_session,
            "source_turn": self.source_turn,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Relation:
    """An edge in the knowledge graph."""
    id: Optional[int] = None
    from_entity_id: int = 0
    to_entity_id: int = 0
    relation_type: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_session: str = ""
    source_turn: int = 0
    created_at: float = 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Relation":
        props = json.loads(row["properties"]) if row["properties"] else {}
        return cls(
            id=row["id"],
            from_entity_id=row["from_entity_id"],
            to_entity_id=row["to_entity_id"],
            relation_type=row["relation_type"],
            properties=props,
            confidence=row["confidence"],
            source_session=row["source_session"] or "",
            source_turn=row["source_turn"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "relation_type": self.relation_type,
            "properties": self.properties,
            "confidence": self.confidence,
            "source_session": self.source_session,
            "source_turn": self.source_turn,
            "created_at": self.created_at,
        }


# -----------------------------------------------------------------------------
# KnowledgeGraph
# -----------------------------------------------------------------------------

class KnowledgeGraph:
    """
    SQLite-backed knowledge graph with FTS5 search.

    Thread-safe for concurrent readers + single writer via WAL mode.
    """

    _WRITE_MAX_RETRIES = 15
    _WRITE_RETRY_MIN_S = 0.020
    _WRITE_RETRY_MAX_S = 0.150
    _CHECKPOINT_EVERY_N_WRITES = 50

    def __init__(
        self,
        db_path: Path | None = None,
        max_entities: int = 10000,
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_KG_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entities = max_entities

        self._lock = threading.RLock()  # RLock so nested calls within _execute_write don't deadlock
        self._write_count = 0
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._init_schema()

    # -------------------------------------------------------------------------
    # Schema init / migration
    # -------------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA user_version")
            row = cur.fetchone()
            version = row[0] if row else 0

            if version < SCHEMA_VERSION:
                cur.executescript(SCHEMA_SQL)
                cur.executescript(FTS_SQL)
                cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._conn.commit()

    # -------------------------------------------------------------------------
    # Write helper (same jitter-retry pattern as SessionDB)
    # -------------------------------------------------------------------------

    def _execute_write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        import random
        last_err: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.commit()
                    except BaseException:
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        raise
                self._write_count += 1
                if self._write_count % self._CHECKPOINT_EVERY_N_WRITES == 0:
                    self._try_wal_checkpoint()
                return result
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if "locked" in err_msg or "busy" in err_msg:
                    last_err = exc
                    time.sleep(random.uniform(
                        self._WRITE_RETRY_MIN_S,
                        self._WRITE_RETRY_MAX_S,
                    ))
                    continue
                raise
        raise last_err or RuntimeError("Unknown write error")

    def _try_wal_checkpoint(self) -> None:
        try:
            self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Entity CRUD
    # -------------------------------------------------------------------------

    def upsert_entity(
        self,
        name: str,
        entity_type: str = "concept",
        alias: str = "",
        properties: Dict[str, Any] | None = None,
        confidence: float = 1.0,
        source_session: str = "",
        source_turn: int = 0,
    ) -> Entity:
        """Insert or update an entity. Returns the entity with id set."""
        now = time.time()
        props = json.dumps(properties or {}, ensure_ascii=False)
        alias = alias or ""

        def _do(conn: sqlite3.Connection) -> Entity:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id FROM entities WHERE name = ? AND entity_type = ?
                """,
                (name, entity_type),
            )
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE entities
                    SET alias=?, properties=?, confidence=?,
                        source_session=?, source_turn=?, updated_at=?
                    WHERE id = ?
                    """,
                    (alias, props, confidence, source_session, source_turn,
                     now, existing["id"]),
                )
                entity_id = existing["id"]
            else:
                cur.execute(
                    """
                    INSERT INTO entities
                        (name, entity_type, alias, properties, confidence,
                         source_session, source_turn, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, entity_type, alias, props, confidence,
                     source_session, source_turn, now, now),
                )
                entity_id = cur.lastrowid

            conn.commit()
            return self.get_entity_by_id(entity_id)

        return self._execute_write(_do)

    def get_entity_by_id(self, entity_id: int) -> Optional[Entity]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            row = cur.fetchone()
            return Entity.from_row(row) if row else None

    def get_entity_by_name(self, name: str, entity_type: str = "concept") -> Optional[Entity]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM entities WHERE name = ? AND entity_type = ?",
                (name, entity_type),
            )
            row = cur.fetchone()
            return Entity.from_row(row) if row else None

    def search_entities(self, query: str, entity_type: str = "", limit: int = 20) -> List[Entity]:
        """Full-text search over entity names and aliases."""
        with self._lock:
            cur = self._conn.cursor()
            if entity_type:
                cur.execute(
                    """
                    SELECT e.* FROM entities e
                    JOIN entities_fts f ON e.id = f.rowid
                    WHERE entities_fts MATCH ? AND e.entity_type = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, entity_type, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT e.* FROM entities e
                    JOIN entities_fts f ON e.id = f.rowid
                    WHERE entities_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                )
            return [Entity.from_row(row) for row in cur.fetchall()]

    def list_entities(
        self,
        entity_type: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        with self._lock:
            cur = self._conn.cursor()
            if entity_type:
                cur.execute(
                    "SELECT * FROM entities WHERE entity_type = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (entity_type, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT * FROM entities ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            return [Entity.from_row(row) for row in cur.fetchall()]

    def delete_entity(self, entity_id: int) -> bool:
        def _do(conn: sqlite3.Connection) -> bool:
            cur = conn.cursor()
            cur.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.commit()
            return cur.rowcount > 0
        return self._execute_write(_do)

    def entity_count(self) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM entities")
            return cur.fetchone()[0]

    # -------------------------------------------------------------------------
    # Relation CRUD
    # -------------------------------------------------------------------------

    def upsert_relation(
        self,
        from_entity_id: int,
        to_entity_id: int,
        relation_type: str,
        properties: Dict[str, Any] | None = None,
        confidence: float = 1.0,
        source_session: str = "",
        source_turn: int = 0,
    ) -> Relation:
        """Insert or update a relation (unique by from/to/type tuple)."""
        now = time.time()
        props = json.dumps(properties or {}, ensure_ascii=False)

        def _do(conn: sqlite3.Connection) -> Relation:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id FROM relations
                WHERE from_entity_id = ? AND to_entity_id = ? AND relation_type = ?
                """,
                (from_entity_id, to_entity_id, relation_type),
            )
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE relations
                    SET properties=?, confidence=?, source_session=?, source_turn=?
                    WHERE id = ?
                    """,
                    (props, confidence, source_session, source_turn, existing["id"]),
                )
                rel_id = existing["id"]
            else:
                cur.execute(
                    """
                    INSERT INTO relations
                        (from_entity_id, to_entity_id, relation_type, properties,
                         confidence, source_session, source_turn, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (from_entity_id, to_entity_id, relation_type, props,
                     confidence, source_session, source_turn, now),
                )
                rel_id = cur.lastrowid

            conn.commit()
            # Return the relation
            cur.execute("SELECT * FROM relations WHERE id = ?", (rel_id,))
            return Relation.from_row(cur.fetchone())

        return self._execute_write(_do)

    def get_relations_from(self, entity_id: int) -> List[Relation]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM relations WHERE from_entity_id = ?",
                (entity_id,),
            )
            return [Relation.from_row(row) for row in cur.fetchall()]

    def get_relations_to(self, entity_id: int) -> List[Relation]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM relations WHERE to_entity_id = ?",
                (entity_id,),
            )
            return [Relation.from_row(row) for row in cur.fetchall()]

    def get_neighbors(self, entity_id: int, depth: int = 1) -> List[Tuple[Entity, Relation]]:
        """Get all entities connected to this entity (1 hop)."""
        results = []
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT e.*, r.relation_type, r.confidence, r.properties,
                       r.source_session, r.source_turn, r.created_at
                FROM relations r
                JOIN entities e ON (e.id = r.to_entity_id)
                WHERE r.from_entity_id = ?
                UNION ALL
                SELECT e.*, r.relation_type, r.confidence, r.properties,
                       r.source_session, r.source_turn, r.created_at
                FROM relations r
                JOIN entities e ON (e.id = r.from_entity_id)
                WHERE r.to_entity_id = ?
                """,
                (entity_id, entity_id),
            )
            for row in cur.fetchall():
                entity = Entity.from_row(row)
                rel = Relation(
                    from_entity_id=entity_id,
                    to_entity_id=entity.id,
                    relation_type=row["relation_type"],
                    properties=json.loads(row["properties"]) if row["properties"] else {},
                    confidence=row["confidence"],
                    source_session=row["source_session"] or "",
                    source_turn=row["source_turn"],
                    created_at=row["created_at"],
                )
                results.append((entity, rel))
        return results

    def delete_relation(self, relation_id: int) -> bool:
        def _do(conn: sqlite3.Connection) -> bool:
            cur = conn.cursor()
            cur.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
            conn.commit()
            return cur.rowcount > 0
        return self._execute_write(_do)

    def relation_count(self) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM relations")
            return cur.fetchone()[0]

    # -------------------------------------------------------------------------
    # Multi-hop reasoning traversal
    # -------------------------------------------------------------------------

    def traverse(
        self,
        start_entity_id: int,
        relation_filter: str = "",
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """Breadth-first traversal from a start entity.

        Returns a tree of {entity_id: {"entity": Entity, "relations": [...], "children": {...}}}
        """
        visited: Dict[int, bool] = {}
        results: Dict[int, Any] = {}

        def _bfs(current_id: int, depth: int) -> None:
            if depth > max_depth or visited.get(current_id):
                return
            visited[current_id] = True

            entity = self.get_entity_by_id(current_id)
            if not entity:
                return

            rels = self.get_relations_from(current_id)
            if relation_filter:
                rels = [r for r in rels if r.relation_type == relation_filter]

            children = {}
            for rel in rels:
                if rel.to_entity_id not in visited:
                    _bfs(rel.to_entity_id, depth + 1)
                    children[rel.to_entity_id] = {
                        "entity": self.get_entity_by_id(rel.to_entity_id),
                        "relation": rel,
                    }

            results[current_id] = {
                "entity": entity,
                "relations": rels,
                "children": children,
            }

        _bfs(start_entity_id, 0)
        return results

    # -------------------------------------------------------------------------
    # Bulk operations (for incremental indexing)
    # -------------------------------------------------------------------------

    def bulk_upsert_entities(
        self,
        entities: List[Dict[str, Any]],
        source_session: str = "",
    ) -> List[Entity]:
        """Bulk upsert a list of entity dicts. Efficient for incremental indexing."""
        now = time.time()
        results: List[Entity] = []

        def _do(conn: sqlite3.Connection) -> List[Entity]:
            cur = conn.cursor()
            for e in entities:
                name = e.get("name", "")
                entity_type = e.get("entity_type", "concept")
                alias = e.get("alias", "")
                props = json.dumps(e.get("properties", {}), ensure_ascii=False)
                confidence = e.get("confidence", 1.0)
                source_turn = e.get("source_turn", 0)

                cur.execute(
                    "SELECT id FROM entities WHERE name = ? AND entity_type = ?",
                    (name, entity_type),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE entities
                        SET alias=?, properties=?, confidence=?,
                            source_session=?, source_turn=?, updated_at=?
                        WHERE id = ?
                        """,
                        (alias, props, confidence, source_session,
                         source_turn, now, existing["id"]),
                    )
                    entity_id = existing["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO entities
                            (name, entity_type, alias, properties, confidence,
                             source_session, source_turn, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (name, entity_type, alias, props, confidence,
                         source_session, source_turn, now, now),
                    )
                    entity_id = cur.lastrowid

                cur.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
                results.append(Entity.from_row(cur.fetchone()))

            conn.commit()
            return results

        return self._execute_write(_do)

    def bulk_upsert_relations(
        self,
        relations: List[Dict[str, Any]],
        source_session: str = "",
    ) -> List[Relation]:
        """Bulk upsert relations. Each dict must have from_name, to_name, from_type, to_type."""
        now = time.time()
        results: List[Relation] = []

        def _do(conn: sqlite3.Connection) -> List[Relation]:
            cur = conn.cursor()
            for r in relations:
                from_name = r.get("from_name", "")
                to_name = r.get("to_name", "")
                from_type = r.get("from_type", "concept")
                to_type = r.get("to_type", "concept")
                rel_type = r.get("relation_type", "related_to")
                props = json.dumps(r.get("properties", {}), ensure_ascii=False)
                confidence = r.get("confidence", 1.0)
                source_turn = r.get("source_turn", 0)

                # Resolve entity IDs
                cur.execute(
                    "SELECT id FROM entities WHERE name = ? AND entity_type = ?",
                    (from_name, from_type),
                )
                from_row = cur.fetchone()
                if not from_row:
                    cur.execute(
                        """
                        INSERT INTO entities (name, entity_type, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (from_name, from_type, now, now),
                    )
                    from_id = cur.lastrowid
                else:
                    from_id = from_row["id"]

                cur.execute(
                    "SELECT id FROM entities WHERE name = ? AND entity_type = ?",
                    (to_name, to_type),
                )
                to_row = cur.fetchone()
                if not to_row:
                    cur.execute(
                        """
                        INSERT INTO entities (name, entity_type, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (to_name, to_type, now, now),
                    )
                    to_id = cur.lastrowid
                else:
                    to_id = to_row["id"]

                # Upsert relation
                cur.execute(
                    """
                    SELECT id FROM relations
                    WHERE from_entity_id = ? AND to_entity_id = ? AND relation_type = ?
                    """,
                    (from_id, to_id, rel_type),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE relations
                        SET properties=?, confidence=?, source_session=?, source_turn=?
                        WHERE id = ?
                        """,
                        (props, confidence, source_session, source_turn, existing["id"]),
                    )
                    rel_id = existing["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO relations
                            (from_entity_id, to_entity_id, relation_type, properties,
                             confidence, source_session, source_turn, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (from_id, to_id, rel_type, props, confidence,
                         source_session, source_turn, now),
                    )
                    rel_id = cur.lastrowid

                cur.execute("SELECT * FROM relations WHERE id = ?", (rel_id,))
                results.append(Relation.from_row(cur.fetchone()))

            conn.commit()
            return results

        return self._execute_write(_do)

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def vacuum(self) -> None:
        """Compact the database. Call occasionally, not in hot path."""
        def _do(_conn: sqlite3.Connection) -> None:
            _conn.execute("VACUUM")
        self._execute_write(_do)

    def stats(self) -> Dict[str, Any]:
        """Return basic statistics about the knowledge graph."""
        return {
            "entity_count": self.entity_count(),
            "relation_count": self.relation_count(),
            "db_path": str(self.db_path),
        }
