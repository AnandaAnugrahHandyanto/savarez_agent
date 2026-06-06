from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermex.core.embedding import cosine_similarity
from hermex.core.store.base import (
    AbstractPatternStore,
    AbstractSessionStore,
    AbstractSkillRegistry,
    AbstractTelemetryStore,
    CoreStore,
    CrystallizedSkill,
    PatternRecord,
    Session,
    TelemetryEvent,
    TelemetryHit,
)


@dataclass(frozen=True)
class SQLiteStoreConfig:
    path: Path


class _SQLiteDB:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    def _initialize(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    metadata TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    tool_name TEXT,
                    success INTEGER NOT NULL,
                    failure_reason TEXT,
                    source_accuracy REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_key TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    session_ids TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skills (
                    pattern_key TEXT PRIMARY KEY,
                    skill_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )
            self._conn.commit()


class SQLiteSessionStore(AbstractSessionStore):
    def __init__(self, db: _SQLiteDB) -> None:
        self._db = db

    async def load_or_create(self, session_id: str) -> Session:
        def load() -> Session:
            rows = self._db.query("SELECT metadata FROM sessions WHERE session_id = ?", (session_id,))
            if rows:
                return Session(session_id=session_id, metadata=json.loads(rows[0]["metadata"]))
            self._db.execute(
                "INSERT INTO sessions (session_id, metadata, updated_at) VALUES (?, ?, ?)",
                (session_id, "{}", time.time()),
            )
            return Session(session_id=session_id)

        return await asyncio.to_thread(load)

    async def save(self, session: Session) -> None:
        def save() -> None:
            self._db.execute(
                """
                INSERT INTO sessions (session_id, metadata, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (session.session_id, json.dumps(session.metadata), time.time()),
            )

        await asyncio.to_thread(save)


class SQLiteTelemetryStore(AbstractTelemetryStore):
    def __init__(self, db: _SQLiteDB) -> None:
        self._db = db

    async def emit(self, trace: TelemetryEvent) -> None:
        def emit() -> None:
            self._db.execute(
                """
                INSERT INTO telemetry
                    (session_id, summary, embedding, tool_name, success, failure_reason, source_accuracy, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.session_id,
                    trace.summary,
                    json.dumps(trace.embedding),
                    trace.tool_name,
                    1 if trace.success else 0,
                    trace.failure_reason,
                    trace.source_accuracy,
                    time.time(),
                ),
            )

        await asyncio.to_thread(emit)

    async def search_similar(
        self,
        embedding: list[float],
        top_k: int,
        exclude_session: str | None = None,
    ) -> list[TelemetryHit]:
        def search() -> list[TelemetryHit]:
            rows = self._db.query(
                """
                SELECT session_id, summary, embedding, tool_name, success, failure_reason, source_accuracy
                FROM telemetry
                WHERE (? IS NULL OR session_id != ?)
                ORDER BY id DESC
                """,
                (exclude_session, exclude_session),
            )
            hits: list[TelemetryHit] = []
            for row in rows:
                score = cosine_similarity(embedding, json.loads(row["embedding"]))
                if score <= 0:
                    continue
                hits.append(_row_to_hit(row, score))
            hits.sort(key=lambda hit: hit.score * hit.source_accuracy, reverse=True)
            return hits[:top_k]

        return await asyncio.to_thread(search)

    async def search_failures(self, embedding: list[float], top_k: int) -> list[TelemetryHit]:
        def search() -> list[TelemetryHit]:
            rows = self._db.query(
                """
                SELECT session_id, summary, embedding, tool_name, success, failure_reason, source_accuracy
                FROM telemetry
                WHERE success = 0
                ORDER BY id DESC
                """
            )
            hits: list[TelemetryHit] = []
            for row in rows:
                score = cosine_similarity(embedding, json.loads(row["embedding"]))
                if score <= 0:
                    continue
                hits.append(_row_to_hit(row, score))
            hits.sort(key=lambda hit: hit.score * hit.source_accuracy, reverse=True)
            return hits[:top_k]

        return await asyncio.to_thread(search)


class SQLitePatternStore(AbstractPatternStore):
    def __init__(self, db: _SQLiteDB) -> None:
        self._db = db

    async def increment(self, pattern: tuple[str, ...], session_id: str) -> int:
        pattern_json = json.dumps(list(pattern))

        def increment() -> int:
            rows = self._db.query("SELECT count, session_ids FROM patterns WHERE pattern_key = ?", (pattern_json,))
            if rows:
                count = int(rows[0]["count"]) + 1
                session_ids = sorted(set(json.loads(rows[0]["session_ids"])) | {session_id})
                self._db.execute(
                    "UPDATE patterns SET count = ?, session_ids = ?, updated_at = ? WHERE pattern_key = ?",
                    (count, json.dumps(session_ids), time.time(), pattern_json),
                )
                return count
            self._db.execute(
                "INSERT INTO patterns (pattern_key, count, session_ids, updated_at) VALUES (?, ?, ?, ?)",
                (pattern_json, 1, json.dumps([session_id]), time.time()),
            )
            return 1

        return await asyncio.to_thread(increment)

    async def get_above_threshold(self, threshold: int) -> list[PatternRecord]:
        def get() -> list[PatternRecord]:
            rows = self._db.query(
                "SELECT pattern_key, count, session_ids FROM patterns WHERE count >= ? ORDER BY count DESC",
                (threshold,),
            )
            return [
                PatternRecord(
                    pattern_key=tuple(json.loads(row["pattern_key"])),
                    count=int(row["count"]),
                    session_ids=list(json.loads(row["session_ids"])),
                )
                for row in rows
            ]

        return await asyncio.to_thread(get)


class SQLiteSkillRegistry(AbstractSkillRegistry):
    def __init__(self, db: _SQLiteDB) -> None:
        self._db = db

    async def list_all(self) -> list[CrystallizedSkill]:
        def list_all() -> list[CrystallizedSkill]:
            rows = self._db.query("SELECT skill_json FROM skills ORDER BY created_at ASC")
            return [_skill_from_json(row["skill_json"]) for row in rows]

        return await asyncio.to_thread(list_all)

    async def register_if_absent(self, pattern_key: tuple[str, ...], skill: Any) -> bool:
        pattern_json = json.dumps(list(pattern_key))

        def register() -> bool:
            rows = self._db.query("SELECT pattern_key FROM skills WHERE pattern_key = ?", (pattern_json,))
            if rows:
                return False
            self._db.execute(
                "INSERT INTO skills (pattern_key, skill_json, created_at) VALUES (?, ?, ?)",
                (pattern_json, _skill_to_json(skill), time.time()),
            )
            return True

        return await asyncio.to_thread(register)

    async def exists_for_pattern(self, pattern_key: tuple[str, ...]) -> bool:
        pattern_json = json.dumps(list(pattern_key))

        def exists() -> bool:
            rows = self._db.query("SELECT pattern_key FROM skills WHERE pattern_key = ?", (pattern_json,))
            return bool(rows)

        return await asyncio.to_thread(exists)


def build_sqlite_core_store(config: SQLiteStoreConfig) -> CoreStore:
    db = _SQLiteDB(config.path)
    return CoreStore(
        patterns=SQLitePatternStore(db),
        telemetry=SQLiteTelemetryStore(db),
        sessions=SQLiteSessionStore(db),
        skills=SQLiteSkillRegistry(db),
    )


def _row_to_hit(row: sqlite3.Row, score: float) -> TelemetryHit:
    return TelemetryHit(
        session_id=row["session_id"],
        summary=row["summary"],
        score=score,
        source_accuracy=float(row["source_accuracy"]),
        tool_name=row["tool_name"],
        success=bool(row["success"]),
        failure_reason=row["failure_reason"],
    )


def _skill_to_json(skill: Any) -> str:
    if isinstance(skill, CrystallizedSkill):
        payload = {
            "pattern_key": list(skill.pattern_key),
            "tool_name": skill.tool_name,
            "description": skill.description,
            "input_schema": skill.input_schema,
            "execution_plan": skill.execution_plan,
        }
    else:
        payload = dict(skill)
    return json.dumps(payload)


def _skill_from_json(raw: str) -> CrystallizedSkill:
    payload = json.loads(raw)
    return CrystallizedSkill(
        pattern_key=tuple(payload["pattern_key"]),
        tool_name=payload["tool_name"],
        description=payload["description"],
        input_schema=payload["input_schema"],
        execution_plan=payload.get("execution_plan", []),
    )
