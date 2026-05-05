"""SQLite-backed fact store with enrichment, linking, and trust scoring."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .embeddings import (
    EmbeddingProvider,
    NoopEmbeddingProvider,
    bytes_to_vector,
    cosine_similarity,
    vector_to_bytes,
)
from .enrichment import canonicalize_key, enrich_fact, extract_entities

try:
    from . import holographic as hrr
except ImportError:
    import holographic as hrr  # type: ignore[no-redef]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content            TEXT NOT NULL UNIQUE,
    category           TEXT DEFAULT 'general',
    tags               TEXT DEFAULT '',
    trust_score        REAL DEFAULT 0.5,
    retrieval_count    INTEGER DEFAULT 0,
    helpful_count      INTEGER DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hrr_vector         BLOB,
    metadata_json      TEXT DEFAULT '{}',
    salience_score     REAL DEFAULT 0.5,
    source_confidence  REAL DEFAULT 0.5,
    source_channel     TEXT DEFAULT '',
    intent_type        TEXT DEFAULT 'general',
    embedding_vector   BLOB,
    embedding_dim      INTEGER DEFAULT 0,
    embedding_provider TEXT DEFAULT '',
    embedding_model    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    entity_type TEXT DEFAULT 'unknown',
    canonical_key TEXT DEFAULT '',
    aliases     TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_entities (
    fact_id   INTEGER REFERENCES facts(fact_id),
    entity_id INTEGER REFERENCES entities(entity_id),
    PRIMARY KEY (fact_id, entity_id)
);

CREATE TABLE IF NOT EXISTS fact_links (
    fact_id          INTEGER NOT NULL REFERENCES facts(fact_id),
    related_fact_id  INTEGER NOT NULL REFERENCES facts(fact_id),
    link_type        TEXT NOT NULL DEFAULT 'related',
    strength         REAL NOT NULL DEFAULT 0.0,
    reason           TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (fact_id, related_fact_id)
);

CREATE INDEX IF NOT EXISTS idx_facts_trust      ON facts(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_facts_category   ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_salience   ON facts(salience_score DESC);
CREATE INDEX IF NOT EXISTS idx_facts_source     ON facts(source_channel);
CREATE INDEX IF NOT EXISTS idx_facts_intent     ON facts(intent_type);
CREATE INDEX IF NOT EXISTS idx_entities_name    ON entities(name);
CREATE INDEX IF NOT EXISTS idx_fact_links_right ON fact_links(related_fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_links_type  ON fact_links(link_type);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_key);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
    USING fts5(content, tags, content=facts, content_rowid=fact_id);

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content, tags)
        VALUES (new.fact_id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, tags)
        VALUES ('delete', old.fact_id, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, tags)
        VALUES ('delete', old.fact_id, old.content, old.tags);
    INSERT INTO facts_fts(rowid, content, tags)
        VALUES (new.fact_id, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS memory_banks (
    bank_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name  TEXT NOT NULL UNIQUE,
    vector     BLOB NOT NULL,
    dim        INTEGER NOT NULL,
    fact_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS understanding_ingest_queue (
    ingest_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ingest_type     TEXT NOT NULL,
    session_id      TEXT DEFAULT '',
    dedupe_key      TEXT NOT NULL UNIQUE,
    payload_json    TEXT NOT NULL,
    source_channel  TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    available_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    last_error      TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_ingest_queue_status
    ON understanding_ingest_queue(status, available_at, ingest_id);

CREATE TABLE IF NOT EXISTS understanding_state (
    state_key   TEXT PRIMARY KEY,
    state_value TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_HELPFUL_DELTA = 0.05
_UNHELPFUL_DELTA = -0.10
_TRUST_MIN = 0.0
_TRUST_MAX = 1.0
_MAX_LINK_SCAN = 500
_MAX_BACKOFF_SECONDS = 1800


def _utc_now_sql() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _clamp_trust(value: float) -> float:
    return max(_TRUST_MIN, min(_TRUST_MAX, value))


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class MemoryStore:
    """SQLite-backed fact store with enrichment, trust scoring, and links."""

    def __init__(
        self,
        db_path: "str | Path | None" = None,
        default_trust: float = 0.5,
        hrr_dim: int = 1024,
        embedding_provider: EmbeddingProvider | None = None,
        link_threshold: float = 0.36,
    ) -> None:
        if db_path is None:
            from hermes_constants import get_hermes_home

            db_path = str(get_hermes_home() / "memory_store.db")
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_trust = _clamp_trust(default_trust)
        self.hrr_dim = hrr_dim
        self._hrr_available = hrr._HAS_NUMPY
        self._embedding_provider = embedding_provider or NoopEmbeddingProvider()
        self._link_threshold = _clamp_unit(link_threshold)
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._lock = threading.RLock()
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._ensure_fact_column("hrr_vector", "BLOB")
        self._ensure_fact_column("metadata_json", "TEXT DEFAULT '{}'")
        self._ensure_fact_column("salience_score", "REAL DEFAULT 0.5")
        self._ensure_fact_column("source_confidence", "REAL DEFAULT 0.5")
        self._ensure_fact_column("source_channel", "TEXT DEFAULT ''")
        self._ensure_fact_column("intent_type", "TEXT DEFAULT 'general'")
        self._ensure_fact_column("embedding_vector", "BLOB")
        self._ensure_fact_column("embedding_dim", "INTEGER DEFAULT 0")
        self._ensure_fact_column("embedding_provider", "TEXT DEFAULT ''")
        self._ensure_fact_column("embedding_model", "TEXT DEFAULT ''")
        self._ensure_entity_column("canonical_key", "TEXT DEFAULT ''")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_key)")
        self._recover_processing_ingest()
        self._conn.commit()

    def _ensure_fact_column(self, name: str, definition: str) -> None:
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(facts)").fetchall()}
        if name not in columns:
            self._conn.execute(f"ALTER TABLE facts ADD COLUMN {name} {definition}")

    def _ensure_entity_column(self, name: str, definition: str) -> None:
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(entities)").fetchall()}
        if name not in columns:
            self._conn.execute(f"ALTER TABLE entities ADD COLUMN {name} {definition}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_fact(
        self,
        content: str,
        category: str = "general",
        tags: str = "",
        source_channel: str = "tool:fact_store",
        source_confidence: float | None = None,
        intent_type: str | None = None,
        salience_score: float | None = None,
    ) -> int:
        """Insert a fact and return its fact_id."""
        normalized = content.strip()
        if not normalized:
            raise ValueError("content must not be empty")

        enrichment = enrich_fact(
            normalized,
            category=category,
            tags=tags,
            source_channel=source_channel,
            intent_type=intent_type,
            salience_score=salience_score,
            source_confidence=source_confidence,
        )
        embedding_payload = self._build_embedding_payload(normalized)

        with self._lock:
            try:
                cur = self._conn.execute(
                    """
                    INSERT INTO facts (
                        content, category, tags, trust_score,
                        metadata_json, salience_score, source_confidence,
                        source_channel, intent_type, embedding_vector,
                        embedding_dim, embedding_provider, embedding_model
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized,
                        category,
                        tags,
                        self.default_trust,
                        json.dumps(enrichment.to_dict(), ensure_ascii=False),
                        enrichment.salience_score,
                        enrichment.source_confidence,
                        enrichment.source_channel,
                        enrichment.intent_type,
                        embedding_payload["vector"],
                        embedding_payload["dim"],
                        embedding_payload["provider"],
                        embedding_payload["model"],
                    ),
                )
                fact_id: int = cur.lastrowid  # type: ignore[assignment]
            except sqlite3.IntegrityError:
                row = self._conn.execute(
                    "SELECT fact_id FROM facts WHERE content = ?", (normalized,)
                ).fetchone()
                return int(row["fact_id"])

            self._refresh_fact_entities(fact_id, enrichment.entities)
            self._compute_hrr_vector(fact_id, normalized, commit=False)
            self._rebuild_bank(category, commit=False)
            self._refresh_links_for_fact(fact_id, commit=False)
            self._conn.commit()
            return fact_id

    def search_facts(
        self,
        query: str,
        category: str | None = None,
        min_trust: float = 0.3,
        limit: int = 10,
    ) -> list[dict]:
        """Full-text search over facts using FTS5."""
        with self._lock:
            query = query.strip()
            if not query:
                return []

            params: list = [query, min_trust]
            category_clause = ""
            if category is not None:
                category_clause = "AND f.category = ?"
                params.append(category)
            params.append(limit)

            sql = f"""
                SELECT f.fact_id, f.content, f.category, f.tags,
                       f.trust_score, f.retrieval_count, f.helpful_count,
                       f.created_at, f.updated_at, f.metadata_json,
                       f.salience_score, f.source_confidence, f.source_channel,
                       f.intent_type, f.embedding_provider, f.embedding_model
                FROM facts f
                JOIN facts_fts fts ON fts.rowid = f.fact_id
                WHERE facts_fts MATCH ?
                  AND f.trust_score >= ?
                  {category_clause}
                ORDER BY fts.rank, f.trust_score DESC
                LIMIT ?
            """

            rows = self._conn.execute(sql, params).fetchall()
            results = [self._row_to_dict(row) for row in rows]

            if results:
                ids = [result["fact_id"] for result in results]
                placeholders = ",".join("?" * len(ids))
                self._conn.execute(
                    f"UPDATE facts SET retrieval_count = retrieval_count + 1 WHERE fact_id IN ({placeholders})",
                    ids,
                )
                self._conn.commit()

            return results

    def update_fact(
        self,
        fact_id: int,
        content: str | None = None,
        trust_delta: float | None = None,
        tags: str | None = None,
        category: str | None = None,
        source_channel: str | None = None,
        source_confidence: float | None = None,
        intent_type: str | None = None,
        salience_score: float | None = None,
    ) -> bool:
        """Partially update a fact. Trust is clamped to [0, 1]."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
            if row is None:
                return False

            new_content = content.strip() if content is not None else row["content"]
            new_tags = tags if tags is not None else row["tags"]
            new_category = category if category is not None else row["category"]
            new_source = source_channel if source_channel is not None else row["source_channel"]
            new_intent = intent_type if intent_type is not None else row["intent_type"]
            effective_salience = salience_score if salience_score is not None else row["salience_score"]
            effective_confidence = source_confidence if source_confidence is not None else row["source_confidence"]
            new_trust = row["trust_score"]
            if trust_delta is not None:
                new_trust = _clamp_trust(new_trust + trust_delta)

            enrichment = enrich_fact(
                new_content,
                category=new_category,
                tags=new_tags,
                source_channel=new_source,
                intent_type=new_intent,
                salience_score=effective_salience,
                source_confidence=effective_confidence,
            )
            embedding_payload = self._build_embedding_payload(new_content)

            self._conn.execute(
                """
                UPDATE facts
                SET content = ?,
                    category = ?,
                    tags = ?,
                    trust_score = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    metadata_json = ?,
                    salience_score = ?,
                    source_confidence = ?,
                    source_channel = ?,
                    intent_type = ?,
                    embedding_vector = ?,
                    embedding_dim = ?,
                    embedding_provider = ?,
                    embedding_model = ?
                WHERE fact_id = ?
                """,
                (
                    new_content,
                    new_category,
                    new_tags,
                    new_trust,
                    json.dumps(enrichment.to_dict(), ensure_ascii=False),
                    enrichment.salience_score,
                    enrichment.source_confidence,
                    enrichment.source_channel,
                    enrichment.intent_type,
                    embedding_payload["vector"],
                    embedding_payload["dim"],
                    embedding_payload["provider"],
                    embedding_payload["model"],
                    fact_id,
                ),
            )

            self._refresh_fact_entities(fact_id, enrichment.entities)
            self._compute_hrr_vector(fact_id, new_content, commit=False)
            old_category = row["category"]
            self._rebuild_bank(old_category, commit=False)
            if new_category != old_category:
                self._rebuild_bank(new_category, commit=False)
            self._refresh_links_for_fact(fact_id, commit=False)
            self._conn.commit()
            return True

    def remove_fact(self, fact_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT fact_id, category FROM facts WHERE fact_id = ?", (fact_id,)
            ).fetchone()
            if row is None:
                return False

            self._conn.execute("DELETE FROM fact_entities WHERE fact_id = ?", (fact_id,))
            self._conn.execute(
                "DELETE FROM fact_links WHERE fact_id = ? OR related_fact_id = ?",
                (fact_id, fact_id),
            )
            self._conn.execute("DELETE FROM facts WHERE fact_id = ?", (fact_id,))
            self._rebuild_bank(row["category"], commit=False)
            self._conn.commit()
            return True

    def list_facts(
        self,
        category: str | None = None,
        min_trust: float = 0.0,
        limit: int = 50,
    ) -> list[dict]:
        with self._lock:
            params: list = [min_trust]
            category_clause = ""
            if category is not None:
                category_clause = "AND category = ?"
                params.append(category)
            params.append(limit)

            sql = f"""
                SELECT fact_id, content, category, tags, trust_score,
                       retrieval_count, helpful_count, created_at, updated_at,
                       metadata_json, salience_score, source_confidence,
                       source_channel, intent_type, embedding_provider,
                       embedding_model
                FROM facts
                WHERE trust_score >= ?
                  {category_clause}
                ORDER BY trust_score DESC, salience_score DESC
                LIMIT ?
            """
            rows = self._conn.execute(sql, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def get_fact(self, fact_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
            if row is None:
                return None
            result = self._row_to_dict(row)
            result["links"] = self.get_fact_links(fact_id)
            return result

    def get_fact_links(self, fact_id: int, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    CASE WHEN fl.fact_id = ? THEN fl.related_fact_id ELSE fl.fact_id END AS linked_fact_id,
                    fl.link_type,
                    fl.strength,
                    fl.reason,
                    f.content,
                    f.category,
                    f.updated_at
                FROM fact_links fl
                JOIN facts f
                  ON f.fact_id = CASE WHEN fl.fact_id = ? THEN fl.related_fact_id ELSE fl.fact_id END
                WHERE fl.fact_id = ? OR fl.related_fact_id = ?
                ORDER BY fl.strength DESC, f.updated_at DESC
                LIMIT ?
                """,
                (fact_id, fact_id, fact_id, fact_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def enqueue_ingest(
        self,
        ingest_type: str,
        payload: dict,
        *,
        dedupe_key: str,
        source_channel: str = "",
        session_id: str = "",
        max_pending: int = 200,
    ) -> dict:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            existing = self._conn.execute(
                """
                SELECT ingest_id, status
                FROM understanding_ingest_queue
                WHERE dedupe_key = ?
                """,
                (dedupe_key,),
            ).fetchone()
            if existing is not None:
                return {
                    "enqueued": False,
                    "duplicate": True,
                    "ingest_id": int(existing["ingest_id"]),
                    "status": existing["status"],
                }

            pending_count = self._conn.execute(
                """
                SELECT COUNT(*)
                FROM understanding_ingest_queue
                WHERE status IN ('pending', 'failed', 'processing')
                """
            ).fetchone()[0]
            if pending_count >= max_pending:
                rejected = int(self._get_state("ingest_enqueue_rejected_count") or "0") + 1
                self._set_state("ingest_enqueue_rejected_count", str(rejected))
                self._set_state(
                    "last_ingest_error_summary",
                    f"understanding ingest queue full ({pending_count} items)",
                )
                self._conn.commit()
                return {
                    "enqueued": False,
                    "duplicate": False,
                    "reason": "queue_full",
                    "pending_items": int(pending_count),
                }

            now = _utc_now_sql()
            cur = self._conn.execute(
                """
                INSERT INTO understanding_ingest_queue (
                    ingest_type, session_id, dedupe_key, payload_json,
                    source_channel, status, created_at, updated_at,
                    available_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    ingest_type,
                    session_id,
                    dedupe_key,
                    payload_json,
                    source_channel,
                    now,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return {
                "enqueued": True,
                "duplicate": False,
                "ingest_id": int(cur.lastrowid),
            }

    def claim_ingest_batch(self, *, limit: int = 1) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT ingest_id
                FROM understanding_ingest_queue
                WHERE status IN ('pending', 'failed')
                  AND available_at <= CURRENT_TIMESTAMP
                ORDER BY ingest_id ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            if not rows:
                return []

            claimed: list[dict] = []
            now = _utc_now_sql()
            for row in rows:
                ingest_id = int(row["ingest_id"])
                cur = self._conn.execute(
                    """
                    UPDATE understanding_ingest_queue
                    SET status = 'processing',
                        attempt_count = attempt_count + 1,
                        started_at = ?,
                        updated_at = ?
                    WHERE ingest_id = ?
                      AND status IN ('pending', 'failed')
                    """,
                    (now, now, ingest_id),
                )
                if cur.rowcount != 1:
                    continue
                claimed_row = self._conn.execute(
                    "SELECT * FROM understanding_ingest_queue WHERE ingest_id = ?",
                    (ingest_id,),
                ).fetchone()
                if claimed_row is not None:
                    claimed.append(dict(claimed_row))
            self._conn.commit()
            return claimed

    def complete_ingest(self, ingest_id: int, *, facts_written: int = 0) -> None:
        with self._lock:
            now = _utc_now_sql()
            processed_count = int(self._get_state("ingest_processed_count") or "0") + 1
            self._conn.execute(
                "DELETE FROM understanding_ingest_queue WHERE ingest_id = ?",
                (ingest_id,),
            )
            self._set_state("last_ingest_success_at", now)
            self._set_state("last_ingest_error_summary", "")
            self._set_state("ingest_processed_count", str(processed_count))
            self._set_state("last_ingest_facts_written", str(max(0, int(facts_written))))
            self._conn.commit()

    def fail_ingest(self, ingest_id: int, error: str, *, retry_delay_seconds: int = 60) -> None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT attempt_count
                FROM understanding_ingest_queue
                WHERE ingest_id = ?
                """,
                (ingest_id,),
            ).fetchone()
            if row is None:
                return

            attempts = max(1, int(row["attempt_count"]))
            next_delay = min(
                max(1, int(retry_delay_seconds)) * (2 ** max(0, attempts - 1)),
                _MAX_BACKOFF_SECONDS,
            )
            next_at = datetime.now(timezone.utc) + timedelta(seconds=next_delay)
            next_at_sql = next_at.strftime("%Y-%m-%d %H:%M:%S")
            summary = (error or "unknown ingest failure").strip()[:240]
            now = _utc_now_sql()
            self._conn.execute(
                """
                UPDATE understanding_ingest_queue
                SET status = 'failed',
                    updated_at = ?,
                    available_at = ?,
                    last_error = ?
                WHERE ingest_id = ?
                """,
                (now, next_at_sql, summary, ingest_id),
            )
            self._set_state("last_ingest_error_summary", summary)
            self._conn.commit()

    def _recover_processing_ingest(self) -> None:
        now = _utc_now_sql()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        cur = self._conn.execute(
            """
            UPDATE understanding_ingest_queue
            SET status = 'failed',
                updated_at = ?,
                available_at = ?,
                last_error = CASE
                    WHEN trim(coalesce(last_error, '')) = ''
                    THEN 'Recovered interrupted ingest attempt'
                    ELSE last_error
                END
            WHERE status = 'processing'
              AND (started_at IS NULL OR started_at < ?)
            """,
            (now, now, cutoff),
        )
        if cur.rowcount:
            self._set_state(
                "last_ingest_error_summary",
                "Recovered interrupted ingest attempt",
            )

    def _get_state(self, key: str) -> str:
        row = self._conn.execute(
            "SELECT state_value FROM understanding_state WHERE state_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return ""
        return str(row["state_value"] or "")

    def _set_state(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO understanding_state (state_key, state_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                state_value = excluded.state_value,
                updated_at = excluded.updated_at
            """,
            (key, value, _utc_now_sql()),
        )

    def index_status(self) -> dict:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            enriched = self._conn.execute(
                "SELECT COUNT(*) FROM facts WHERE metadata_json IS NOT NULL AND metadata_json != '' AND metadata_json != '{}'"
            ).fetchone()[0]
            embedded = self._conn.execute(
                "SELECT COUNT(*) FROM facts WHERE embedding_vector IS NOT NULL"
            ).fetchone()[0]
            hrr_ready = self._conn.execute(
                "SELECT COUNT(*) FROM facts WHERE hrr_vector IS NOT NULL"
            ).fetchone()[0]
            linked = self._conn.execute("SELECT COUNT(*) FROM fact_links").fetchone()[0]
            latest = self._conn.execute("SELECT MAX(updated_at) FROM facts").fetchone()[0]
            pending = self._conn.execute(
                "SELECT COUNT(*) FROM understanding_ingest_queue WHERE status = 'pending'"
            ).fetchone()[0]
            failed = self._conn.execute(
                "SELECT COUNT(*) FROM understanding_ingest_queue WHERE status = 'failed'"
            ).fetchone()[0]
            processing = self._conn.execute(
                "SELECT COUNT(*) FROM understanding_ingest_queue WHERE status = 'processing'"
            ).fetchone()[0]
            oldest_pending = self._conn.execute(
                """
                SELECT MIN(created_at)
                FROM understanding_ingest_queue
                WHERE status IN ('pending', 'failed', 'processing')
                """
            ).fetchone()[0]

        return {
            "db_path": str(self.db_path),
            "facts": int(total),
            "enriched_facts": int(enriched),
            "embedded_facts": int(embedded),
            "hrr_ready_facts": int(hrr_ready),
            "links": int(linked),
            "embedding_provider": getattr(self._embedding_provider, "name", "none"),
            "embedding_available": bool(self._embedding_provider.is_available()),
            "embedding_model": getattr(self._embedding_provider, "model", ""),
            "latest_update": latest,
            "link_threshold": self._link_threshold,
            "pending_ingest_items": int(pending),
            "failed_ingest_items": int(failed),
            "processing_ingest_items": int(processing),
            "oldest_pending_ingest": oldest_pending,
            "last_ingest_success": self._get_state("last_ingest_success_at") or None,
            "last_ingest_error": self._get_state("last_ingest_error_summary") or None,
            "ingest_enqueue_rejected": int(self._get_state("ingest_enqueue_rejected_count") or "0"),
            "reindex_status": self._get_state("reindex_status") or "idle",
            "reindex_started_at": self._get_state("reindex_started_at") or None,
            "reindex_completed_at": self._get_state("reindex_completed_at") or None,
            "reindex_error": self._get_state("reindex_error") or None,
        }

    def rebuild_understanding_index(
        self,
        *,
        include_embeddings: bool = True,
        refresh_links: bool = True,
    ) -> dict:
        with self._lock:
            started_at = _utc_now_sql()
            self._set_state("reindex_status", "running")
            self._set_state("reindex_started_at", started_at)
            self._set_state("reindex_error", "")
            self._conn.commit()

            try:
                rows = self._conn.execute(
                    """
                    SELECT fact_id, content, category, tags, source_channel,
                           source_confidence, intent_type, salience_score
                    FROM facts
                    ORDER BY fact_id
                    """
                ).fetchall()

                categories: set[str] = set()
                updated = 0
                embedded = 0

                if refresh_links:
                    self._conn.execute("DELETE FROM fact_links")

                for row in rows:
                    categories.add(row["category"])
                    enrichment = enrich_fact(
                        row["content"],
                        category=row["category"],
                        tags=row["tags"] or "",
                        source_channel=row["source_channel"] or "unknown",
                        intent_type=row["intent_type"] or None,
                        salience_score=row["salience_score"],
                        source_confidence=row["source_confidence"],
                    )
                    embedding_payload = {"vector": None, "dim": 0, "provider": "", "model": ""}
                    if include_embeddings:
                        embedding_payload = self._build_embedding_payload(row["content"])
                        if embedding_payload["vector"] is not None:
                            embedded += 1

                    self._conn.execute(
                        """
                        UPDATE facts
                        SET metadata_json = ?,
                            salience_score = ?,
                            source_confidence = ?,
                            source_channel = ?,
                            intent_type = ?,
                            embedding_vector = COALESCE(?, embedding_vector),
                            embedding_dim = CASE WHEN ? > 0 THEN ? ELSE embedding_dim END,
                            embedding_provider = CASE WHEN ? != '' THEN ? ELSE embedding_provider END,
                            embedding_model = CASE WHEN ? != '' THEN ? ELSE embedding_model END
                        WHERE fact_id = ?
                        """,
                        (
                            json.dumps(enrichment.to_dict(), ensure_ascii=False),
                            enrichment.salience_score,
                            enrichment.source_confidence,
                            enrichment.source_channel,
                            enrichment.intent_type,
                            embedding_payload["vector"],
                            embedding_payload["dim"],
                            embedding_payload["dim"],
                            embedding_payload["provider"],
                            embedding_payload["provider"],
                            embedding_payload["model"],
                            embedding_payload["model"],
                            row["fact_id"],
                        ),
                    )
                    self._refresh_fact_entities(row["fact_id"], enrichment.entities)
                    self._compute_hrr_vector(row["fact_id"], row["content"], commit=False)
                    updated += 1

                for category in categories:
                    self._rebuild_bank(category, commit=False)

                if refresh_links:
                    for row in rows:
                        self._refresh_links_for_fact(row["fact_id"], commit=False)

                completed_at = _utc_now_sql()
                self._set_state("reindex_status", "completed")
                self._set_state("reindex_completed_at", completed_at)
                self._conn.commit()
            except Exception as exc:
                self._set_state("reindex_status", "failed")
                self._set_state("reindex_error", str(exc)[:240])
                self._conn.commit()
                raise

        return {
            "facts_reindexed": updated,
            "embedded_facts": embedded,
            "links_rebuilt": refresh_links,
            "embedding_provider": getattr(self._embedding_provider, "name", "none"),
            "reindex_started_at": started_at,
            "reindex_completed_at": completed_at,
        }

    def record_feedback(self, fact_id: int, helpful: bool) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT fact_id, trust_score, helpful_count FROM facts WHERE fact_id = ?",
                (fact_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"fact_id {fact_id} not found")

            old_trust: float = row["trust_score"]
            delta = _HELPFUL_DELTA if helpful else _UNHELPFUL_DELTA
            new_trust = _clamp_trust(old_trust + delta)
            helpful_increment = 1 if helpful else 0

            self._conn.execute(
                """
                UPDATE facts
                SET trust_score = ?,
                    helpful_count = helpful_count + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE fact_id = ?
                """,
                (new_trust, helpful_increment, fact_id),
            )
            self._conn.commit()

            return {
                "fact_id": fact_id,
                "old_trust": old_trust,
                "new_trust": new_trust,
                "helpful_count": row["helpful_count"] + helpful_increment,
            }

    # ------------------------------------------------------------------
    # Entity helpers
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> list[str]:
        return extract_entities(text)

    @staticmethod
    def _merge_aliases(raw_aliases: str, value: str) -> str:
        aliases = [alias.strip() for alias in (raw_aliases or "").split(",") if alias.strip()]
        lower_aliases = {alias.lower() for alias in aliases}
        candidate = value.strip()
        if candidate and candidate.lower() not in lower_aliases:
            aliases.append(candidate)
        return ",".join(aliases)

    def _resolve_entity(self, name: str, *, commit: bool = True) -> int:
        canonical_key = canonicalize_key(name)
        if canonical_key:
            row = self._conn.execute(
                """
                SELECT entity_id, name, aliases, canonical_key
                FROM entities
                WHERE canonical_key = ?
                """,
                (canonical_key,),
            ).fetchone()
            if row is not None:
                updated_aliases = self._merge_aliases(row["aliases"], name)
                if updated_aliases != (row["aliases"] or ""):
                    self._conn.execute(
                        "UPDATE entities SET aliases = ? WHERE entity_id = ?",
                        (updated_aliases, row["entity_id"]),
                    )
                    if commit:
                        self._conn.commit()
                return int(row["entity_id"])

        row = self._conn.execute(
            "SELECT entity_id, canonical_key FROM entities WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone()
        if row is not None:
            if canonical_key and not row["canonical_key"]:
                self._conn.execute(
                    "UPDATE entities SET canonical_key = ? WHERE entity_id = ?",
                    (canonical_key, row["entity_id"]),
                )
                if commit:
                    self._conn.commit()
            return int(row["entity_id"])

        alias_row = self._conn.execute(
            """
            SELECT entity_id, canonical_key FROM entities
            WHERE ',' || lower(aliases) || ',' LIKE '%,' || lower(?) || ',%'
            """,
            (name,),
        ).fetchone()
        if alias_row is not None:
            if canonical_key and not alias_row["canonical_key"]:
                self._conn.execute(
                    "UPDATE entities SET canonical_key = ? WHERE entity_id = ?",
                    (canonical_key, alias_row["entity_id"]),
                )
                if commit:
                    self._conn.commit()
            return int(alias_row["entity_id"])

        cur = self._conn.execute(
            "INSERT INTO entities (name, canonical_key) VALUES (?, ?)",
            (name, canonical_key),
        )
        if commit:
            self._conn.commit()
        return int(cur.lastrowid)  # type: ignore[return-value]

    def _refresh_fact_entities(self, fact_id: int, entities: list[str]) -> None:
        self._conn.execute("DELETE FROM fact_entities WHERE fact_id = ?", (fact_id,))
        for name in entities:
            entity_id = self._resolve_entity(name, commit=False)
            self._conn.execute(
                """
                INSERT OR IGNORE INTO fact_entities (fact_id, entity_id)
                VALUES (?, ?)
                """,
                (fact_id, entity_id),
            )

    # ------------------------------------------------------------------
    # Vectors and linking
    # ------------------------------------------------------------------

    def _build_embedding_payload(self, content: str) -> dict:
        provider = self._embedding_provider
        if not provider or not provider.is_available():
            return {"vector": None, "dim": 0, "provider": "", "model": ""}

        vector = provider.embed_one(content)
        if not vector:
            return {"vector": None, "dim": 0, "provider": "", "model": ""}

        return {
            "vector": vector_to_bytes(vector),
            "dim": len(vector),
            "provider": getattr(provider, "name", ""),
            "model": getattr(provider, "model", ""),
        }

    def _compute_hrr_vector(self, fact_id: int, content: str, *, commit: bool = True) -> None:
        if not self._hrr_available:
            return

        rows = self._conn.execute(
            """
            SELECT e.name FROM entities e
            JOIN fact_entities fe ON fe.entity_id = e.entity_id
            WHERE fe.fact_id = ?
            """,
            (fact_id,),
        ).fetchall()
        entities = [row["name"] for row in rows]

        vector = hrr.encode_fact(content, entities, self.hrr_dim)
        self._conn.execute(
            "UPDATE facts SET hrr_vector = ? WHERE fact_id = ?",
            (hrr.phases_to_bytes(vector), fact_id),
        )
        if commit:
            self._conn.commit()

    def _rebuild_bank(self, category: str, *, commit: bool = True) -> None:
        if not self._hrr_available:
            return

        bank_name = f"cat:{category}"
        rows = self._conn.execute(
            "SELECT hrr_vector FROM facts WHERE category = ? AND hrr_vector IS NOT NULL",
            (category,),
        ).fetchall()

        if not rows:
            self._conn.execute("DELETE FROM memory_banks WHERE bank_name = ?", (bank_name,))
            if commit:
                self._conn.commit()
            return

        vectors = [hrr.bytes_to_phases(row["hrr_vector"]) for row in rows]
        bank_vector = hrr.bundle(*vectors)
        fact_count = len(vectors)
        hrr.snr_estimate(self.hrr_dim, fact_count)

        self._conn.execute(
            """
            INSERT INTO memory_banks (bank_name, vector, dim, fact_count, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(bank_name) DO UPDATE SET
                vector = excluded.vector,
                dim = excluded.dim,
                fact_count = excluded.fact_count,
                updated_at = excluded.updated_at
            """,
            (bank_name, hrr.phases_to_bytes(bank_vector), self.hrr_dim, fact_count),
        )
        if commit:
            self._conn.commit()

    def rebuild_all_vectors(self, dim: int | None = None) -> int:
        with self._lock:
            if not self._hrr_available:
                return 0

            if dim is not None:
                self.hrr_dim = dim

            rows = self._conn.execute(
                "SELECT fact_id, content, category FROM facts"
            ).fetchall()
            categories: set[str] = set()
            for row in rows:
                self._compute_hrr_vector(row["fact_id"], row["content"], commit=False)
                categories.add(row["category"])
            for category in categories:
                self._rebuild_bank(category, commit=False)
            self._conn.commit()
            return len(rows)

    def _refresh_links_for_fact(self, fact_id: int, *, commit: bool = True) -> None:
        row = self._conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
        if row is None:
            return

        base_fact = dict(row)
        self._conn.execute(
            "DELETE FROM fact_links WHERE fact_id = ? OR related_fact_id = ?",
            (fact_id, fact_id),
        )

        candidates = self._conn.execute(
            """
            SELECT * FROM facts
            WHERE fact_id != ?
            ORDER BY updated_at DESC, salience_score DESC
            LIMIT ?
            """,
            (fact_id, _MAX_LINK_SCAN),
        ).fetchall()

        for candidate in candidates:
            score, link_type, reason = self._link_score(base_fact, dict(candidate))
            if score < self._link_threshold:
                continue
            left_id, right_id = sorted((fact_id, candidate["fact_id"]))
            self._conn.execute(
                """
                INSERT OR REPLACE INTO fact_links (
                    fact_id, related_fact_id, link_type, strength, reason,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (left_id, right_id, link_type, score, reason),
            )

        if commit:
            self._conn.commit()

    def _link_score(self, left: dict, right: dict) -> tuple[float, str, str]:
        left_meta = self._parse_metadata(left.get("metadata_json"))
        right_meta = self._parse_metadata(right.get("metadata_json"))

        left_entities = set(left_meta.get("entity_keys", left_meta.get("entities", [])))
        right_entities = set(right_meta.get("entity_keys", right_meta.get("entities", [])))
        left_projects = set(left_meta.get("project_keys", left_meta.get("projects", [])))
        right_projects = set(right_meta.get("project_keys", right_meta.get("projects", [])))
        left_topics = set(left_meta.get("topic_keys", left_meta.get("topics", [])))
        right_topics = set(right_meta.get("topic_keys", right_meta.get("topics", [])))

        shared_entities = sorted(left_entities & right_entities)
        shared_projects = sorted(left_projects & right_projects)
        shared_topics = sorted(left_topics & right_topics)

        score = 0.0
        reasons: list[str] = []
        link_type = "related"

        if shared_entities:
            score += min(0.45, 0.22 + (0.14 * len(shared_entities)))
            link_type = "entity"
            reasons.append(f"shared entities: {', '.join(shared_entities[:3])}")

        if shared_projects:
            score += min(0.5, 0.24 + (0.14 * len(shared_projects)))
            link_type = "project"
            reasons.append(f"shared projects: {', '.join(shared_projects[:3])}")

        if shared_topics:
            score += min(0.2, 0.05 * len(shared_topics))
            if link_type == "related":
                link_type = "topic"
            reasons.append(f"shared topics: {', '.join(shared_topics[:4])}")

        semantic_similarity = self._semantic_similarity(left, right)
        if semantic_similarity >= 0.72:
            score += 0.25 * semantic_similarity
            if link_type == "related":
                link_type = "semantic"
            reasons.append(f"semantic similarity {semantic_similarity:.2f}")

        return min(1.0, score), link_type, "; ".join(reasons)

    def _semantic_similarity(self, left: dict, right: dict) -> float:
        scores: list[float] = []

        if self._hrr_available and left.get("hrr_vector") and right.get("hrr_vector"):
            left_vec = hrr.bytes_to_phases(left["hrr_vector"])
            right_vec = hrr.bytes_to_phases(right["hrr_vector"])
            scores.append((hrr.similarity(left_vec, right_vec) + 1.0) / 2.0)

        left_emb = bytes_to_vector(left.get("embedding_vector"))
        right_emb = bytes_to_vector(right.get("embedding_vector"))
        if left_emb and right_emb and len(left_emb) == len(right_emb):
            scores.append((cosine_similarity(left_emb, right_emb) + 1.0) / 2.0)

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        result = dict(row)
        result["metadata"] = self._parse_metadata(result.pop("metadata_json", None))
        result.pop("hrr_vector", None)
        result.pop("embedding_vector", None)
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
