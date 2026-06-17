"""SQLite + OpenViking storage layer for the Context Pager engine.

SQLite is the primary fast store for tool-output hashes and session metadata.
OpenViking is a best-effort warm archival tier — if unavailable, the engine
works perfectly in local-only mode.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_DB_DIR = "~/.hermes/data"
_DEFAULT_DB_NAME = "context_pager.db"
_OV_ENDPOINT = "http://127.0.0.1:1933"
_OV_TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# SQLite Store
# ---------------------------------------------------------------------------


class SQLiteStore:
    """Persistent hash store for tool output deduplication.

    Thread-safe via a reentrant lock.  All public methods catch exceptions
    and log rather than raising, so callers never need to handle store errors.
    """

    def __init__(self, db_path: str | None = None):
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection  # type checker: always set by _init_db
        self._db_path = self._resolve_path(db_path)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_tool_hash(
        self,
        session_id: str,
        turn_index: int,
        msg_index: int,
        content_hash: str,
        content: str,
        tool_name: str,
    ) -> None:
        """Record a tool output hash in the database."""
        try:
            with self._lock:
                self._conn.execute(
                    """INSERT OR REPLACE INTO tool_outputs
                       (session_id, turn_index, msg_index, content_hash, content, tool_name)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, turn_index, msg_index, content_hash, content, tool_name),
                )
                self._conn.commit()
        except Exception as exc:
            logger.warning("store_tool_hash failed: %s", exc)

    def find_tool_duplicates(
        self,
        session_id: str,
        content_hash: str,
        older_than_turn: int,
    ) -> List[Dict[str, Any]]:
        """Find tool outputs with the same hash that are *more recent* than the given turn.

        Returns list of dicts with keys: turn_index, msg_index, tool_name.
        """
        try:
            with self._lock:
                cursor = self._conn.execute(
                    """SELECT turn_index, msg_index, tool_name
                       FROM tool_outputs
                       WHERE session_id = ? AND content_hash = ? AND turn_index > ?
                       ORDER BY turn_index ASC, msg_index ASC""",
                    (session_id, content_hash, older_than_turn),
                )
                return [
                    {
                        "turn_index": row[0],
                        "msg_index": row[1],
                        "tool_name": row[2],
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as exc:
            logger.warning("find_tool_duplicates failed: %s", exc)
            return []

    def store_session_metadata(
        self,
        session_id: str,
        turn_count: int,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Upsert session-level metadata."""
        try:
            meta_json = json.dumps(metadata or {})
            with self._lock:
                self._conn.execute(
                    """INSERT OR REPLACE INTO session_metadata
                       (session_id, turn_count, metadata_json)
                       VALUES (?, ?, ?)""",
                    (session_id, turn_count, meta_json),
                )
                self._conn.commit()
        except Exception as exc:
            logger.warning("store_session_metadata failed: %s", exc)

    def clear_session(self, session_id: str) -> None:
        """Remove all data for a given session."""
        try:
            with self._lock:
                self._conn.execute(
                    "DELETE FROM tool_outputs WHERE session_id = ?",
                    (session_id,),
                )
                self._conn.execute(
                    "DELETE FROM session_metadata WHERE session_id = ?",
                    (session_id,),
                )
                self._conn.commit()
        except Exception as exc:
            logger.warning("clear_session failed: %s", exc)

    def close(self) -> None:
        """Close the database connection."""
        try:
            with self._lock:
                if self._conn:
                    self._conn.close()
        except Exception as exc:
            logger.warning("close failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_path(self, db_path: str | None) -> str:
        if db_path:
            return os.path.expanduser(db_path)
        db_dir = os.path.expanduser(_DEFAULT_DB_DIR)
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, _DEFAULT_DB_NAME)

    def _init_db(self) -> None:
        try:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS tool_outputs (
                    session_id   TEXT NOT NULL,
                    turn_index   INTEGER NOT NULL,
                    msg_index    INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    tool_name    TEXT NOT NULL DEFAULT '',
                    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (session_id, turn_index, msg_index)
                );
                CREATE INDEX IF NOT EXISTS idx_tool_hash
                    ON tool_outputs(session_id, content_hash);
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id    TEXT PRIMARY KEY,
                    turn_count    INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            self._conn.commit()
            logger.debug("SQLite store initialized at %s", self._db_path)
        except Exception as exc:
            logger.error("Failed to initialize SQLite store at %s: %s", self._db_path, exc)
            self._conn = sqlite3.connect(":memory:")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS tool_outputs (
                    session_id   TEXT NOT NULL,
                    turn_index   INTEGER NOT NULL,
                    msg_index    INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    tool_name    TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (session_id, turn_index, msg_index)
                );
                CREATE INDEX IF NOT EXISTS idx_tool_hash
                    ON tool_outputs(session_id, content_hash);
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id    TEXT PRIMARY KEY,
                    turn_count    INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            self._conn.commit()


# ---------------------------------------------------------------------------
# OpenViking Archival Client (best-effort)
# ---------------------------------------------------------------------------


class OpenVikingArchiver:
    """Best-effort archival client for OpenViking.

    If the server is unavailable, all operations silently no-op.
    """

    def __init__(self, endpoint: str | None = None):
        self._endpoint = (endpoint or _OV_ENDPOINT).rstrip("/")
        self._httpx = None
        self._available = False
        self._probed = False
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """Lazy health check — cached after first probe."""
        if not self._probed:
            self._probe_health()
        return self._available

    def archive_turn(
        self,
        session_id: str,
        turn_index: int,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """Archive a full (pre-compression) turn to OpenViking.

        Returns True if archival succeeded, False otherwise.
        """
        if not self.is_available():
            return False
        try:
            client = self._get_httpx()
            if client is None:
                return False
            payload = {
                "session_id": session_id,
                "turn_index": turn_index,
                "messages": messages,
                "compressed": False,
                "archived_by": "context_pager",
            }
            resp = client.post(
                f"{self._endpoint}/api/v1/memory/context_pager/archive",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=_OV_TIMEOUT,
            )
            return resp.status_code < 400
        except Exception as exc:
            logger.debug("OpenViking archive_turn failed (non-fatal): %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_httpx(self):
        if self._httpx is not None:
            return self._httpx
        try:
            import httpx
            self._httpx = httpx
        except ImportError:
            self._httpx = None
        return self._httpx

    def _probe_health(self):
        with self._lock:
            if self._probed:
                return
            self._probed = True
            try:
                client = self._get_httpx()
                if client is None:
                    return
                resp = client.get(
                    f"{self._endpoint}/health",
                    timeout=3.0,
                )
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
