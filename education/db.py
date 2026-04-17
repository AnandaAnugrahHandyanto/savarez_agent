from __future__ import annotations

import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from education.paths import question_bank_db_path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    source_uri TEXT,
    source_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT,
    title TEXT,
    subject TEXT,
    grade TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_artifact_path TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    status TEXT NOT NULL,
    last_error TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_subject_grade ON documents(subject, grade);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    input_path TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    options_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_document ON ingest_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status_started ON ingest_jobs(status, started_at);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES ingest_jobs(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    mime_type TEXT,
    created_at REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_artifacts_document_kind ON artifacts(document_id, kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);

CREATE TABLE IF NOT EXISTS source_blocks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    block_index INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    kind TEXT NOT NULL,
    heading_path_json TEXT NOT NULL DEFAULT '[]',
    content_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mineru_ref TEXT,
    asset_path TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_blocks_document_index ON source_blocks(document_id, block_index);
CREATE INDEX IF NOT EXISTS idx_source_blocks_document_page ON source_blocks(document_id, page_start, page_end);
CREATE INDEX IF NOT EXISTS idx_source_blocks_kind ON source_blocks(kind);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    question_number TEXT,
    question_type TEXT,
    stem_markdown TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    answer_markdown TEXT,
    explanation_markdown TEXT,
    difficulty TEXT,
    subject TEXT,
    grade TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    formula_count INTEGER NOT NULL DEFAULT 0,
    citation_status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_questions_document ON questions(document_id);
CREATE INDEX IF NOT EXISTS idx_questions_subject_grade ON questions(subject, grade);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(question_type);
CREATE INDEX IF NOT EXISTS idx_questions_citation_status ON questions(citation_status);

CREATE TABLE IF NOT EXISTS question_citations (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_block_id TEXT REFERENCES source_blocks(id) ON DELETE SET NULL,
    page_start INTEGER,
    page_end INTEGER,
    quote_markdown TEXT,
    span_start INTEGER,
    span_end INTEGER,
    citation_kind TEXT NOT NULL,
    integrity_status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_question_citations_question ON question_citations(question_id);
CREATE INDEX IF NOT EXISTS idx_question_citations_document ON question_citations(document_id);
CREATE INDEX IF NOT EXISTS idx_question_citations_block ON question_citations(source_block_id);
CREATE INDEX IF NOT EXISTS idx_question_citations_integrity ON question_citations(integrity_status);
"""


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class EducationDB:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else question_bank_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)
            row = self.conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO schema_version(version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            elif int(row[0]) != SCHEMA_VERSION:
                self.conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (SCHEMA_VERSION,),
                )

    def _execute_write(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        attempts = 5
        for attempt in range(attempts):
            try:
                with self.conn:
                    return self.conn.execute(sql, tuple(params))
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == attempts - 1:
                    raise
                time.sleep(0.05 * (2 ** attempt) + random.random() * 0.01)
        raise RuntimeError("unreachable write retry state")

    def create_document(self, **fields: Any) -> None:
        now = fields.pop("now", time.time())
        values = {
            "id": fields["id"],
            "sha256": fields["sha256"],
            "source_uri": fields.get("source_uri"),
            "source_type": fields.get("source_type", "local_file"),
            "original_filename": fields["original_filename"],
            "mime_type": fields.get("mime_type"),
            "title": fields.get("title"),
            "subject": fields.get("subject"),
            "grade": fields.get("grade"),
            "tags_json": _json_dumps(fields.get("tags", [])),
            "raw_artifact_path": fields["raw_artifact_path"],
            "created_at": fields.get("created_at", now),
            "updated_at": fields.get("updated_at", now),
            "status": fields.get("status", "pending"),
            "last_error": fields.get("last_error"),
            "metadata_json": _json_dumps(fields.get("metadata", {})),
        }
        self._execute_write(
            """
            INSERT INTO documents(
                id, sha256, source_uri, source_type, original_filename, mime_type,
                title, subject, grade, tags_json, raw_artifact_path, created_at,
                updated_at, status, last_error, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["id"],
                values["sha256"],
                values["source_uri"],
                values["source_type"],
                values["original_filename"],
                values["mime_type"],
                values["title"],
                values["subject"],
                values["grade"],
                values["tags_json"],
                values["raw_artifact_path"],
                values["created_at"],
                values["updated_at"],
                values["status"],
                values["last_error"],
                values["metadata_json"],
            ),
        )

    def get_document(self, document_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()

    def create_ingest_job(self, **fields: Any) -> None:
        self._execute_write(
            """
            INSERT INTO ingest_jobs(
                id, document_id, input_path, started_at, finished_at, status,
                stage, warnings_json, error, options_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields["id"], fields.get("document_id"), fields["input_path"],
                fields.get("started_at", time.time()), fields.get("finished_at"),
                fields.get("status", "pending"), fields.get("stage", "intake"),
                _json_dumps(fields.get("warnings", [])), fields.get("error"),
                _json_dumps(fields.get("options", {})),
            ),
        )

    def update_ingest_job(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "finished_at", "status", "stage", "warnings_json", "error", "options_json"
        }
        updates = []
        params = []
        for key, value in fields.items():
            column = key
            if key == "warnings":
                column = "warnings_json"
                value = _json_dumps(value)
            if key == "options":
                column = "options_json"
                value = _json_dumps(value)
            if column not in allowed:
                continue
            updates.append(f"{column} = ?")
            params.append(value)
        if not updates:
            return
        params.append(job_id)
        self._execute_write(
            f"UPDATE ingest_jobs SET {', '.join(updates)} WHERE id = ?",
            params,
        )

    def add_artifact(self, **fields: Any) -> None:
        self._execute_write(
            """
            INSERT INTO artifacts(
                id, document_id, job_id, kind, path, sha256, mime_type, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields["id"], fields["document_id"], fields.get("job_id"),
                fields["kind"], fields["path"], fields.get("sha256"),
                fields.get("mime_type"), fields.get("created_at", time.time()),
                _json_dumps(fields.get("metadata", {})),
            ),
        )

    def add_source_blocks(self, blocks: Iterable[dict[str, Any]]) -> None:
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO source_blocks(
                    id, document_id, block_index, page_start, page_end, kind,
                    heading_path_json, content_markdown, content_hash, mineru_ref,
                    asset_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        block["id"], block["document_id"], block["block_index"],
                        block.get("page_start"), block.get("page_end"), block["kind"],
                        _json_dumps(block.get("heading_path", [])),
                        block["content_markdown"], block["content_hash"],
                        block.get("mineru_ref"), block.get("asset_path"),
                        block.get("created_at", time.time()),
                    )
                    for block in blocks
                ],
            )

    def add_questions(self, questions: Iterable[dict[str, Any]]) -> None:
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO questions(
                    id, document_id, question_number, question_type, stem_markdown,
                    options_json, answer_markdown, explanation_markdown, difficulty,
                    subject, grade, tags_json, formula_count, citation_status,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        question["id"], question["document_id"],
                        question.get("question_number"), question.get("question_type"),
                        question["stem_markdown"], _json_dumps(question.get("options", [])),
                        question.get("answer_markdown"), question.get("explanation_markdown"),
                        question.get("difficulty"), question.get("subject"),
                        question.get("grade"), _json_dumps(question.get("tags", [])),
                        question.get("formula_count", 0), question.get("citation_status", "missing"),
                        question.get("created_at", time.time()), question.get("updated_at", time.time()),
                        _json_dumps(question.get("metadata", {})),
                    )
                    for question in questions
                ],
            )

    def add_question_citations(self, citations: Iterable[dict[str, Any]]) -> None:
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO question_citations(
                    id, question_id, document_id, source_block_id, page_start, page_end,
                    quote_markdown, span_start, span_end, citation_kind, integrity_status,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        citation["id"], citation["question_id"], citation["document_id"],
                        citation.get("source_block_id"), citation.get("page_start"),
                        citation.get("page_end"), citation.get("quote_markdown"),
                        citation.get("span_start"), citation.get("span_end"),
                        citation.get("citation_kind", "stem"),
                        citation.get("integrity_status", "valid"),
                        _json_dumps(citation.get("metadata", {})),
                    )
                    for citation in citations
                ],
            )

    def search_questions(self, query: str, limit: int = 20) -> list[sqlite3.Row]:
        pattern = f"%{query}%"
        return list(
            self.conn.execute(
                """
                SELECT * FROM questions
                WHERE stem_markdown LIKE ?
                   OR answer_markdown LIKE ?
                   OR explanation_markdown LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            )
        )
