"""Private local document RAG tools for Hermes.

This MVP intentionally avoids heavyweight mandatory dependencies. It stores
chunks and deterministic hashed embeddings in a profile-scoped SQLite database
under ``$HERMES_HOME/personal-rag/personal_rag.db``. PDF text extraction uses
``pypdf`` when available; plain text/markdown files are supported directly.

The retrieval layer returns sourced passages only. The active Hermes model then
uses those passages to produce the final answer, so provider/model routing stays
unchanged (for example openai-codex + gpt-5.5).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from hermes_constants import get_hermes_home
from tools.registry import registry

DB_NAME = "personal_rag.db"
DEFAULT_DIMENSIONS = 384
DEFAULT_CHUNK_CHARS = 1800
DEFAULT_OVERLAP_CHARS = 250
MAX_CHUNK_CHARS = 6000
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".text", ".log"}
SUPPORTED_SUFFIXES = SUPPORTED_TEXT_SUFFIXES | {".pdf"}

_TOKEN_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ']+", re.UNICODE)


PERSONAL_RAG_INGEST_SCHEMA = {
    "name": "personal_rag_ingest",
    "description": (
        "Index a local PDF or text/markdown file into the user's private local "
        "document RAG store. Returns document/chunk counts and the storage path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to a local PDF/text/markdown file.",
            },
            "document_type": {
                "type": "string",
                "description": (
                    "Optional label used for filtering, e.g. vefa, esalia, paie, "
                    "banque, impots, mail, etsy, generic."
                ),
                "default": "generic",
            },
            "title": {
                "type": "string",
                "description": "Optional human-readable title. Defaults to the filename.",
            },
            "chunk_chars": {
                "type": "integer",
                "description": "Approximate chunk size in characters. Default 1800.",
                "default": DEFAULT_CHUNK_CHARS,
            },
            "overlap_chars": {
                "type": "integer",
                "description": "Character overlap between chunks. Default 250.",
                "default": DEFAULT_OVERLAP_CHARS,
            },
        },
        "required": ["file_path"],
    },
}


PERSONAL_RAG_SEARCH_SCHEMA = {
    "name": "personal_rag_search",
    "description": (
        "Search the user's private local document RAG index and return sourced "
        "passages with file/page metadata. Use this before answering questions "
        "about previously indexed personal documents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query in French or English.",
            },
            "document_type": {
                "type": "string",
                "description": "Optional filter such as vefa, esalia, paie, banque, impots, mail, etsy, all.",
                "default": "all",
            },
            "k": {
                "type": "integer",
                "description": "Maximum number of passages to return. Default 6, max 20.",
                "default": 6,
            },
        },
        "required": ["query"],
    },
}


PERSONAL_RAG_LIST_SCHEMA = {
    "name": "personal_rag_list",
    "description": "List documents currently indexed in the user's private local RAG store.",
    "parameters": {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "description": "Optional filter by document type; use all for no filter.",
                "default": "all",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of documents to return. Default 50, max 200.",
                "default": 50,
            },
        },
        "required": [],
    },
}


def _rag_dir() -> Path:
    path = get_hermes_home() / "personal-rag"
    path.mkdir(parents=True, exist_ok=True)
    (path / "documents" / "raw").mkdir(parents=True, exist_ok=True)
    return path


def _db_path() -> Path:
    return _rag_dir() / DB_NAME


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL,
            suffix TEXT NOT NULL,
            created_at TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL,
            token_count INTEGER NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        """
    )
    conn.commit()


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _resolve_file(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported file type {path.suffix!r}. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    return path


def _extract_text_pages(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return [{"page": 1, "text": path.read_text(encoding="utf-8", errors="replace")}]

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:  # pragma: no cover - depends on environment
            raise RuntimeError("PDF ingestion requires the optional 'pypdf' package") from exc

        reader = PdfReader(str(path))
        pages: list[dict] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append({"page": index, "text": text})
        return pages

    raise ValueError(f"Unsupported file type: {suffix}")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _chunk_pages(
    pages: Sequence[dict],
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[dict]:
    chunk_chars = max(300, min(int(chunk_chars or DEFAULT_CHUNK_CHARS), MAX_CHUNK_CHARS))
    overlap_chars = max(0, min(int(overlap_chars or DEFAULT_OVERLAP_CHARS), chunk_chars // 2))
    chunks: list[dict] = []

    for page in pages:
        page_no = int(page["page"])
        text = _normalize_space(page.get("text") or "")
        if not text:
            continue

        if len(text) <= chunk_chars:
            chunks.append({"text": text, "page_start": page_no, "page_end": page_no})
            continue

        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_chars)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"text": chunk, "page_start": page_no, "page_end": page_no})
            if end >= len(text):
                break
            start = max(end - overlap_chars, start + 1)

    return chunks


def _tokens(text: str) -> list[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _hashed_embedding(text: str, dimensions: int = DEFAULT_DIMENSIONS) -> list[float]:
    """Return a deterministic normalized hashing-vector embedding.

    This keeps the MVP dependency-light and fully local. It is lexical rather
    than deeply semantic, but works well enough for sourced retrieval and can be
    replaced later by sentence-transformers/Chroma/Qdrant without changing the
    public Hermes tool shape.
    """
    vector = [0.0] * dimensions
    for tok in _tokens(text):
        digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "big")
        idx = raw % dimensions
        sign = 1.0 if ((raw >> 8) & 1) else -1.0
        vector[idx] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _safe_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def personal_rag_ingest(
    file_path: str,
    document_type: str = "generic",
    title: str | None = None,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> str:
    try:
        path = _resolve_file(file_path)
        pages = _extract_text_pages(path)
        chunks = _chunk_pages(pages, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        if not chunks:
            return _json_response(
                {
                    "success": False,
                    "error": "No extractable text found. This may be a scanned PDF; OCR is not included in this MVP.",
                    "source_file": str(path),
                    "page_count": len(pages),
                }
            )

        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc_type = (document_type or "generic").strip().lower()
        doc_title = (title or path.name).strip()

        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO documents
                (id, source_file, title, document_type, suffix, created_at, page_count, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, str(path), doc_title, doc_type, path.suffix.lower(), now, len(pages), len(chunks)),
            )
            for index, chunk in enumerate(chunks):
                embedding = _hashed_embedding(chunk["text"])
                conn.execute(
                    """
                    INSERT INTO chunks
                    (id, document_id, chunk_index, page_start, page_end, text, embedding, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        doc_id,
                        index,
                        chunk.get("page_start"),
                        chunk.get("page_end"),
                        chunk["text"],
                        json.dumps(embedding),
                        len(_tokens(chunk["text"])),
                    ),
                )
            conn.commit()

        return _json_response(
            {
                "success": True,
                "document_id": doc_id,
                "source_file": str(path),
                "title": doc_title,
                "document_type": doc_type,
                "page_count": len(pages),
                "chunk_count": len(chunks),
                "db_path": str(_db_path()),
            }
        )
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc)})


def personal_rag_search(query: str, document_type: str = "all", k: int = 6) -> str:
    try:
        query = (query or "").strip()
        if not query:
            raise ValueError("query is required")
        limit = _safe_int(k, 6, 1, 20)
        doc_type = (document_type or "all").strip().lower()
        query_embedding = _hashed_embedding(query)

        sql = """
            SELECT
                chunks.id AS chunk_id,
                chunks.chunk_index,
                chunks.page_start,
                chunks.page_end,
                chunks.text,
                chunks.embedding,
                chunks.token_count,
                documents.id AS document_id,
                documents.source_file,
                documents.title,
                documents.document_type,
                documents.created_at
            FROM chunks
            JOIN documents ON chunks.document_id = documents.id
        """
        params: list[str] = []
        if doc_type and doc_type != "all":
            sql += " WHERE documents.document_type = ?"
            params.append(doc_type)

        scored: list[dict] = []
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        for row in rows:
            embedding = json.loads(row["embedding"])
            score = _cosine(query_embedding, embedding)
            if score <= 0:
                continue
            scored.append(
                {
                    "score": round(score, 6),
                    "text": row["text"],
                    "source_file": row["source_file"],
                    "title": row["title"],
                    "document_type": row["document_type"],
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                    "chunk_index": row["chunk_index"],
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "token_count": row["token_count"],
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        passages = scored[:limit]
        return _json_response(
            {
                "success": True,
                "query": query,
                "document_type": doc_type,
                "result_count": len(passages),
                "passages": passages,
                "note": (
                    "Use these passages as evidence only. If no passage directly supports the answer, "
                    "say that the indexed documents are insufficient."
                ),
            }
        )
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc)})


def personal_rag_list(document_type: str = "all", limit: int = 50) -> str:
    try:
        doc_type = (document_type or "all").strip().lower()
        limit_i = _safe_int(limit, 50, 1, 200)
        sql = """
            SELECT id, source_file, title, document_type, suffix, created_at, page_count, chunk_count
            FROM documents
        """
        params: list[str | int] = []
        if doc_type and doc_type != "all":
            sql += " WHERE document_type = ?"
            params.append(doc_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit_i)

        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        documents = [dict(row) for row in rows]
        return _json_response(
            {
                "success": True,
                "document_type": doc_type,
                "count": len(documents),
                "documents": documents,
                "db_path": str(_db_path()),
            }
        )
    except Exception as exc:
        return _json_response({"success": False, "error": str(exc)})


def check_personal_rag_requirements() -> bool:
    return True


registry.register(
    name="personal_rag_ingest",
    toolset="personal_rag",
    schema=PERSONAL_RAG_INGEST_SCHEMA,
    handler=lambda args, **kw: personal_rag_ingest(
        file_path=args.get("file_path", ""),
        document_type=args.get("document_type", "generic"),
        title=args.get("title"),
        chunk_chars=args.get("chunk_chars", DEFAULT_CHUNK_CHARS),
        overlap_chars=args.get("overlap_chars", DEFAULT_OVERLAP_CHARS),
    ),
    check_fn=check_personal_rag_requirements,
    emoji="📥",
)

registry.register(
    name="personal_rag_search",
    toolset="personal_rag",
    schema=PERSONAL_RAG_SEARCH_SCHEMA,
    handler=lambda args, **kw: personal_rag_search(
        query=args.get("query", ""),
        document_type=args.get("document_type", "all"),
        k=args.get("k", 6),
    ),
    check_fn=check_personal_rag_requirements,
    emoji="📚",
)

registry.register(
    name="personal_rag_list",
    toolset="personal_rag",
    schema=PERSONAL_RAG_LIST_SCHEMA,
    handler=lambda args, **kw: personal_rag_list(
        document_type=args.get("document_type", "all"),
        limit=args.get("limit", 50),
    ),
    check_fn=check_personal_rag_requirements,
    emoji="🗂️",
)
