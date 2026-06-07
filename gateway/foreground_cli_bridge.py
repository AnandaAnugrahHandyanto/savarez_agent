"""Foreground CLI ↔ gateway phone-control bridge.

This is intentionally file/SQLite based so a visible Hermes CLI process and the
long-running gateway service can coordinate without tmux, pseudo-terminals, or
hidden background CLI sessions.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from hermes_cli.config import get_hermes_home

DB_PATH = get_hermes_home() / "foreground_cli_bridge.sqlite3"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            client_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            pid INTEGER NOT NULL,
            cwd TEXT,
            session_id TEXT,
            status TEXT NOT NULL DEFAULT 'idle',
            last_user TEXT,
            last_response TEXT,
            updated_at REAL NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS commands (
            id TEXT PRIMARY KEY,
            client_key TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            response TEXT,
            error TEXT,
            source_json TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    return conn


def register_client(client_key: str, name: str, pid: int, cwd: str, session_id: str | None = None) -> int:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO clients (client_key, name, pid, cwd, session_id, status, updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, 'idle', ?, ?)
            ON CONFLICT(client_key) DO UPDATE SET
                name=excluded.name,
                pid=excluded.pid,
                cwd=excluded.cwd,
                session_id=COALESCE(excluded.session_id, clients.session_id),
                updated_at=excluded.updated_at
            """,
            (client_key, name, pid, cwd, session_id, now, now),
        )
        row = conn.execute("SELECT id FROM clients WHERE client_key=?", (client_key,)).fetchone()
        return int(row["id"])


def update_client(client_key: str, **fields: Any) -> None:
    allowed = {"name", "pid", "cwd", "session_id", "status", "last_user", "last_response"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at=?")
    vals.append(time.time())
    vals.append(client_key)
    with _connect() as conn:
        conn.execute(f"UPDATE clients SET {', '.join(sets)} WHERE client_key=?", vals)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def list_clients(max_age: float = 24 * 3600) -> list[dict[str, Any]]:
    cutoff = time.time() - max_age
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM clients WHERE updated_at >= ? ORDER BY id ASC", (cutoff,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["alive"] = _pid_alive(d.get("pid") or -1)
        out.append(d)
    return out


def get_client(number: int) -> dict[str, Any] | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM clients WHERE id=?", (int(number),)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["alive"] = _pid_alive(d.get("pid") or -1)
    return d


def enqueue_command(number: int, text: str, source: dict[str, Any] | None = None) -> str:
    client = get_client(number)
    if not client:
        raise ValueError(f"编号{number}不存在")
    if not client.get("alive"):
        raise ValueError(f"编号{number}窗口进程不在运行")
    cmd_id = uuid.uuid4().hex
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO commands (id, client_key, text, status, source_json, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (cmd_id, client["client_key"], text, json.dumps(source or {}, ensure_ascii=False), now, now),
        )
    return cmd_id


def fetch_next_command(client_key: str) -> dict[str, Any] | None:
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM commands
            WHERE client_key=? AND status='pending'
            ORDER BY created_at ASC LIMIT 1
            """,
            (client_key,),
        ).fetchone()
        if not row:
            conn.commit()
            return None
        conn.execute(
            "UPDATE commands SET status='running', updated_at=? WHERE id=?",
            (time.time(), row["id"]),
        )
        conn.commit()
    return dict(row)


def complete_command(command_id: str, response: str | None = None, error: str | None = None) -> None:
    status = "failed" if error else "done"
    with _connect() as conn:
        conn.execute(
            "UPDATE commands SET status=?, response=?, error=?, updated_at=? WHERE id=?",
            (status, response, error, time.time(), command_id),
        )


def get_command(command_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM commands WHERE id=?", (command_id,)).fetchone()
    return dict(row) if row else None
