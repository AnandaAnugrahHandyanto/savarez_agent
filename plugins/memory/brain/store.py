"""Local SQLite brain store for Hermes brain-first memory.

The store starts with source-isolated durable facts and now also supports
source-scoped documents/chunks for richer company-brain imports.  Facts stay
small and high-signal; document chunks preserve file provenance, line ranges,
repo commits, and supersession state so future imports can replace old chunks
without bleeding across sources.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_SOURCES: Dict[str, Dict[str, str]] = {
    "personal": {
        "title": "Personal",
        "description": "Christian-specific private preferences, identity context, and Friday operating memory.",
        "owner_kind": "personal",
        "default_visibility": "private",
    },
    "altcoinist": {
        "title": "Altcoinist",
        "description": "Altcoinist company, product, team, support, metrics, and strategy knowledge.",
        "owner_kind": "company",
        "default_visibility": "private",
    },
    "marktr": {
        "title": "Marktr",
        "description": "Marktr company knowledge and operating context. Kept separate from Altcoinist.",
        "owner_kind": "company",
        "default_visibility": "private",
    },
    "hermes": {
        "title": "Hermes",
        "description": "Hermes Agent implementation, configuration, skills, tools, and architecture knowledge.",
        "owner_kind": "agent_system",
        "default_visibility": "private",
    },
    "openclaw": {
        "title": "OpenClaw",
        "description": "OpenClaw implementation, legacy Friday architecture, and migration knowledge.",
        "owner_kind": "agent_system",
        "default_visibility": "private",
    },
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT DEFAULT '',
    owner_kind         TEXT DEFAULT 'unknown',
    default_visibility TEXT DEFAULT 'private',
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facts (
    fact_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id          TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    content            TEXT NOT NULL,
    normalized_content TEXT NOT NULL,
    kind               TEXT NOT NULL DEFAULT 'note',
    confidence         REAL NOT NULL DEFAULT 0.7,
    notability         TEXT NOT NULL DEFAULT 'medium',
    provenance         TEXT DEFAULT '',
    visibility         TEXT NOT NULL DEFAULT 'private',
    valid_from         TEXT DEFAULT '',
    valid_until        TEXT DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, normalized_content)
);

CREATE INDEX IF NOT EXISTS idx_brain_facts_source ON facts(source_id);
CREATE INDEX IF NOT EXISTS idx_brain_facts_kind ON facts(kind);
CREATE INDEX IF NOT EXISTS idx_brain_facts_confidence ON facts(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_brain_facts_updated ON facts(updated_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
    USING fts5(content, kind, provenance, content='facts', content_rowid='fact_id');

CREATE TRIGGER IF NOT EXISTS brain_facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content, kind, provenance)
        VALUES (new.fact_id, new.content, new.kind, new.provenance);
END;

CREATE TRIGGER IF NOT EXISTS brain_facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, kind, provenance)
        VALUES ('delete', old.fact_id, old.content, old.kind, old.provenance);
END;

CREATE TRIGGER IF NOT EXISTS brain_facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, kind, provenance)
        VALUES ('delete', old.fact_id, old.content, old.kind, old.provenance);
    INSERT INTO facts_fts(rowid, content, kind, provenance)
        VALUES (new.fact_id, new.content, new.kind, new.provenance);
END;

CREATE TABLE IF NOT EXISTS documents (
    document_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id             TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    path                  TEXT NOT NULL,
    title                 TEXT NOT NULL DEFAULT '',
    kind                  TEXT NOT NULL DEFAULT 'document',
    repo                  TEXT NOT NULL DEFAULT '',
    repo_commit           TEXT NOT NULL DEFAULT '',
    content_hash          TEXT NOT NULL,
    metadata              TEXT DEFAULT '',
    visibility            TEXT NOT NULL DEFAULT 'private',
    is_active             INTEGER NOT NULL DEFAULT 1,
    supersedes_document_id INTEGER REFERENCES documents(document_id) ON DELETE SET NULL,
    superseded_at         TEXT DEFAULT '',
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, path, repo, repo_commit, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_brain_documents_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_brain_documents_path ON documents(source_id, path);
CREATE INDEX IF NOT EXISTS idx_brain_documents_active ON documents(source_id, is_active);
CREATE INDEX IF NOT EXISTS idx_brain_documents_commit ON documents(repo_commit);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id           INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    source_id             TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    path                  TEXT NOT NULL,
    section               TEXT NOT NULL DEFAULT '',
    line_start            INTEGER NOT NULL DEFAULT 0,
    line_end              INTEGER NOT NULL DEFAULT 0,
    chunk_index           INTEGER NOT NULL DEFAULT 0,
    content               TEXT NOT NULL,
    normalized_content    TEXT NOT NULL,
    kind                  TEXT NOT NULL DEFAULT 'document_chunk',
    confidence            REAL NOT NULL DEFAULT 0.75,
    notability            TEXT NOT NULL DEFAULT 'medium',
    provenance            TEXT DEFAULT '',
    visibility            TEXT NOT NULL DEFAULT 'private',
    repo                  TEXT NOT NULL DEFAULT '',
    repo_commit           TEXT NOT NULL DEFAULT '',
    content_hash          TEXT NOT NULL,
    is_active             INTEGER NOT NULL DEFAULT 1,
    supersedes_chunk_id   INTEGER REFERENCES document_chunks(chunk_id) ON DELETE SET NULL,
    superseded_at         TEXT DEFAULT '',
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, path, repo, repo_commit, section, line_start, line_end, normalized_content, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_source ON document_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_path ON document_chunks(source_id, path);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_active ON document_chunks(source_id, is_active);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_kind ON document_chunks(kind);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_commit ON document_chunks(repo_commit);
CREATE INDEX IF NOT EXISTS idx_brain_chunks_location ON document_chunks(source_id, path, section, line_start, line_end);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
    USING fts5(content, kind, path, section, provenance, content='document_chunks', content_rowid='chunk_id');

CREATE TRIGGER IF NOT EXISTS brain_chunks_ai AFTER INSERT ON document_chunks BEGIN
    INSERT INTO chunks_fts(rowid, content, kind, path, section, provenance)
        VALUES (new.chunk_id, new.content, new.kind, new.path, new.section, new.provenance);
END;

CREATE TRIGGER IF NOT EXISTS brain_chunks_ad AFTER DELETE ON document_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, kind, path, section, provenance)
        VALUES ('delete', old.chunk_id, old.content, old.kind, old.path, old.section, old.provenance);
END;

CREATE TRIGGER IF NOT EXISTS brain_chunks_au AFTER UPDATE ON document_chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, kind, path, section, provenance)
        VALUES ('delete', old.chunk_id, old.content, old.kind, old.path, old.section, old.provenance);
    INSERT INTO chunks_fts(rowid, content, kind, path, section, provenance)
        VALUES (new.chunk_id, new.content, new.kind, new.path, new.section, new.provenance);
END;

CREATE TABLE IF NOT EXISTS maintenance_log (
    entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id  TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    summary    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

BRAIN_SCHEMA_VERSION = 3

_WORD_RE = re.compile(r"[\w][\w\-']*", re.UNICODE)
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_KEY_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)\b")
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*([\"']?)[^\s\"']{8,}\2"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)xox[baprs]-[A-Za-z0-9\-]{10,}"),
)


def redact_secret_text(text: str) -> tuple[str, int]:
    """Return ``text`` with obvious secret values replaced by ``[REDACTED]``."""
    hits = 0
    for pattern in _SECRET_VALUE_PATTERNS:
        text, count = pattern.subn("[REDACTED]", text)
        hits += count
    return text, hits


def redact_secrets(value: Any) -> tuple[Any, int]:
    """Recursively redact obvious secret values before they reach SQLite."""
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, dict):
        total = 0
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            new_key, key_hits = redact_secrets(key) if isinstance(key, str) else (key, 0)
            if isinstance(key, str) and _SECRET_KEY_RE.search(key):
                new_item, item_hits = "[REDACTED]", 1
            else:
                new_item, item_hits = redact_secrets(item)
            total += key_hits + item_hits
            redacted[new_key] = new_item
        return redacted, total
    if isinstance(value, list):
        total = 0
        redacted_items = []
        for item in value:
            new_item, hits = redact_secrets(item)
            total += hits
            redacted_items.append(new_item)
        return redacted_items, total
    if isinstance(value, tuple):
        redacted_list, hits = redact_secrets(list(value))
        return tuple(redacted_list), hits
    return value, 0


def utc_now() -> str:
    """Return a stable UTC ISO timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_content(content: str) -> str:
    """Normalize content for source-local deduplication."""
    return re.sub(r"\s+", " ", content.strip()).casefold()


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def serialize_provenance(provenance: Any) -> str:
    if provenance is None:
        return ""
    if isinstance(provenance, str):
        return provenance.strip()
    try:
        return json.dumps(provenance, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(provenance)


def deserialize_jsonish(value: Any) -> Any:
    if value is None or value == "":
        return {}
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {"raw": value}


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sql_identifier(identifier: str) -> str:
    """Return a validated SQLite identifier for internal migration SQL."""
    if not _SQL_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return identifier


class BrainStore:

    """Profile-scoped local brain store.

    The store treats ``source_id`` as a hard partition.  All writes require a
    source and all recall can be restricted to one source; tests assert that
    company sources do not bleed into each other.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            from hermes_constants import get_hermes_home

            db_path = get_hermes_home() / "brain" / "brain.db"
        self.db_path = Path(db_path).expanduser()
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._chmod_private(self.db_path.parent, 0o700)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._harden_db_files()

    def _init_db(self) -> None:
        from hermes_state import apply_wal_with_fallback

        with self._lock:
            apply_wal_with_fallback(self._conn, db_label="brain.db")
            self._conn.execute("PRAGMA secure_delete=ON")
            self._conn.execute("PRAGMA foreign_keys=ON")
            old_version = int(self._conn.execute("PRAGMA user_version").fetchone()[0] or 0)
            if old_version < BRAIN_SCHEMA_VERSION:
                self._migrate_legacy_schema()
            self._conn.executescript(_SCHEMA)
            self.seed_default_sources()
            if old_version < BRAIN_SCHEMA_VERSION:
                self._drop_fact_fts_infrastructure()
                self._drop_chunk_fts_infrastructure()
                self._redact_existing_fact_rows()
                self._redact_existing_document_rows()
                self._conn.executescript(_SCHEMA)
                self._rebuild_fts_indexes()
                self._conn.execute("PRAGMA user_version = " + str(int(BRAIN_SCHEMA_VERSION)))
            self._conn.commit()
            if old_version < BRAIN_SCHEMA_VERSION:
                self._scrub_deleted_pages()
            self._harden_db_files()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _chmod_private(path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except OSError:
            # Best effort: unsupported filesystems should not break provider init.
            pass

    def _harden_db_files(self) -> None:
        for path in (self.db_path, Path(f"{self.db_path}-wal"), Path(f"{self.db_path}-shm")):
            if path.exists():
                self._chmod_private(path, 0o600)

    def _scrub_deleted_pages(self) -> None:
        """Best-effort purge of deleted legacy bytes after redaction migrations."""
        # VACUUM cannot run inside a transaction; callers commit before this.
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        try:
            self._conn.execute("VACUUM")
        except sqlite3.Error:
            pass
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self._conn.commit()
        self._harden_db_files()

    def _table_exists(self, table: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _columns(self, table: str) -> set[str]:
        if not self._table_exists(table):
            return set()
        table_name = sql_identifier(table)
        return {str(row["name"]) for row in self._conn.execute("PRAGMA table_info(" + table_name + ")").fetchall()}

    def _unique_index_columns(self, table: str) -> list[list[str]]:
        """Return column lists for unique indexes/constraints on an internal table."""
        if not self._table_exists(table):
            return []
        table_name = sql_identifier(table)
        indexes = self._conn.execute("PRAGMA index_list(" + table_name + ")").fetchall()
        unique_columns: list[list[str]] = []
        for index in indexes:
            if int(index["unique"] or 0) != 1:
                continue
            index_name = sql_identifier(str(index["name"]))
            columns = [
                str(row["name"])
                for row in self._conn.execute("PRAGMA index_info(" + index_name + ")").fetchall()
                if row["name"] is not None
            ]
            if columns:
                unique_columns.append(columns)
        return unique_columns

    def _has_unique_columns(self, table: str, columns: list[str]) -> bool:
        return columns in self._unique_index_columns(table)

    def _copy_existing_columns(self, source_table: str, target_table: str, ordered_columns: list[str]) -> None:
        source_columns = self._columns(source_table)
        target_columns = self._columns(target_table)
        columns = [column for column in ordered_columns if column in source_columns and column in target_columns]
        if not columns:
            return
        column_sql = ", ".join(sql_identifier(column) for column in columns)
        source_name = sql_identifier(source_table)
        target_name = sql_identifier(target_table)
        self._conn.execute(
            "INSERT OR IGNORE INTO " + target_name + " (" + column_sql + ") SELECT " + column_sql + " FROM " + source_name
        )

    def _drop_fact_fts_infrastructure(self) -> None:
        for trigger in ("brain_facts_ai", "brain_facts_ad", "brain_facts_au"):
            self._conn.execute("DROP TRIGGER IF EXISTS " + sql_identifier(trigger))
        if self._table_exists("facts_fts"):
            self._conn.execute("DROP TABLE " + sql_identifier("facts_fts"))

    def _drop_chunk_fts_infrastructure(self) -> None:
        for trigger in ("brain_chunks_ai", "brain_chunks_ad", "brain_chunks_au"):
            self._conn.execute("DROP TRIGGER IF EXISTS " + sql_identifier(trigger))
        if self._table_exists("chunks_fts"):
            self._conn.execute("DROP TABLE " + sql_identifier("chunks_fts"))

    def _copy_legacy_documents_redacted(self, source_table: str) -> None:
        source_name = sql_identifier(source_table)
        rows = self._conn.execute(
            """
            SELECT document_id, source_id, path, title, kind, repo, repo_commit, content_hash,
                   metadata, visibility, is_active, supersedes_document_id, superseded_at,
                   created_at, updated_at
            FROM """ + source_name
        ).fetchall()
        for row in rows:
            path, _ = redact_secret_text(str(row["path"] or ""))
            title, _ = redact_secret_text(str(row["title"] or ""))
            repo, _ = redact_secret_text(str(row["repo"] or ""))
            repo_commit, _ = redact_secret_text(str(row["repo_commit"] or ""))
            metadata, _ = redact_secrets(deserialize_jsonish(row["metadata"] or ""))
            self._conn.execute(
                """
                INSERT OR IGNORE INTO documents (
                    document_id, source_id, path, title, kind, repo, repo_commit, content_hash,
                    metadata, visibility, is_active, supersedes_document_id, superseded_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["document_id"]),
                    row["source_id"],
                    path,
                    title,
                    row["kind"],
                    repo,
                    repo_commit,
                    row["content_hash"],
                    serialize_provenance(metadata),
                    row["visibility"],
                    int(row["is_active"] or 0),
                    row["supersedes_document_id"],
                    row["superseded_at"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _copy_legacy_chunks_redacted(self, source_table: str) -> None:
        source_name = sql_identifier(source_table)
        rows = self._conn.execute(
            """
            SELECT chunk_id, document_id, source_id, path, section, line_start, line_end,
                   chunk_index, content, kind, confidence, notability, provenance,
                   visibility, repo, repo_commit, content_hash, is_active,
                   supersedes_chunk_id, superseded_at, created_at, updated_at
            FROM """ + source_name
        ).fetchall()
        for row in rows:
            path, _ = redact_secret_text(str(row["path"] or ""))
            section, _ = redact_secret_text(str(row["section"] or ""))
            repo, _ = redact_secret_text(str(row["repo"] or ""))
            repo_commit, _ = redact_secret_text(str(row["repo_commit"] or ""))
            content, _ = redact_secret_text(str(row["content"] or ""))
            provenance, _ = redact_secrets(deserialize_jsonish(row["provenance"] or ""))
            self._conn.execute(
                """
                INSERT OR IGNORE INTO document_chunks (
                    chunk_id, document_id, source_id, path, section, line_start, line_end,
                    chunk_index, content, normalized_content, kind, confidence, notability,
                    provenance, visibility, repo, repo_commit, content_hash, is_active,
                    supersedes_chunk_id, superseded_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["chunk_id"]),
                    int(row["document_id"]),
                    row["source_id"],
                    path,
                    section,
                    int(row["line_start"] or 0),
                    int(row["line_end"] or 0),
                    int(row["chunk_index"] or 0),
                    content,
                    normalize_content(content),
                    row["kind"],
                    float(row["confidence"] or 0.0),
                    row["notability"],
                    serialize_provenance(provenance),
                    row["visibility"],
                    repo,
                    repo_commit,
                    row["content_hash"],
                    int(row["is_active"] or 0),
                    row["supersedes_chunk_id"],
                    row["superseded_at"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

    def _redact_existing_fact_rows(self) -> None:
        if not self._table_exists("facts"):
            return
        rows = self._conn.execute("SELECT fact_id, content, provenance FROM facts").fetchall()
        for row in rows:
            content, _ = redact_secret_text(str(row["content"] or ""))
            provenance, _ = redact_secrets(deserialize_jsonish(row["provenance"] or ""))
            self._conn.execute(
                """
                UPDATE facts
                SET content = ?, normalized_content = ?, provenance = ?
                WHERE fact_id = ?
                """,
                (content, normalize_content(content), serialize_provenance(provenance), int(row["fact_id"])),
            )

    def _redact_existing_document_rows(self) -> None:
        """Scrub legacy document rows before FTS rebuilds can surface secrets."""
        if self._table_exists("documents"):
            rows = self._conn.execute(
                "SELECT document_id, path, title, repo, repo_commit, metadata FROM documents"
            ).fetchall()
            for row in rows:
                path, _ = redact_secret_text(str(row["path"] or ""))
                title, _ = redact_secret_text(str(row["title"] or ""))
                repo, _ = redact_secret_text(str(row["repo"] or ""))
                repo_commit, _ = redact_secret_text(str(row["repo_commit"] or ""))
                metadata, _ = redact_secrets(deserialize_jsonish(row["metadata"] or ""))
                self._conn.execute(
                    """
                    UPDATE documents
                    SET path = ?, title = ?, repo = ?, repo_commit = ?, metadata = ?
                    WHERE document_id = ?
                    """,
                    (path, title, repo, repo_commit, serialize_provenance(metadata), int(row["document_id"])),
                )
        if self._table_exists("document_chunks"):
            rows = self._conn.execute(
                """
                SELECT chunk_id, path, section, repo, repo_commit, content, provenance
                FROM document_chunks
                """
            ).fetchall()
            for row in rows:
                path, _ = redact_secret_text(str(row["path"] or ""))
                section, _ = redact_secret_text(str(row["section"] or ""))
                repo, _ = redact_secret_text(str(row["repo"] or ""))
                repo_commit, _ = redact_secret_text(str(row["repo_commit"] or ""))
                content, _ = redact_secret_text(str(row["content"] or ""))
                provenance, _ = redact_secrets(deserialize_jsonish(row["provenance"] or ""))
                self._conn.execute(
                    """
                    UPDATE document_chunks
                    SET path = ?, section = ?, repo = ?, repo_commit = ?, content = ?,
                        normalized_content = ?, provenance = ?
                    WHERE chunk_id = ?
                    """,
                    (
                        path,
                        section,
                        repo,
                        repo_commit,
                        content,
                        normalize_content(content),
                        serialize_provenance(provenance),
                        int(row["chunk_id"]),
                    ),
                )

    def _migrate_document_repo_constraints(self) -> None:
        """Rebuild v2 document tables whose unique constraints did not include repo."""
        if not (self._table_exists("documents") and self._table_exists("document_chunks")):
            return
        documents_need_repo = self._has_unique_columns(
            "documents", ["source_id", "path", "repo_commit", "content_hash"]
        ) and not self._has_unique_columns(
            "documents", ["source_id", "path", "repo", "repo_commit", "content_hash"]
        )
        chunks_need_repo = self._has_unique_columns(
            "document_chunks",
            ["source_id", "path", "repo_commit", "section", "line_start", "line_end", "normalized_content"],
        ) and not self._has_unique_columns(
            "document_chunks",
            [
                "source_id",
                "path",
                "repo",
                "repo_commit",
                "section",
                "line_start",
                "line_end",
                "normalized_content",
                "content_hash",
            ],
        )
        if not (documents_need_repo or chunks_need_repo):
            return

        old_documents = "_brain_documents_repo_migration_old"
        old_chunks = "_brain_chunks_repo_migration_old"
        if self._table_exists(old_documents) or self._table_exists(old_chunks):
            raise RuntimeError("unfinished brain document repo-constraint migration detected")

        self._conn.execute("PRAGMA foreign_keys=OFF")
        try:
            self._drop_chunk_fts_infrastructure()
            self._conn.execute("ALTER TABLE documents RENAME TO " + sql_identifier(old_documents))
            self._conn.execute("ALTER TABLE document_chunks RENAME TO " + sql_identifier(old_chunks))
            self._conn.executescript(_SCHEMA)
            # Keep chunk FTS disabled while legacy rows are copied; rebuild FTS only from redacted rows later.
            self._drop_chunk_fts_infrastructure()
            self._copy_legacy_documents_redacted(old_documents)
            self._copy_legacy_chunks_redacted(old_chunks)
            self._redact_existing_document_rows()
            self._conn.execute("DROP TABLE " + sql_identifier(old_chunks))
            self._conn.execute("DROP TABLE " + sql_identifier(old_documents))
            # Re-run schema after dropping old indexes so repo-aware indexes/triggers exist on the rebuilt tables.
            self._conn.executescript(_SCHEMA)
        finally:
            self._conn.execute("PRAGMA foreign_keys=ON")

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        if table in {"sources", "facts"} and column not in self._columns(table):
            table_name = sql_identifier(table)
            column_name = sql_identifier(column)
            self._conn.execute("ALTER TABLE " + table_name + " ADD COLUMN " + column_name + " " + definition)

    def _migrate_legacy_schema(self) -> None:
        """Bring older facts-only brain DBs up to the current additive schema."""
        if self._table_exists("sources"):
            self._add_column_if_missing("sources", "title", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("sources", "description", "TEXT DEFAULT ''")
            self._add_column_if_missing("sources", "owner_kind", "TEXT DEFAULT 'unknown'")
            self._add_column_if_missing("sources", "default_visibility", "TEXT DEFAULT 'private'")
            self._add_column_if_missing("sources", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("sources", "updated_at", "TEXT NOT NULL DEFAULT ''")

        if self._table_exists("facts"):
            self._add_column_if_missing("facts", "normalized_content", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("facts", "kind", "TEXT NOT NULL DEFAULT 'note'")
            self._add_column_if_missing("facts", "confidence", "REAL NOT NULL DEFAULT 0.7")
            self._add_column_if_missing("facts", "notability", "TEXT NOT NULL DEFAULT 'medium'")
            self._add_column_if_missing("facts", "provenance", "TEXT DEFAULT ''")
            self._add_column_if_missing("facts", "visibility", "TEXT NOT NULL DEFAULT 'private'")
            self._add_column_if_missing("facts", "valid_from", "TEXT DEFAULT ''")
            self._add_column_if_missing("facts", "valid_until", "TEXT DEFAULT ''")
            self._add_column_if_missing("facts", "created_at", "TEXT NOT NULL DEFAULT ''")
            self._add_column_if_missing("facts", "updated_at", "TEXT NOT NULL DEFAULT ''")

            rows = self._conn.execute(
                "SELECT fact_id, content FROM facts WHERE normalized_content = '' OR normalized_content IS NULL"
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    "UPDATE facts SET normalized_content = ? WHERE fact_id = ?",
                    (normalize_content(str(row["content"] or "")), int(row["fact_id"])),
                )

        self._migrate_document_repo_constraints()

    def _rebuild_fts_indexes(self) -> None:
        for table in ("facts_fts", "chunks_fts"):
            if self._table_exists(table):
                table_name = sql_identifier(table)
                try:
                    self._conn.execute("INSERT INTO " + table_name + "(" + table_name + ") VALUES('rebuild')")
                except sqlite3.Error:
                    pass

    # -- sources ---------------------------------------------------------

    def seed_default_sources(self) -> None:
        now = utc_now()
        for source_id, data in DEFAULT_SOURCES.items():
            self._conn.execute(
                """
                INSERT INTO sources (source_id, title, description, owner_kind, default_visibility, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    owner_kind=excluded.owner_kind,
                    default_visibility=excluded.default_visibility,
                    updated_at=excluded.updated_at
                """,
                (
                    source_id,
                    data["title"],
                    data["description"],
                    data["owner_kind"],
                    data["default_visibility"],
                    now,
                    now,
                ),
            )

    def list_sources(self) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT source_id, title, description, owner_kind, default_visibility, created_at, updated_at "
                "FROM sources ORDER BY source_id"
            ).fetchall()
            return [dict(row) for row in rows]

    def source_exists(self, source_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        return row is not None

    def default_visibility(self, source_id: str) -> str:
        row = self._conn.execute(
            "SELECT default_visibility FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"unknown brain source: {source_id}")
        return str(row["default_visibility"] or "private")

    # -- facts -----------------------------------------------------------

    def write_fact(
        self,
        *,
        source_id: str,
        content: str,
        kind: str = "note",
        confidence: float = 0.7,
        notability: str = "medium",
        provenance: Any = None,
        visibility: str | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> int:
        """Write a durable source-scoped fact and return its id.

        Duplicate content in the same source returns the existing id.  The same
        content may exist in different sources because company boundaries are
        intentionally independent.
        """

        source_id = (source_id or "").strip().lower()
        content = (content or "").strip()
        content, _content_redactions = redact_secret_text(content)
        provenance, _provenance_redactions = redact_secrets(provenance)
        if not source_id:
            raise ValueError("source_id is required")
        if not content:
            raise ValueError("content must not be empty")

        with self._lock:
            if not self.source_exists(source_id):
                raise ValueError(f"unknown brain source: {source_id}")
            now = utc_now()
            normalized = normalize_content(content)
            existing = self._conn.execute(
                """
                SELECT fact_id, valid_until
                FROM facts
                WHERE source_id = ? AND normalized_content = ?
                ORDER BY fact_id
                LIMIT 1
                """,
                (source_id, normalized),
            ).fetchone()
            if existing:
                if existing["valid_until"]:
                    self._conn.execute(
                        "UPDATE facts SET valid_until = '', updated_at = ? WHERE fact_id = ?",
                        (now, int(existing["fact_id"])),
                    )
                    self._conn.commit()
                return int(existing["fact_id"])

            prov = serialize_provenance(provenance)
            fact_visibility = (visibility or self.default_visibility(source_id) or "private").strip()
            try:
                cur = self._conn.execute(
                    """
                    INSERT INTO facts (
                        source_id, content, normalized_content, kind, confidence,
                        notability, provenance, visibility, valid_from, valid_until,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        content,
                        normalized,
                        kind or "note",
                        clamp_confidence(confidence),
                        notability or "medium",
                        prov,
                        fact_visibility,
                        valid_from or now,
                        valid_until or "",
                        now,
                        now,
                    ),
                )
                self._conn.commit()
                if cur.lastrowid is None:
                    raise RuntimeError("brain fact insert did not return an id")
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                row = self._conn.execute(
                    "SELECT fact_id FROM facts WHERE source_id = ? AND normalized_content = ?",
                    (source_id, normalized),
                ).fetchone()
                if row is None:
                    raise
                return int(row["fact_id"])

    def supersede_fact(self, *, source_id: str, old_content: str, superseded_at: str | None = None) -> int:
        """Mark matching source-scoped fact content inactive for replace mirrors."""
        source_id = (source_id or "").strip().lower()
        old_content = (old_content or "").strip()
        old_content, _redactions = redact_secret_text(old_content)
        if not source_id or not old_content:
            return 0
        normalized = normalize_content(old_content)
        now = superseded_at or utc_now()
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE facts
                SET valid_until = ?, updated_at = ?
                WHERE source_id = ? AND normalized_content = ?
                  AND (valid_until IS NULL OR valid_until = '')
                """,
                (now, now, source_id, normalized),
            )
            self._conn.commit()
            return int(cur.rowcount or 0)

    def recall(
        self,
        query: str,
        *,
        source_id: str | None = None,
        mode: str = "balanced",
        limit: int = 5,
    ) -> List[dict]:
        """Recall facts using FTS5 with a safe LIKE fallback."""
        query = (query or "").strip()
        if not query:
            return []
        if source_id:
            source_id = source_id.strip().lower()
        limit = max(1, min(int(limit or 5), 50))
        min_confidence = self._min_confidence_for_mode(mode)
        if mode == "conservative":
            limit = min(limit, 10)
        elif mode == "tokenmax":
            limit = min(max(limit, 10), 50)

        with self._lock:
            try:
                return self._recall_fts(query, source_id=source_id, min_confidence=min_confidence, limit=limit)
            except sqlite3.Error:
                return self._recall_like(query, source_id=source_id, min_confidence=min_confidence, limit=limit)

    def _recall_fts(
        self,
        query: str,
        *,
        source_id: str | None,
        min_confidence: float,
        limit: int,
    ) -> List[dict]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return self._recall_like(query, source_id=source_id, min_confidence=min_confidence, limit=limit)

        where = [
            "facts_fts MATCH ?",
            "f.confidence >= ?",
            "(f.valid_until IS NULL OR f.valid_until = '' OR f.valid_until > ?)",
        ]
        params: list[Any] = [fts_query, min_confidence, utc_now()]
        if source_id:
            where.append("f.source_id = ?")
            params.append(source_id)
        params.append(limit)

        rows = self._conn.execute(
            f"""
            SELECT f.*, bm25(facts_fts) AS rank
            FROM facts_fts
            JOIN facts f ON f.fact_id = facts_fts.rowid
            WHERE {' AND '.join(where)}
            ORDER BY rank ASC, f.confidence DESC, f.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def _recall_like(
        self,
        query: str,
        *,
        source_id: str | None,
        min_confidence: float,
        limit: int,
    ) -> List[dict]:
        like = f"%{query}%"
        where = [
            "f.content LIKE ?",
            "f.confidence >= ?",
            "(f.valid_until IS NULL OR f.valid_until = '' OR f.valid_until > ?)",
        ]
        params: list[Any] = [like, min_confidence, utc_now()]
        if source_id:
            where.append("f.source_id = ?")
            params.append(source_id)
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT f.*, 0.0 AS rank
            FROM facts f
            WHERE {' AND '.join(where)}
            ORDER BY f.confidence DESC, f.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    # -- documents/chunks ------------------------------------------------

    def write_document_chunk(
        self,
        *,
        source_id: str,
        path: str,
        content: str,
        title: str = "",
        section: str = "",
        line_start: int | None = None,
        line_end: int | None = None,
        chunk_index: int = 0,
        repo: str = "",
        repo_commit: str = "",
        kind: str = "document_chunk",
        confidence: float = 0.75,
        notability: str = "medium",
        provenance: Any = None,
        metadata: Any = None,
        visibility: str | None = None,
    ) -> dict:
        """Upsert a source-scoped document chunk and supersede stale siblings.

        Exact duplicates are keyed by source, repo, repo commit, path, document
        hash, heading/line range, and normalized content.  A new chunk for the same source/path/
        heading/line range supersedes older active chunks, keeping default
        recall current while preserving inactive history for audits.
        """

        source_id = (source_id or "").strip().lower()
        path = (path or "").strip()
        path, _path_redactions = redact_secret_text(path)
        title = (title or "").strip()
        title, _title_redactions = redact_secret_text(title)
        content = (content or "").strip()
        content, _content_redactions = redact_secret_text(content)
        section = (section or "").strip()
        section, _section_redactions = redact_secret_text(section)
        repo = (repo or "").strip()
        repo, _repo_redactions = redact_secret_text(repo)
        repo_commit = (repo_commit or "").strip()
        repo_commit, _repo_commit_redactions = redact_secret_text(repo_commit)
        if not source_id:
            raise ValueError("source_id is required")
        if not path:
            raise ValueError("path is required")
        if not content:
            raise ValueError("content must not be empty")

        line_start_i = int(line_start or 0)
        line_end_i = int(line_end or 0)
        chunk_index_i = int(chunk_index or 0)
        normalized = normalize_content(content)
        metadata_obj = deserialize_jsonish(metadata)
        if not isinstance(metadata_obj, dict):
            metadata_obj = {"value": metadata_obj}
        metadata_obj, _metadata_redactions = redact_secrets(metadata_obj)
        provenance, _provenance_redactions = redact_secrets(provenance)
        document_hash = (
            metadata_obj.get("file_sha256")
            or metadata_obj.get("document_sha256")
            or metadata_obj.get("content_hash")
        )
        if not document_hash and repo_commit:
            document_hash = sha256_text("\0".join([source_id, path, repo, repo_commit]))
        content_hash = str(document_hash or sha256_text(content))
        chunk_hash = sha256_text(content)

        with self._lock:
            if not self.source_exists(source_id):
                raise ValueError(f"unknown brain source: {source_id}")
            now = utc_now()
            chunk_visibility = (visibility or self.default_visibility(source_id) or "private").strip()

            existing_active = self._conn.execute(
                """
                SELECT c.chunk_id, c.document_id
                FROM document_chunks c
                JOIN documents d ON d.document_id = c.document_id
                WHERE c.source_id = ? AND c.path = ? AND c.repo = ? AND c.repo_commit = ? AND c.section = ?
                  AND c.line_start = ? AND c.line_end = ? AND c.normalized_content = ?
                  AND c.content_hash = ? AND c.is_active = 1 AND d.is_active = 1
                LIMIT 1
                """,
                (source_id, path, repo, repo_commit, section, line_start_i, line_end_i, normalized, content_hash),
            ).fetchone()
            if existing_active:
                return {
                    "document_id": int(existing_active["document_id"]),
                    "chunk_id": int(existing_active["chunk_id"]),
                    "source": source_id,
                    "path": path,
                    "superseded_chunk_ids": [],
                    "deduped": True,
                    "is_active": True,
                }

            document_id, document_superseded_chunk_ids = self._ensure_document(
                source_id=source_id,
                path=path,
                title=title or Path(path).name,
                kind=kind or "document",
                repo=repo,
                repo_commit=repo_commit,
                content_hash=content_hash,
                metadata=metadata_obj,
                visibility=chunk_visibility,
                now=now,
            )

            existing = self._conn.execute(
                """
                SELECT chunk_id, document_id, is_active
                FROM document_chunks
                WHERE document_id = ? AND source_id = ? AND path = ? AND repo = ? AND repo_commit = ? AND section = ?
                  AND line_start = ? AND line_end = ? AND normalized_content = ? AND content_hash = ?
                LIMIT 1
                """,
                (document_id, source_id, path, repo, repo_commit, section, line_start_i, line_end_i, normalized, content_hash),
            ).fetchone()
            if existing:
                superseded_chunk_ids = list(dict.fromkeys(document_superseded_chunk_ids))
                if not bool(existing["is_active"]):
                    prov_obj = self._build_chunk_provenance(
                        provenance=provenance,
                        repo=repo,
                        repo_commit=repo_commit,
                        path=path,
                        section=section,
                        line_start=line_start_i,
                        line_end=line_end_i,
                        chunk_index=chunk_index_i,
                        content_hash=content_hash,
                        chunk_hash=chunk_hash,
                        metadata=metadata_obj,
                    )
                    self._conn.execute(
                        """
                        UPDATE document_chunks
                        SET chunk_index = ?, content = ?, normalized_content = ?, kind = ?, confidence = ?,
                            notability = ?, provenance = ?, visibility = ?, repo = ?, repo_commit = ?,
                            content_hash = ?, is_active = 1, supersedes_chunk_id = ?, superseded_at = '',
                            updated_at = ?
                        WHERE chunk_id = ?
                        """,
                        (
                            chunk_index_i,
                            content,
                            normalized,
                            kind or "document_chunk",
                            clamp_confidence(confidence),
                            notability or "medium",
                            serialize_provenance(prov_obj),
                            chunk_visibility,
                            repo,
                            repo_commit,
                            content_hash,
                            superseded_chunk_ids[0] if superseded_chunk_ids else None,
                            now,
                            int(existing["chunk_id"]),
                        ),
                    )
                self._conn.commit()
                return {
                    "document_id": int(existing["document_id"]),
                    "chunk_id": int(existing["chunk_id"]),
                    "source": source_id,
                    "path": path,
                    "superseded_chunk_ids": superseded_chunk_ids,
                    "deduped": True,
                    "is_active": True,
                }

            stale_rows = self._conn.execute(
                """
                SELECT chunk_id
                FROM document_chunks
                WHERE source_id = ? AND path = ? AND repo = ? AND section = ?
                  AND line_start = ? AND line_end = ? AND is_active = 1
                  AND NOT (repo_commit = ? AND normalized_content = ? AND content_hash = ?)
                ORDER BY chunk_id
                """,
                (source_id, path, repo, section, line_start_i, line_end_i, repo_commit, normalized, content_hash),
            ).fetchall()
            same_slice_superseded_chunk_ids = [int(row["chunk_id"]) for row in stale_rows]
            if same_slice_superseded_chunk_ids:
                self._conn.execute(
                    f"""
                    UPDATE document_chunks
                    SET is_active = 0, superseded_at = ?, updated_at = ?
                    WHERE chunk_id IN ({','.join('?' for _ in same_slice_superseded_chunk_ids)})
                    """,
                    [now, now, *same_slice_superseded_chunk_ids],
                )
            superseded_chunk_ids = list(dict.fromkeys([*document_superseded_chunk_ids, *same_slice_superseded_chunk_ids]))

            prov_obj = self._build_chunk_provenance(
                provenance=provenance,
                repo=repo,
                repo_commit=repo_commit,
                path=path,
                section=section,
                line_start=line_start_i,
                line_end=line_end_i,
                chunk_index=chunk_index_i,
                content_hash=content_hash,
                chunk_hash=chunk_hash,
                metadata=metadata_obj,
            )
            cur = self._conn.execute(
                """
                INSERT INTO document_chunks (
                    document_id, source_id, path, section, line_start, line_end, chunk_index,
                    content, normalized_content, kind, confidence, notability, provenance,
                    visibility, repo, repo_commit, content_hash, is_active,
                    supersedes_chunk_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    document_id,
                    source_id,
                    path,
                    section,
                    line_start_i,
                    line_end_i,
                    chunk_index_i,
                    content,
                    normalized,
                    kind or "document_chunk",
                    clamp_confidence(confidence),
                    notability or "medium",
                    serialize_provenance(prov_obj),
                    chunk_visibility,
                    repo,
                    repo_commit,
                    content_hash,
                    superseded_chunk_ids[0] if superseded_chunk_ids else None,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            if cur.lastrowid is None:
                raise RuntimeError("brain document chunk insert did not return an id")
            return {
                "document_id": int(document_id),
                "chunk_id": int(cur.lastrowid),
                "source": source_id,
                "path": path,
                "superseded_chunk_ids": superseded_chunk_ids,
                "deduped": False,
                "is_active": True,
            }

    def _ensure_document(
        self,
        *,
        source_id: str,
        path: str,
        title: str,
        kind: str,
        repo: str,
        repo_commit: str,
        content_hash: str,
        metadata: dict,
        visibility: str,
        now: str,
    ) -> tuple[int, list[int]]:
        metadata_text = serialize_provenance(metadata)
        existing = self._conn.execute(
            """
            SELECT document_id
            FROM documents
            WHERE source_id = ? AND path = ? AND repo = ? AND repo_commit = ? AND content_hash = ?
              AND is_active = 1
            """,
            (source_id, path, repo, repo_commit, content_hash),
        ).fetchone()
        if existing:
            return int(existing["document_id"]), []

        active_rows = self._conn.execute(
            """
            SELECT document_id
            FROM documents
            WHERE source_id = ? AND path = ? AND repo = ? AND is_active = 1
            ORDER BY document_id
            """,
            (source_id, path, repo),
        ).fetchall()
        superseded_document_ids = [int(row["document_id"]) for row in active_rows]
        superseded_chunk_ids: list[int] = []
        if superseded_document_ids:
            placeholders = ','.join('?' for _ in superseded_document_ids)
            chunk_rows = self._conn.execute(
                f"""
                SELECT chunk_id
                FROM document_chunks
                WHERE document_id IN ({placeholders}) AND is_active = 1
                ORDER BY chunk_id
                """,
                superseded_document_ids,
            ).fetchall()
            superseded_chunk_ids = [int(row["chunk_id"]) for row in chunk_rows]
            self._conn.execute(
                f"""
                UPDATE documents
                SET is_active = 0, superseded_at = ?, updated_at = ?
                WHERE document_id IN ({placeholders})
                """,
                [now, now, *superseded_document_ids],
            )
            self._conn.execute(
                f"""
                UPDATE document_chunks
                SET is_active = 0, superseded_at = ?, updated_at = ?
                WHERE document_id IN ({placeholders}) AND is_active = 1
                """,
                [now, now, *superseded_document_ids],
            )

        inactive = self._conn.execute(
            """
            SELECT document_id
            FROM documents
            WHERE source_id = ? AND path = ? AND repo = ? AND repo_commit = ? AND content_hash = ?
              AND is_active = 0
            ORDER BY document_id DESC
            LIMIT 1
            """,
            (source_id, path, repo, repo_commit, content_hash),
        ).fetchone()
        if inactive:
            document_id = int(inactive["document_id"])
            self._conn.execute(
                """
                UPDATE documents
                SET title = ?, kind = ?, metadata = ?, visibility = ?, is_active = 1,
                    supersedes_document_id = ?, superseded_at = '', updated_at = ?
                WHERE document_id = ?
                """,
                (
                    title,
                    kind or "document",
                    metadata_text,
                    visibility,
                    superseded_document_ids[0] if superseded_document_ids else None,
                    now,
                    document_id,
                ),
            )
            return document_id, superseded_chunk_ids

        cur = self._conn.execute(
            """
            INSERT INTO documents (
                source_id, path, title, kind, repo, repo_commit, content_hash,
                metadata, visibility, is_active, supersedes_document_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                source_id,
                path,
                title,
                kind or "document",
                repo,
                repo_commit,
                content_hash,
                metadata_text,
                visibility,
                superseded_document_ids[0] if superseded_document_ids else None,
                now,
                now,
            ),
        )
        if cur.lastrowid is None:
            raise RuntimeError("brain document insert did not return an id")
        return int(cur.lastrowid), superseded_chunk_ids

    @staticmethod
    def _build_chunk_provenance(
        *,
        provenance: Any,
        repo: str,
        repo_commit: str,
        path: str,
        section: str,
        line_start: int,
        line_end: int,
        chunk_index: int,
        content_hash: str,
        chunk_hash: str,
        metadata: dict,
    ) -> dict:
        base: dict[str, Any] = {
            "repo": repo,
            "repo_commit": repo_commit,
            "path": path,
            "section": section,
            "line_start": line_start,
            "line_end": line_end,
            "chunk_index": chunk_index,
            "content_hash": content_hash,
            "chunk_hash": chunk_hash,
        }
        if metadata:
            base["metadata"] = metadata
        if isinstance(provenance, dict):
            base.update(provenance)
        elif provenance:
            base["origin_note"] = str(provenance)
        return base

    def recall_documents(
        self,
        query: str,
        *,
        source_id: str | None = None,
        mode: str = "balanced",
        limit: int = 5,
        include_inactive: bool = False,
    ) -> List[dict]:
        """Recall source-filtered document chunks with provenance."""
        query = (query or "").strip()
        if not query:
            return []
        if source_id:
            source_id = source_id.strip().lower()
        limit = max(1, min(int(limit or 5), 50))
        min_confidence = self._min_confidence_for_mode(mode)
        if mode == "conservative":
            limit = min(limit, 10)
        elif mode == "tokenmax":
            limit = min(max(limit, 10), 50)

        with self._lock:
            try:
                return self._recall_documents_fts(
                    query,
                    source_id=source_id,
                    min_confidence=min_confidence,
                    limit=limit,
                    include_inactive=include_inactive,
                )
            except sqlite3.Error:
                return self._recall_documents_like(
                    query,
                    source_id=source_id,
                    min_confidence=min_confidence,
                    limit=limit,
                    include_inactive=include_inactive,
                )

    def _recall_documents_fts(
        self,
        query: str,
        *,
        source_id: str | None,
        min_confidence: float,
        limit: int,
        include_inactive: bool,
    ) -> List[dict]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return self._recall_documents_like(
                query,
                source_id=source_id,
                min_confidence=min_confidence,
                limit=limit,
                include_inactive=include_inactive,
            )
        where = ["chunks_fts MATCH ?", "c.confidence >= ?"]
        params: list[Any] = [fts_query, min_confidence]
        if source_id:
            where.append("c.source_id = ?")
            params.append(source_id)
        if not include_inactive:
            where.append("c.is_active = 1")
            where.append("d.is_active = 1")
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT c.*, d.title AS document_title, d.kind AS document_kind,
                   d.repo AS document_repo, d.repo_commit AS document_repo_commit,
                   d.content_hash AS document_content_hash, d.metadata AS document_metadata,
                   d.is_active AS document_is_active, bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN document_chunks c ON c.chunk_id = chunks_fts.rowid
            JOIN documents d ON d.document_id = c.document_id
            WHERE {' AND '.join(where)}
            ORDER BY rank ASC, c.confidence DESC, c.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_document_chunk(row) for row in rows]

    def _recall_documents_like(
        self,
        query: str,
        *,
        source_id: str | None,
        min_confidence: float,
        limit: int,
        include_inactive: bool,
    ) -> List[dict]:
        terms = [t.casefold() for t in _WORD_RE.findall(query) if t.strip("'\"")][:8]
        if not terms:
            terms = [query.casefold()]
        where = ["LOWER(c.content || ' ' || c.path || ' ' || c.section) LIKE ?" for _ in terms]
        where.append("c.confidence >= ?")
        params: list[Any] = [f"%{term}%" for term in terms]
        params.append(min_confidence)
        if source_id:
            where.append("c.source_id = ?")
            params.append(source_id)
        if not include_inactive:
            where.append("c.is_active = 1")
            where.append("d.is_active = 1")
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT c.*, d.title AS document_title, d.kind AS document_kind,
                   d.repo AS document_repo, d.repo_commit AS document_repo_commit,
                   d.content_hash AS document_content_hash, d.metadata AS document_metadata,
                   d.is_active AS document_is_active, 0.0 AS rank
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE {' AND '.join(where)}
            ORDER BY c.confidence DESC, c.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_document_chunk(row) for row in rows]

    # -- maintenance -----------------------------------------------------

    def stats(self) -> dict:
        with self._lock:
            source_rows = self._conn.execute(
                """
                SELECT s.source_id, COUNT(f.fact_id) AS facts
                FROM sources s
                LEFT JOIN facts f ON f.source_id = s.source_id
                GROUP BY s.source_id
                ORDER BY s.source_id
                """
            ).fetchall()
            doc_rows = self._conn.execute(
                """
                SELECT s.source_id,
                       COUNT(d.document_id) AS total,
                       SUM(CASE WHEN d.is_active = 1 THEN 1 ELSE 0 END) AS active
                FROM sources s
                LEFT JOIN documents d ON d.source_id = s.source_id
                GROUP BY s.source_id
                ORDER BY s.source_id
                """
            ).fetchall()
            chunk_rows = self._conn.execute(
                """
                SELECT s.source_id,
                       COUNT(c.chunk_id) AS total,
                       SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active
                FROM sources s
                LEFT JOIN document_chunks c ON c.source_id = s.source_id
                GROUP BY s.source_id
                ORDER BY s.source_id
                """
            ).fetchall()
            source_counts = {row["source_id"]: int(row["facts"]) for row in source_rows}
            document_counts = {
                row["source_id"]: {"active": int(row["active"] or 0), "total": int(row["total"] or 0)}
                for row in doc_rows
            }
            chunk_counts = {
                row["source_id"]: {"active": int(row["active"] or 0), "total": int(row["total"] or 0)}
                for row in chunk_rows
            }
            return {
                "sources": source_counts,
                "fact_count": sum(source_counts.values()),
                "documents": document_counts,
                "document_chunks": chunk_counts,
                "document_count": sum(row["total"] for row in document_counts.values()),
                "active_document_count": sum(row["active"] for row in document_counts.values()),
                "document_chunk_count": sum(row["total"] for row in chunk_counts.values()),
                "active_document_chunk_count": sum(row["active"] for row in chunk_counts.values()),
            }

    @staticmethod
    def _min_confidence_for_mode(mode: str) -> float:
        return 0.75 if mode == "conservative" else 0.0

    @staticmethod
    def _build_fts_query(query: str) -> str:
        # Quote every token so punctuation in user text cannot become FTS syntax.
        terms = [t.strip("'\"") for t in _WORD_RE.findall(query) if t.strip("'\"")]
        if not terms:
            return ""
        # AND keeps recall precise for the MVP.  Broader expansion can come later.
        return " AND ".join(f'"{term}"' for term in terms[:12])

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> dict:
        content, _content_redactions = redact_secret_text(str(row["content"] or ""))
        provenance_obj, _provenance_redactions = redact_secrets(deserialize_jsonish(row["provenance"] or ""))
        provenance = serialize_provenance(provenance_obj)
        return {
            "fact_id": int(row["fact_id"]),
            "source_id": row["source_id"],
            "content": content,
            "kind": row["kind"],
            "confidence": float(row["confidence"]),
            "notability": row["notability"],
            "provenance": provenance,
            "visibility": row["visibility"],
            "valid_from": row["valid_from"] or "",
            "valid_until": row["valid_until"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_document_chunk(row: sqlite3.Row) -> dict:
        provenance, _provenance_redactions = redact_secrets(deserialize_jsonish(row["provenance"] or ""))
        path, _path_redactions = redact_secret_text(str(row["path"] or ""))
        section, _section_redactions = redact_secret_text(str(row["section"] or ""))
        repo, _repo_redactions = redact_secret_text(str(row["repo"] or ""))
        repo_commit, _repo_commit_redactions = redact_secret_text(str(row["repo_commit"] or ""))
        document_title, _document_title_redactions = redact_secret_text(str(row["document_title"] or ""))
        document_repo, _document_repo_redactions = redact_secret_text(str(row["document_repo"] or ""))
        document_repo_commit, _document_repo_commit_redactions = redact_secret_text(
            str(row["document_repo_commit"] or "")
        )
        document_metadata, _document_metadata_redactions = redact_secrets(
            deserialize_jsonish(row["document_metadata"] or "")
        )
        content, _content_redactions = redact_secret_text(str(row["content"] or ""))
        return {
            "chunk_id": int(row["chunk_id"]),
            "document_id": int(row["document_id"]),
            "source_id": row["source_id"],
            "path": path,
            "section": section,
            "line_start": int(row["line_start"] or 0),
            "line_end": int(row["line_end"] or 0),
            "chunk_index": int(row["chunk_index"] or 0),
            "content": content,
            "kind": row["kind"],
            "confidence": float(row["confidence"]),
            "notability": row["notability"],
            "provenance": provenance,
            "visibility": row["visibility"],
            "repo": repo,
            "repo_commit": repo_commit,
            "content_hash": row["content_hash"],
            "is_active": bool(row["is_active"]),
            "supersedes_chunk_id": int(row["supersedes_chunk_id"]) if row["supersedes_chunk_id"] else None,
            "superseded_at": row["superseded_at"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "document": {
                "document_id": int(row["document_id"]),
                "source_id": row["source_id"],
                "path": path,
                "title": document_title,
                "kind": row["document_kind"] or "",
                "repo": document_repo,
                "repo_commit": document_repo_commit,
                "content_hash": row["document_content_hash"] or "",
                "metadata": document_metadata,
                "is_active": bool(row["document_is_active"]),
            },
        }
