#!/usr/bin/env python3
"""SQLite-backed persistent memory store with markdown export compatibility."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

ENTRY_DELIMITER = "\n§\n"
DEFAULT_MEMORY_DIR = get_hermes_home() / "memories"
DEFAULT_DB_PATH = get_hermes_home() / "memory.db"
_BOOT_DEFAULT_MEMORY_DIR = DEFAULT_MEMORY_DIR
_BOOT_DEFAULT_DB_PATH = DEFAULT_DB_PATH


def get_default_memory_dir() -> Path:
    if DEFAULT_MEMORY_DIR != _BOOT_DEFAULT_MEMORY_DIR:
        return Path(DEFAULT_MEMORY_DIR)
    return get_hermes_home() / "memories"


def get_default_db_path() -> Path:
    if DEFAULT_DB_PATH != _BOOT_DEFAULT_DB_PATH:
        return Path(DEFAULT_DB_PATH)
    return get_hermes_home() / "memory.db"


class PersistentMemoryStore:
    def __init__(
        self,
        db_path: Path | None = None,
        memory_dir: Path | None = None,
        memory_char_limit: int = 2200,
        user_char_limit: int = 1375,
    ):
        self.db_path = Path(db_path or get_default_db_path())
        self.memory_dir = Path(memory_dir or get_default_memory_dir())
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'global',
                    scope_value TEXT,
                    source TEXT NOT NULL DEFAULT 'manual',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_used_at REAL,
                    use_count INTEGER NOT NULL DEFAULT 0,
                    supersedes_id TEXT,
                    fingerprint TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_target_status ON memory_entries(target, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_kind_status ON memory_entries(kind, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_scope_status ON memory_entries(scope, scope_value, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_updated ON memory_entries(updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_fingerprint ON memory_entries(fingerprint)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    detail TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_lanes (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'global',
                    scope_value TEXT,
                    lane_key TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_event_id TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_lanes_target_scope ON memory_lanes(target, scope, scope_value)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_lattice_events (
                    id TEXT PRIMARY KEY,
                    lane_id TEXT NOT NULL,
                    entry_id TEXT,
                    block_type TEXT NOT NULL,
                    prev_event_id TEXT,
                    supersedes_event_id TEXT,
                    content TEXT,
                    content_fingerprint TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_lattice_lane_created ON memory_lattice_events(lane_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_lattice_entry_created ON memory_lattice_events(entry_id, created_at)"
            )
            conn.commit()

    def _normalize_content(self, content: str) -> str:
        return " ".join(content.strip().split())

    def _fingerprint(self, target: str, content: str) -> str:
        normalized = f"{target}:{self._normalize_content(content).lower()}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _char_limit(self, target: str) -> int:
        return self.user_char_limit if target == "user" else self.memory_char_limit

    def _write_event(self, conn: sqlite3.Connection, entry_id: Optional[str], action: str, target: str, detail: str = ""):
        conn.execute(
            "INSERT INTO memory_events(entry_id, action, target, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (entry_id, action, target, detail, time.time()),
        )

    @staticmethod
    def _lane_key(target: str, scope: str, scope_value: str | None) -> str:
        return f"{target}:{scope}:{scope_value or '*'}"

    def _ensure_lane(
        self,
        conn: sqlite3.Connection,
        *,
        target: str,
        scope: str,
        scope_value: str | None,
    ) -> Dict[str, Any]:
        lane_key = self._lane_key(target, scope, scope_value)
        row = conn.execute("SELECT * FROM memory_lanes WHERE lane_key = ?", (lane_key,)).fetchone()
        if row:
            return self._row_to_dict(row)
        now = time.time()
        lane_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO memory_lanes(id, target, scope, scope_value, lane_key, description, created_at, updated_at, last_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (lane_id, target, scope, scope_value, lane_key, f"{target} lane for {scope}={scope_value or '*'}", now, now),
        )
        row = conn.execute("SELECT * FROM memory_lanes WHERE id = ?", (lane_id,)).fetchone()
        return self._row_to_dict(row)

    def _latest_event_id_for_entry(self, conn: sqlite3.Connection, entry_id: str | None) -> str | None:
        if not entry_id:
            return None
        row = conn.execute(
            "SELECT id FROM memory_lattice_events WHERE entry_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (entry_id,),
        ).fetchone()
        return row["id"] if row else None

    def _append_lattice_event(
        self,
        conn: sqlite3.Connection,
        *,
        target: str,
        scope: str,
        scope_value: str | None,
        block_type: str,
        entry_id: str | None,
        content: str,
        metadata: Dict[str, Any],
        supersedes_entry_id: str | None = None,
    ) -> Dict[str, Any]:
        lane = self._ensure_lane(conn, target=target, scope=scope, scope_value=scope_value)
        event_id = str(uuid.uuid4())
        created_at = time.time()
        prev_event_id = lane.get("last_event_id")
        supersedes_event_id = self._latest_event_id_for_entry(conn, supersedes_entry_id)
        conn.execute(
            """
            INSERT INTO memory_lattice_events(
                id, lane_id, entry_id, block_type, prev_event_id, supersedes_event_id,
                content, content_fingerprint, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                lane["id"],
                entry_id,
                block_type,
                prev_event_id,
                supersedes_event_id,
                content,
                self._fingerprint(target, content) if content else None,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )
        conn.execute(
            "UPDATE memory_lanes SET last_event_id = ?, updated_at = ? WHERE id = ?",
            (event_id, created_at, lane["id"]),
        )
        row = conn.execute("SELECT * FROM memory_lattice_events WHERE id = ?", (event_id,)).fetchone()
        return self._row_to_dict(row)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    def list_entries(self, target: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM memory_entries WHERE target = ?"
        params: list[Any] = [target]
        if not include_inactive:
            query += " AND status = 'active'"
        query += " ORDER BY updated_at DESC, created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_lattice_events(
        self,
        *,
        target: str | None = None,
        lane_key: str | None = None,
        limit: int | None = None,
    ) -> List[Dict[str, Any]]:
        query = (
            "SELECT e.*, l.lane_key, l.target FROM memory_lattice_events e "
            "JOIN memory_lanes l ON l.id = e.lane_id"
        )
        clauses: list[str] = []
        params: list[Any] = []
        if target is not None:
            clauses.append("l.target = ?")
            params.append(target)
        if lane_key is not None:
            clauses.append("l.lane_key = ?")
            params.append(lane_key)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY e.created_at ASC, e.id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _active_total_chars(self, conn: sqlite3.Connection, target: str, extra_content: str | None = None, replacing_id: str | None = None) -> int:
        rows = conn.execute(
            "SELECT id, content FROM memory_entries WHERE target = ? AND status = 'active' ORDER BY created_at ASC",
            (target,),
        ).fetchall()
        contents = []
        for row in rows:
            if replacing_id and row["id"] == replacing_id:
                continue
            contents.append(row["content"])
        if extra_content is not None:
            contents.append(extra_content)
        if not contents:
            return 0
        return len(ENTRY_DELIMITER.join(contents))

    def _export_markdown_locked(self, conn: sqlite3.Connection, target: str):
        rows = conn.execute(
            "SELECT content FROM memory_entries WHERE target = ? AND status = 'active' ORDER BY importance DESC, updated_at DESC",
            (target,),
        ).fetchall()
        content = ENTRY_DELIMITER.join(row["content"] for row in rows)
        path = self.memory_dir / ("USER.md" if target == "user" else "MEMORY.md")
        path.write_text(content, encoding="utf-8")

    def add_entry(
        self,
        target: str,
        content: str,
        *,
        kind: str = "lesson",
        scope: str = "global",
        scope_value: str | None = None,
        source: str = "manual",
        confidence: float = 1.0,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}
        fingerprint = self._fingerprint(target, content)
        with self._connect() as conn:
            duplicate = conn.execute(
                "SELECT * FROM memory_entries WHERE target = ? AND fingerprint = ? AND status = 'active'",
                (target, fingerprint),
            ).fetchone()
            if duplicate:
                return {
                    "success": True,
                    "message": "Entry already exists (no duplicate added).",
                    "entry": self._row_to_dict(duplicate),
                    "entries": self.list_entries(target),
                }
            total = self._active_total_chars(conn, target, extra_content=content)
            limit = self._char_limit(target)
            if total > limit:
                return {
                    "success": False,
                    "error": f"Memory at {self._active_total_chars(conn, target):,}/{limit:,} chars. Adding this entry ({len(content)} chars) would exceed the limit. Replace or remove existing entries first.",
                }
            now = time.time()
            entry_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO memory_entries(
                    id, target, kind, content, status, scope, scope_value, source,
                    confidence, importance, created_at, updated_at, last_used_at,
                    use_count, supersedes_id, fingerprint
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, ?)
                """,
                (
                    entry_id, target, kind, content, scope, scope_value, source,
                    confidence, importance, now, now, fingerprint,
                ),
            )
            self._write_event(conn, entry_id, "add", target, content)
            self._append_lattice_event(
                conn,
                target=target,
                scope=scope,
                scope_value=scope_value,
                block_type="add",
                entry_id=entry_id,
                content=content,
                metadata={
                    "target": target,
                    "kind": kind,
                    "scope": scope,
                    "scope_value": scope_value,
                    "source": source,
                    "confidence": confidence,
                    "importance": importance,
                    "status_after": "active",
                },
            )
            self._export_markdown_locked(conn, target)
            row = conn.execute("SELECT * FROM memory_entries WHERE id = ?", (entry_id,)).fetchone()
            conn.commit()
        return {
            "success": True,
            "message": "Entry added.",
            "entry": self._row_to_dict(row),
            "entries": self.list_entries(target),
        }

    def _find_active_matches(self, conn: sqlite3.Connection, target: str, substring: str) -> List[sqlite3.Row]:
        return conn.execute(
            "SELECT * FROM memory_entries WHERE target = ? AND status = 'active' AND content LIKE ? ORDER BY created_at ASC",
            (target, f"%{substring}%"),
        ).fetchall()

    def replace_entry(
        self,
        target: str,
        old_text: str,
        new_content: str,
        *,
        kind: str = "lesson",
        scope: str = "global",
        scope_value: str | None = None,
        source: str = "manual",
        confidence: float = 1.0,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}
        with self._connect() as conn:
            matches = self._find_active_matches(conn, target, old_text)
            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}
            unique_contents = {row["content"] for row in matches}
            if len(unique_contents) > 1:
                previews = [row["content"][:80] + ("..." if len(row["content"]) > 80 else "") for row in matches]
                return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}
            old_row = matches[0]
            limit = self._char_limit(target)
            total = self._active_total_chars(conn, target, extra_content=new_content, replacing_id=old_row["id"])
            if total > limit:
                return {"success": False, "error": f"Replacement would put memory at {total:,}/{limit:,} chars. Shorten the new content or remove other entries first."}
            now = time.time()
            conn.execute("UPDATE memory_entries SET status = 'superseded', updated_at = ? WHERE id = ?", (now, old_row["id"]))
            new_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO memory_entries(
                    id, target, kind, content, status, scope, scope_value, source,
                    confidence, importance, created_at, updated_at, last_used_at,
                    use_count, supersedes_id, fingerprint
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, NULL, 0, ?, ?)
                """,
                (
                    new_id, target, kind, new_content, scope, scope_value, source,
                    confidence, importance, now, now, old_row["id"], self._fingerprint(target, new_content),
                ),
            )
            self._write_event(conn, old_row["id"], "supersede", target, new_content)
            self._append_lattice_event(
                conn,
                target=target,
                scope=scope,
                scope_value=scope_value,
                block_type="replace",
                entry_id=new_id,
                supersedes_entry_id=old_row["id"],
                content=new_content,
                metadata={
                    "target": target,
                    "kind": kind,
                    "scope": scope,
                    "scope_value": scope_value,
                    "source": source,
                    "confidence": confidence,
                    "importance": importance,
                    "status_after": "active",
                },
            )
            self._export_markdown_locked(conn, target)
            row = conn.execute("SELECT * FROM memory_entries WHERE id = ?", (new_id,)).fetchone()
            conn.commit()
        return {"success": True, "message": "Entry replaced.", "entry": self._row_to_dict(row), "entries": self.list_entries(target)}

    def forget_entry(self, target: str, old_text: str) -> Dict[str, Any]:
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        with self._connect() as conn:
            matches = self._find_active_matches(conn, target, old_text)
            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}
            unique_contents = {row["content"] for row in matches}
            if len(unique_contents) > 1:
                previews = [row["content"][:80] + ("..." if len(row["content"]) > 80 else "") for row in matches]
                return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}
            row = matches[0]
            now = time.time()
            conn.execute("UPDATE memory_entries SET status = 'forgotten', updated_at = ? WHERE id = ?", (now, row["id"]))
            self._write_event(conn, row["id"], "forget", target, row["content"])
            self._append_lattice_event(
                conn,
                target=target,
                scope=row["scope"],
                scope_value=row["scope_value"],
                block_type="forget",
                entry_id=row["id"],
                supersedes_entry_id=row["id"],
                content=row["content"],
                metadata={
                    "target": target,
                    "kind": row["kind"],
                    "scope": row["scope"],
                    "scope_value": row["scope_value"],
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "importance": row["importance"],
                    "status_after": "forgotten",
                },
            )
            self._export_markdown_locked(conn, target)
            conn.commit()
        return {
            "success": True,
            "message": "Entry removed.",
            "entries": self.list_entries(target),
            "entry": self._row_to_dict(row),
        }

    def retrieve_for_prompt(self, target: str) -> List[Dict[str, Any]]:
        target_bias = 0.2 if target == "user" else 0.0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memory_entries WHERE target = ? AND status = 'active'",
                (target,),
            ).fetchall()
        items = []
        now = time.time()
        for row in rows:
            age_days = max(0.0, (now - row["updated_at"]) / 86400.0)
            recency = max(0.0, 0.3 - min(age_days / 365.0, 0.3))
            kind_bonus = 0.0
            if row["kind"] in {"preference", "instruction", "constraint", "identity"}:
                kind_bonus = 0.25
            score = float(row["importance"] or 0) + target_bias + kind_bonus + recency + 0.05 * int(row["use_count"] or 0)
            item = self._row_to_dict(row)
            item["_score"] = score
            items.append(item)
        items.sort(key=lambda x: (x["_score"], x["updated_at"]), reverse=True)
        return items

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    def search_entries(
        self,
        target: str,
        query: str,
        *,
        scope: str | None = None,
        scope_value: str | None = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM memory_entries WHERE target = ? AND status = 'active'"
        params: list[Any] = [target]
        if scope is not None:
            sql += " AND scope = ?"
            params.append(scope)
        if scope_value is not None:
            sql += " AND scope_value = ?"
            params.append(scope_value)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        query_clean = (query or "").strip().lower()
        query_tokens = set(self._tokenize(query_clean))
        now = time.time()
        scored: list[Dict[str, Any]] = []
        for row in rows:
            item = self._row_to_dict(row)
            content = str(item.get("content") or "")
            content_lower = content.lower()
            content_tokens = set(self._tokenize(content))
            overlap = len(query_tokens & content_tokens) if query_tokens else 0
            exact = 1 if query_clean and query_clean in content_lower else 0
            if query_tokens and overlap <= 0 and exact == 0:
                continue
            age_days = max(0.0, (now - float(item.get("updated_at") or now)) / 86400.0)
            recency = max(0.0, 0.3 - min(age_days / 365.0, 0.3))
            score = (
                overlap * 25
                + exact * 50
                + float(item.get("importance") or 0) * 10
                + float(item.get("confidence") or 0) * 5
                + recency
            )
            item["_search_score"] = score
            scored.append(item)
        scored.sort(key=lambda x: (x.get("_search_score", 0), x.get("updated_at", 0)), reverse=True)
        return scored[:limit]

    def render_prompt_block(self, target: str, char_limit: Optional[int] = None) -> Optional[str]:
        limit = char_limit or self._char_limit(target)
        entries = self.retrieve_for_prompt(target)
        if not entries:
            return None
        separator = "═" * 46
        header_name = "USER PROFILE (who the user is)" if target == "user" else "MEMORY (your personal notes)"
        selected: List[str] = []
        body = ""
        for entry in entries:
            candidate_entries = selected + [entry["content"]]
            candidate_body = ENTRY_DELIMITER.join(candidate_entries)
            header = f"{separator}\n{header_name}\n{separator}\n"
            candidate = header + candidate_body
            if len(candidate) <= limit:
                selected.append(entry["content"])
                body = candidate_body
        if not selected:
            # Keep at least the top memory, clipped to fit.
            top = entries[0]["content"]
            header = f"{separator}\n{header_name}\n{separator}\n"
            remaining = max(0, limit - len(header))
            body = top[:remaining]
        return f"{separator}\n{header_name}\n{separator}\n{body}"

    def export_snapshot(self) -> Dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memory_entries ORDER BY created_at ASC, updated_at ASC"
            ).fetchall()
            lane_rows = conn.execute(
                "SELECT * FROM memory_lanes ORDER BY created_at ASC, updated_at ASC"
            ).fetchall()
            lattice_rows = conn.execute(
                "SELECT * FROM memory_lattice_events ORDER BY created_at ASC, id ASC"
            ).fetchall()
        entries = [self._row_to_dict(r) for r in rows]
        lanes = [self._row_to_dict(r) for r in lane_rows]
        lattice_events = [self._row_to_dict(r) for r in lattice_rows]
        return {
            "format": "hermes-memory-snapshot-v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
            "lane_count": len(lanes),
            "lattice_event_count": len(lattice_events),
            "entries": entries,
            "lanes": lanes,
            "lattice_events": lattice_events,
        }

    def export_snapshot_to_file(self, output_path: Path | str) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.export_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def import_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if snapshot.get("format") != "hermes-memory-snapshot-v1":
            return {"success": False, "error": "Unsupported snapshot format."}
        imported = 0
        updated = 0
        with self._connect() as conn:
            for entry in snapshot.get("entries", []):
                existing = conn.execute("SELECT updated_at FROM memory_entries WHERE id = ?", (entry["id"],)).fetchone()
                payload = (
                    entry["id"], entry["target"], entry["kind"], entry["content"], entry["status"],
                    entry.get("scope", "global"), entry.get("scope_value"), entry.get("source", "manual"),
                    float(entry.get("confidence", 1.0)), float(entry.get("importance", 0.5)),
                    float(entry.get("created_at", time.time())), float(entry.get("updated_at", time.time())),
                    entry.get("last_used_at"), int(entry.get("use_count", 0)), entry.get("supersedes_id"),
                    entry.get("fingerprint") or self._fingerprint(entry["target"], entry["content"]),
                )
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO memory_entries(
                            id, target, kind, content, status, scope, scope_value, source,
                            confidence, importance, created_at, updated_at, last_used_at,
                            use_count, supersedes_id, fingerprint
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        payload,
                    )
                    imported += 1
                elif float(entry.get("updated_at", 0)) > float(existing["updated_at"] or 0):
                    conn.execute(
                        """
                        UPDATE memory_entries
                        SET target = ?, kind = ?, content = ?, status = ?, scope = ?, scope_value = ?,
                            source = ?, confidence = ?, importance = ?, created_at = ?, updated_at = ?,
                            last_used_at = ?, use_count = ?, supersedes_id = ?, fingerprint = ?
                        WHERE id = ?
                        """,
                        (
                            entry["target"], entry["kind"], entry["content"], entry["status"],
                            entry.get("scope", "global"), entry.get("scope_value"), entry.get("source", "manual"),
                            float(entry.get("confidence", 1.0)), float(entry.get("importance", 0.5)),
                            float(entry.get("created_at", time.time())), float(entry.get("updated_at", time.time())),
                            entry.get("last_used_at"), int(entry.get("use_count", 0)), entry.get("supersedes_id"),
                            entry.get("fingerprint") or self._fingerprint(entry["target"], entry["content"]), entry["id"],
                        ),
                    )
                    updated += 1
            self._export_markdown_locked(conn, "memory")
            self._export_markdown_locked(conn, "user")
            conn.commit()
        return {"success": True, "imported": imported, "updated": updated, "entry_count": snapshot.get("entry_count", 0)}

    def import_snapshot_from_file(self, input_path: Path | str) -> Dict[str, Any]:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        return self.import_snapshot(payload)
