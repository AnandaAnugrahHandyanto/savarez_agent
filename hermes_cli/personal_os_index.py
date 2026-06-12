"""Read-only Personal OS Obsidian vault indexing and retrieval.

The index is a disposable SQLite cache under Hermes home.  Obsidian markdown
files remain the source of truth and are never modified by this module.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - import itself is trivial, fallback is tested indirectly
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from hermes_constants import get_hermes_home
from hermes_state import apply_wal_with_fallback

SCHEMA_VERSION = 1
DEFAULT_STALE_DAYS = 120

DEFAULT_EXCLUDE_GLOBS = (
    ".obsidian/**",
    ".trash/**",
    ".git/**",
    "Archive/**",
    "Archives/**",
    "**/.obsidian/**",
    "**/.trash/**",
    "**/.git/**",
)

DEFAULT_SENSITIVE_EXCLUDE_GLOBS = (
    "*family*.md",
    "**/*family*.md",
    "family/**",
    "**/family/**",
    "*milene*.md",
    "**/*milene*.md",
    "**/milene/**",
    "*markus*.md",
    "**/*markus*.md",
    "**/markus/**",
    "*school*.md",
    "**/*school*.md",
    "**/school/**",
    "*health*.md",
    "**/*health*.md",
    "health/**",
    "**/health/**",
    "*medical*.md",
    "**/*medical*.md",
    "**/medical/**",
)

SCOPE_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "default": {
        "include": ("*.md", "**/*.md"),
        "exclude": (
            *DEFAULT_EXCLUDE_GLOBS,
            *DEFAULT_SENSITIVE_EXCLUDE_GLOBS,
            "Areas/Personal/Health/**",
            "Areas/Personal/*Family*/**",
            "Areas/Personal/*family*/**",
            "Areas/Personal/*Family*.md",
            "Areas/Personal/*family*.md",
            "Areas/Personal/*Milene*/**",
            "Areas/Personal/*Milene*.md",
            "Areas/Personal/*Markus*/**",
            "Areas/Personal/*Markus*.md",
            "**/Health/**",
        ),
    },
    "family": {
        "include": (
            "HOME.md",
            "TASKS.md",
            "Open Loops.md",
            "Areas/Personal/*Family*/**/*.md",
            "Areas/Personal/*family*/**/*.md",
            "Areas/Personal/*Milene*/**/*.md",
            "Areas/Personal/*Markus*/**/*.md",
            "Areas/Personal/*School*/**/*.md",
            "Areas/Personal/Family*.md",
            "Areas/Personal/Milene*.md",
            "Areas/Personal/Markus*.md",
        ),
        "exclude": (*DEFAULT_EXCLUDE_GLOBS, "Areas/Personal/Health/**", "**/Health/**"),
    },
    "health": {
        "include": ("Areas/Personal/Health/*.md", "Areas/Personal/Health/**/*.md", "**/Health/*.md", "**/Health/**/*.md"),
        "exclude": DEFAULT_EXCLUDE_GLOBS,
    },
    "shopping": {
        "include": ("*Shopping*.md", "*shopping*.md", "Areas/Personal/Shopping list.md", "**/*Shopping*.md", "**/*shopping*.md"),
        "exclude": (*DEFAULT_EXCLUDE_GLOBS, "Areas/Personal/Health/**"),
    },
    "projects": {
        "include": ("Projects/**/*.md", "Open Loops.md", "TASKS.md", "HOME.md"),
        "exclude": (*DEFAULT_EXCLUDE_GLOBS, *DEFAULT_SENSITIVE_EXCLUDE_GLOBS, "Areas/Personal/Health/**"),
    },
    "all": {
        "include": ("*.md", "**/*.md"),
        "exclude": DEFAULT_EXCLUDE_GLOBS,
    },
}

BOOST_FILENAMES = {
    "AGENTS.md": 60.0,
    "CLAUDE.md": 55.0,
    "HOME.md": 50.0,
    "TASKS.md": 45.0,
    "Open Loops.md": 45.0,
}


def default_db_path() -> Path:
    return get_hermes_home() / "personal_os" / "vault_index.db"


def default_vault_root() -> Path:
    env = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/personal OS"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_rel(path: Path | str) -> str:
    return str(path).replace(os.sep, "/")


def _matches_any(rel_path: str, patterns: Iterable[str]) -> bool:
    rel_path = rel_path.strip("/").lower()
    return any(fnmatch.fnmatch(rel_path, pattern.lower()) for pattern in patterns)


def scope_names() -> list[str]:
    return sorted(SCOPE_RULES)


def path_allowed_for_scope(rel_path: str, scope: str) -> bool:
    if scope not in SCOPE_RULES:
        raise ValueError(f"Unknown scope {scope!r}; choose one of: {', '.join(scope_names())}")
    rel_path = rel_path.strip("/")
    rules = SCOPE_RULES[scope]
    return _matches_any(rel_path, rules["include"]) and not _matches_any(rel_path, rules["exclude"])


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body_start = text.find("\n", end + 4)
    body = text[body_start + 1 :] if body_start != -1 else ""
    if yaml is None:
        return {}, body
    try:
        parsed = yaml.safe_load(raw) or {}
        return parsed if isinstance(parsed, dict) else {}, body
    except Exception:
        return {}, body


def _title_from_text(path: Path, body: str, frontmatter: dict[str, Any]) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or path.stem
    return path.stem


def _tags_from_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    raw = frontmatter.get("tags", [])
    if isinstance(raw, str):
        return [part.strip().lstrip("#") for part in re.split(r"[,\s]+", raw) if part.strip()]
    if isinstance(raw, list):
        return [str(item).strip().lstrip("#") for item in raw if str(item).strip()]
    return []


def _chunk_markdown(title: str, body: str, max_chars: int = 1800) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current_heading = title
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        text = "\n".join(current).strip()
        if text:
            # Split very large heading sections at paragraph boundaries.
            while len(text) > max_chars:
                cut = text.rfind("\n\n", 0, max_chars)
                if cut < max_chars // 2:
                    cut = max_chars
                chunks.append((current_heading, text[:cut].strip()))
                text = text[cut:].strip()
            if text:
                chunks.append((current_heading, text))
        current = []

    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(2).strip() or title
        current.append(line)
    flush()
    if not chunks and body.strip():
        chunks.append((title, body.strip()[:max_chars]))
    return chunks


def _sanitize_query(query: str) -> str:
    terms = re.findall(r"[\w\-]+", query, flags=re.UNICODE)
    return " OR ".join(f'"{term}"' for term in terms[:12]) or '""'


@dataclass
class IndexStats:
    indexed_files: int = 0
    unchanged_files: int = 0
    skipped_files: int = 0
    removed_files: int = 0
    chunks: int = 0
    fts_available: bool = True
    warnings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indexed_files": self.indexed_files,
            "unchanged_files": self.unchanged_files,
            "skipped_files": self.skipped_files,
            "removed_files": self.removed_files,
            "chunks": self.chunks,
            "fts_available": self.fts_available,
            "warnings": self.warnings,
        }


class PersonalOSIndex:
    def __init__(self, vault_root: Path | str | None = None, db_path: Path | str | None = None):
        self.vault_root = (Path(vault_root) if vault_root is not None else default_vault_root()).expanduser().resolve()
        self.db_path = (Path(db_path) if db_path is not None else default_db_path()).expanduser().resolve()
        if _is_inside(self.db_path, self.vault_root):
            raise ValueError("Personal OS index DB path must not be inside the vault")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._chmod_best_effort(self.db_path.parent, 0o700)
        self._fts_available: bool | None = None

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        apply_wal_with_fallback(conn, db_label="personal_os_vault_index.db")
        self._harden_db_permissions()
        self._init_schema(conn)
        self._harden_db_permissions()
        return conn

    def _harden_db_permissions(self) -> None:
        self._chmod_best_effort(self.db_path.parent, 0o700)
        for suffix in ("", "-wal", "-shm"):
            self._chmod_best_effort(Path(f"{self.db_path}{suffix}"), 0o600)

    @staticmethod
    def _chmod_best_effort(path: Path, mode: int) -> None:
        try:
            if path.exists():
                path.chmod(mode)
        except OSError:
            pass

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                rel_path TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                indexed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                heading TEXT NOT NULL,
                text TEXT NOT NULL,
                UNIQUE(file_id, chunk_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skipped_files (
                rel_path TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                skipped_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        if self._fts_available is None:
            self._fts_available = self._ensure_fts(conn)
        conn.commit()

    def _ensure_fts(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(rel_path, title, heading, text, tags)"
            )
            return True
        except sqlite3.OperationalError:
            return False

    @property
    def fts_available(self) -> bool:
        if self._fts_available is None:
            with self.connect() as conn:
                self._fts_available = self._ensure_fts(conn)
        return bool(self._fts_available)

    def rebuild(self) -> IndexStats:
        with self.connect() as conn:
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM skipped_files")
            if self._ensure_fts(conn):
                conn.execute("DELETE FROM chunks_fts")
            conn.commit()
        return self.index_changed()

    def index_changed(self) -> IndexStats:
        stats = IndexStats(fts_available=self.fts_available)
        if not self.vault_root.exists() or not self.vault_root.is_dir():
            stats.warnings.append({"path": str(self.vault_root), "reason": "vault_root_missing"})
            return stats

        seen: set[str] = set()
        with self.connect() as conn:
            for path in sorted(self.vault_root.rglob("*.md")):
                rel = _normalize_rel(path.relative_to(self.vault_root))
                seen.add(rel)
                reason = self._skip_reason(path, rel)
                if reason:
                    self._delete_indexed_file(conn, rel)
                    self._record_skip(conn, rel, reason, "")
                    stats.skipped_files += 1
                    stats.warnings.append({"path": rel, "reason": reason})
                    continue
                try:
                    stat = path.stat()
                    content = path.read_bytes()
                except OSError as exc:
                    self._delete_indexed_file(conn, rel)
                    self._record_skip(conn, rel, "read_error", str(exc))
                    stats.skipped_files += 1
                    stats.warnings.append({"path": rel, "reason": "read_error"})
                    continue
                digest = hashlib.sha256(content).hexdigest()
                existing = conn.execute(
                    "SELECT sha256, mtime, size FROM files WHERE rel_path = ?", (rel,)
                ).fetchone()
                if existing and existing["sha256"] == digest and existing["size"] == stat.st_size:
                    stats.unchanged_files += 1
                    continue
                try:
                    text = content.decode("utf-8")
                except UnicodeDecodeError:
                    text = content.decode("utf-8", errors="replace")
                frontmatter, body = _parse_frontmatter(text)
                title = _title_from_text(path, body, frontmatter)
                tags = _tags_from_frontmatter(frontmatter)
                file_id = self._upsert_file(conn, rel, title, stat.st_mtime, stat.st_size, digest, tags)
                conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
                if self._ensure_fts(conn):
                    conn.execute("DELETE FROM chunks_fts WHERE rel_path = ?", (rel,))
                chunks = _chunk_markdown(title, body)
                for idx, (heading, chunk_text) in enumerate(chunks):
                    conn.execute(
                        "INSERT INTO chunks(file_id, chunk_index, heading, text) VALUES (?, ?, ?, ?)",
                        (file_id, idx, heading, chunk_text),
                    )
                    if self._ensure_fts(conn):
                        conn.execute(
                            "INSERT INTO chunks_fts(rowid, rel_path, title, heading, text, tags) VALUES (last_insert_rowid(), ?, ?, ?, ?, ?)",
                            (rel, title, heading, chunk_text, " ".join(tags)),
                        )
                conn.execute("DELETE FROM skipped_files WHERE rel_path = ?", (rel,))
                stats.indexed_files += 1
                stats.chunks += len(chunks)

            rows = conn.execute("SELECT rel_path, id FROM files").fetchall()
            for row in rows:
                if row["rel_path"] not in seen:
                    conn.execute("DELETE FROM files WHERE id = ?", (row["id"],))
                    if self._ensure_fts(conn):
                        conn.execute("DELETE FROM chunks_fts WHERE rel_path = ?", (row["rel_path"],))
                    stats.removed_files += 1
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_indexed_at', ?)", (utc_now_iso(),))
            conn.commit()
        return stats

    def _skip_reason(self, path: Path, rel: str) -> str | None:
        if _matches_any(rel, DEFAULT_EXCLUDE_GLOBS):
            return "excluded_path"
        try:
            if path.is_symlink() and not _is_inside(path, self.vault_root):
                return "symlink_escape"
            if path.stat().st_size == 0:
                return "zero_byte_possibly_unsynced"
        except OSError:
            return "stat_error"
        return None

    def _record_skip(self, conn: sqlite3.Connection, rel: str, reason: str, detail: str) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO skipped_files(rel_path, reason, detail, skipped_at) VALUES (?, ?, ?, ?)",
            (rel, reason, detail, utc_now_iso()),
        )

    def _delete_indexed_file(self, conn: sqlite3.Connection, rel: str) -> None:
        conn.execute("DELETE FROM files WHERE rel_path = ?", (rel,))
        if self._ensure_fts(conn):
            conn.execute("DELETE FROM chunks_fts WHERE rel_path = ?", (rel,))

    def _upsert_file(
        self,
        conn: sqlite3.Connection,
        rel: str,
        title: str,
        mtime: float,
        size: int,
        digest: str,
        tags: list[str],
    ) -> int:
        conn.execute(
            """
            INSERT INTO files(rel_path, title, mtime, size, sha256, tags_json, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rel_path) DO UPDATE SET
              title = excluded.title,
              mtime = excluded.mtime,
              size = excluded.size,
              sha256 = excluded.sha256,
              tags_json = excluded.tags_json,
              indexed_at = excluded.indexed_at
            """,
            (rel, title, mtime, size, digest, json.dumps(tags), utc_now_iso()),
        )
        row = conn.execute("SELECT id FROM files WHERE rel_path = ?", (rel,)).fetchone()
        return int(row["id"])

    def search(self, query: str, *, scope: str = "default", limit: int = 10, stale_days: int = DEFAULT_STALE_DAYS) -> dict[str, Any]:
        if scope not in SCOPE_RULES:
            raise ValueError(f"Unknown scope {scope!r}; choose one of: {', '.join(scope_names())}")
        with self.connect() as conn:
            fts = self._ensure_fts(conn)
            allowed_paths = self._allowed_paths(conn, scope)
            rows = self._search_fts(conn, query, allowed_paths, limit) if fts else self._search_like(conn, query, allowed_paths, limit)
            matches = [self._row_to_match(row, query, stale_days) for row in rows]
            matches.sort(key=lambda item: item["score"], reverse=True)
            warnings = self._warnings_for_scope(conn, scope)
            last_indexed = self._meta(conn, "last_indexed_at")
        return {
            "query": query,
            "scope": scope,
            "vault_root": str(self.vault_root),
            "db_path": str(self.db_path),
            "fts_available": fts,
            "last_indexed_at": last_indexed,
            "matches": matches[:limit],
            "warnings": warnings,
        }

    def _allowed_paths(self, conn: sqlite3.Connection, scope: str) -> list[str]:
        rows = conn.execute("SELECT rel_path FROM files").fetchall()
        return [row["rel_path"] for row in rows if path_allowed_for_scope(row["rel_path"], scope)]

    def _scope_sql(self, allowed_paths: list[str]) -> tuple[str, list[str]]:
        if not allowed_paths:
            return "0", []
        placeholders = ", ".join("?" for _ in allowed_paths)
        return f"f.rel_path IN ({placeholders})", allowed_paths

    def _search_fts(self, conn: sqlite3.Connection, query: str, allowed_paths: list[str], limit: int) -> list[sqlite3.Row]:
        if not allowed_paths:
            return []
        fts_query = _sanitize_query(query)
        scope_clause, scope_params = self._scope_sql(allowed_paths)
        try:
            rows = conn.execute(
                f"""
                SELECT c.id AS chunk_id, f.rel_path, f.title, f.mtime, f.indexed_at,
                       f.tags_json, c.heading, c.text, bm25(chunks_fts) AS rank
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                JOIN files f ON f.id = c.file_id
                WHERE chunks_fts MATCH ? AND {scope_clause}
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, *scope_params, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return self._search_like(conn, query, allowed_paths, limit)
        return list(rows)

    def _search_like(self, conn: sqlite3.Connection, query: str, allowed_paths: list[str], limit: int) -> list[sqlite3.Row]:
        if not allowed_paths:
            return []
        terms = [term.lower() for term in re.findall(r"[\w\-]+", query, flags=re.UNICODE) if term.strip()]
        if not terms:
            return []
        clauses = " OR ".join(["lower(c.text || ' ' || c.heading || ' ' || f.title || ' ' || f.rel_path) LIKE ?" for _ in terms])
        params = [f"%{term}%" for term in terms]
        scope_clause, scope_params = self._scope_sql(allowed_paths)
        rows = conn.execute(
            f"""
            SELECT c.id AS chunk_id, f.rel_path, f.title, f.mtime, f.indexed_at,
                   f.tags_json, c.heading, c.text, 0.0 AS rank
            FROM chunks c
            JOIN files f ON f.id = c.file_id
            WHERE ({clauses}) AND {scope_clause}
            LIMIT ?
            """,
            (*params, *scope_params, limit),
        ).fetchall()
        return list(rows)

    def _row_to_match(self, row: sqlite3.Row, query: str, stale_days: int) -> dict[str, Any]:
        rel = row["rel_path"]
        text = row["text"] or ""
        score = self._score(row, query)
        modified = datetime.fromtimestamp(float(row["mtime"]), timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - modified).days)
        return {
            "path": rel,
            "title": row["title"],
            "heading": row["heading"],
            "snippet": self._snippet(text, query),
            "score": round(score, 3),
            "modified": modified.isoformat(timespec="seconds"),
            "indexed_at": row["indexed_at"],
            "stale": age_days >= stale_days,
            "age_days": age_days,
            "tags": json.loads(row["tags_json"] or "[]"),
        }

    def _score(self, row: sqlite3.Row, query: str) -> float:
        # FTS bm25 is lower-is-better and often negative; convert into a simple
        # positive score with deterministic path/title boosts.
        raw_rank = float(row["rank"] or 0.0)
        score = 100.0 - raw_rank
        rel = row["rel_path"]
        name = Path(rel).name
        score += BOOST_FILENAMES.get(name, 0.0)
        q = query.lower()
        if q and q in str(row["title"]).lower():
            score += 25.0
        if q and q in str(row["heading"]).lower():
            score += 15.0
        return score

    def _snippet(self, text: str, query: str, width: int = 260) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= width:
            return compact
        terms = re.findall(r"[\w\-]+", query, flags=re.UNICODE)
        positions = [compact.lower().find(term.lower()) for term in terms if compact.lower().find(term.lower()) >= 0]
        start = max(0, min(positions) - width // 3) if positions else 0
        end = min(len(compact), start + width)
        prefix = "…" if start else ""
        suffix = "…" if end < len(compact) else ""
        return prefix + compact[start:end].strip() + suffix

    def _warnings_for_scope(self, conn: sqlite3.Connection, scope: str) -> list[dict[str, str]]:
        rows = conn.execute("SELECT rel_path, reason, detail, skipped_at FROM skipped_files ORDER BY rel_path LIMIT 50").fetchall()
        return [dict(row) for row in rows if path_allowed_for_scope(row["rel_path"], scope) or scope == "all"]

    def _meta(self, conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def doctor(self) -> dict[str, Any]:
        with self.connect() as conn:
            file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            skipped_count = conn.execute("SELECT COUNT(*) FROM skipped_files").fetchone()[0]
            last_indexed = self._meta(conn, "last_indexed_at")
        return {
            "vault_root": str(self.vault_root),
            "vault_exists": self.vault_root.exists(),
            "vault_readable": os.access(self.vault_root, os.R_OK) if self.vault_root.exists() else False,
            "db_path": str(self.db_path),
            "db_exists": self.db_path.exists(),
            "fts_available": self.fts_available,
            "indexed_files": file_count,
            "chunks": chunk_count,
            "skipped_files": skipped_count,
            "last_indexed_at": last_indexed,
            "scopes": scope_names(),
        }
