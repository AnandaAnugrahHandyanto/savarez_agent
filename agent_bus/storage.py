"""SQLite storage for agent_bus."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

_DB_LOCK = threading.Lock()
_DB_CONN: Optional[sqlite3.Connection] = None


def _db_path() -> Path:
    """Return the agent_bus SQLite path.

    Priority:
    1. $AGENT_BUS_DB_PATH (for shared-workspace setups where OpenClaw's
       sandbox cannot write to ~/.hermes/).
    2. ~/.openclaw/workspace/.agent-bus/agent_bus.db if OpenClaw workspace
       exists — this is writable from both sides (OpenClaw workspace-write
       allows it; Hermes has full FS access).
    3. Fallback to ~/.hermes/agent_bus.db.
    """
    import os as _os

    override = _os.environ.get("AGENT_BUS_DB_PATH")
    if override:
        return Path(override).expanduser()

    shared = Path.home() / ".openclaw" / "workspace" / ".agent-bus" / "agent_bus.db"
    if shared.parent.parent.exists():
        return shared

    return get_hermes_home() / "agent_bus.db"


def get_conn() -> sqlite3.Connection:
    """Get a process-wide SQLite connection (created on first call)."""
    global _DB_CONN
    if _DB_CONN is not None:
        return _DB_CONN
    with _DB_LOCK:
        if _DB_CONN is not None:
            return _DB_CONN
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _ensure_schema(conn)
        _DB_CONN = conn
        return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            goal TEXT NOT NULL,
            success_criteria TEXT,
            context TEXT,
            priority TEXT DEFAULT 'P2',
            status TEXT DEFAULT 'pending',
            result TEXT,
            created_at REAL NOT NULL,
            acked_at REAL,
            completed_at REAL,
            deadline REAL,
            slack_thread_ts TEXT,
            slack_channel TEXT,
            parent_task_id TEXT,
            terminal_broadcast_ok INTEGER DEFAULT 0,
            learning_wiki_path TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_to_status
            ON tasks(to_agent, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_from_status
            ON tasks(from_agent, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_deadline
            ON tasks(deadline) WHERE deadline IS NOT NULL;

        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            ts REAL NOT NULL,
            agent TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_task
            ON task_events(task_id, ts);
    """)
    # Migrate older DBs (add columns if they don't exist).
    existing_cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
    if "terminal_broadcast_ok" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN terminal_broadcast_ok INTEGER DEFAULT 0")
    if "learning_wiki_path" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN learning_wiki_path TEXT")
    if "user_notified" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN user_notified INTEGER DEFAULT 0")
    if "retry_count" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0")
    conn.commit()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def insert_task(task: Dict[str, Any]) -> None:
    conn = get_conn()
    with _DB_LOCK:
        conn.execute(
            """INSERT INTO tasks (
                task_id, from_agent, to_agent, goal, success_criteria,
                context, priority, status, created_at, deadline, parent_task_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task["task_id"], task["from_agent"], task["to_agent"],
                task["goal"], task.get("success_criteria"),
                task.get("context"), task.get("priority", "P2"),
                task.get("status", "pending"), task["created_at"],
                task.get("deadline"), task.get("parent_task_id"),
            ),
        )
        conn.commit()


def update_task(task_id: str, **fields) -> bool:
    if not fields:
        return False
    conn = get_conn()
    cols = ", ".join(f"{k}=?" for k in fields.keys())
    vals = list(fields.values()) + [task_id]
    with _DB_LOCK:
        cur = conn.execute(f"UPDATE tasks SET {cols} WHERE task_id=?", vals)
        conn.commit()
        return cur.rowcount > 0


def get_task_row(task_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,))
    return row_to_dict(cur.fetchone())


def get_task_events(task_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.execute(
        "SELECT * FROM task_events WHERE task_id=? ORDER BY ts ASC",
        (task_id,),
    )
    return [row_to_dict(r) for r in cur.fetchall()]


def add_event(task_id: str, agent: str, event_type: str, payload: Any = None) -> None:
    conn = get_conn()
    payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    with _DB_LOCK:
        conn.execute(
            """INSERT INTO task_events (task_id, ts, agent, event_type, payload)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, time.time(), agent, event_type, payload_json),
        )
        conn.commit()


def query_tasks(
    *,
    to_agent: Optional[str] = None,
    from_agent: Optional[str] = None,
    status_in: Optional[List[str]] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    where = []
    args: List[Any] = []
    if to_agent:
        where.append("to_agent=?")
        args.append(to_agent)
    if from_agent:
        where.append("from_agent=?")
        args.append(from_agent)
    if status_in:
        placeholders = ",".join("?" * len(status_in))
        where.append(f"status IN ({placeholders})")
        args.extend(status_in)
    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    cur = conn.execute(sql, args)
    return [row_to_dict(r) for r in cur.fetchall()]


def query_timed_out(now: float) -> List[Dict[str, Any]]:
    """Tasks past deadline still in a non-terminal state."""
    conn = get_conn()
    cur = conn.execute(
        """SELECT * FROM tasks
           WHERE deadline IS NOT NULL
             AND deadline < ?
             AND status NOT IN ('done', 'fail', 'timeout')""",
        (now,),
    )
    return [row_to_dict(r) for r in cur.fetchall()]
