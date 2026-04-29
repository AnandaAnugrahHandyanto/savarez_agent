"""Hermes-owned durable state for Feishu Image2 jobs.

This module deliberately lives in Hermes instead of the historical
``marketing-hub/scripts`` runtime.  It provides the persistence surface needed
by the Feishu ingress/worker layers: enqueue an inbound visual request, persist
safe artifacts, claim an exact task, and mark terminal fail-closed outcomes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from gateway.image2_prompt import build_visual_brief_from_payload, compile_image2_prompt_payload


CLAIMABLE_STATUSES = ("ack_sent", "queued", "failed_retryable")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Image2JobStore:
    """SQLite-backed job store for Hermes-owned Image2 requests."""

    def __init__(self, *, db_path: Path, runtime_root: Path) -> None:
        self.db_path = Path(db_path)
        self.runtime_root = Path(runtime_root)

    def enqueue_feishu(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

        task_id = self._task_id(payload)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (task_id,)).fetchone()
        if existing is not None:
            row = dict(existing)
            row["already_existed"] = True
            return {
                "task_id": str(row.get("task_id") or task_id),
                "status": str(row.get("status") or ""),
                "chat_id": str(row.get("chat_id") or ""),
                "root_id": str(row.get("root_id") or ""),
                "thread_id": str(row.get("thread_id") or row.get("root_id") or ""),
                "job_dir": str(row.get("job_dir") or self.runtime_root / task_id),
                "already_existed": True,
            }

        now = _utc_now()
        chat_id = str(payload.get("chat_id") or "")
        root_id = str(payload.get("root_id") or payload.get("thread_id") or "")
        thread_id = str(payload.get("thread_id") or root_id or "")
        feishu_message_id = str(payload.get("feishu_message_id") or "")
        source_files = payload.get("source_files") or []

        job_dir = self.runtime_root / task_id
        job_dir.mkdir(parents=True, exist_ok=True)
        payload_dict = dict(payload)
        brief = build_visual_brief_from_payload(payload_dict)
        compiled_prompt = compile_image2_prompt_payload(payload_dict, brief=brief)
        prompt_text = str(compiled_prompt.get("one_shot_design_prompt") or payload_dict.get("text") or "")

        (job_dir / "message.json").write_text(
            json.dumps(payload_dict, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (job_dir / "source_manifest.json").write_text(
            json.dumps(source_files, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (job_dir / "raw_request.txt").write_text(str(payload_dict.get("text") or ""), encoding="utf-8")
        (job_dir / "brief.json").write_text(
            json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (job_dir / "compiled_prompt.json").write_text(
            json.dumps(compiled_prompt, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (job_dir / "one_shot_design_prompt.txt").write_text(prompt_text, encoding="utf-8")
        (job_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO image2_jobs (
                    task_id, feishu_message_id, chat_id, root_id, thread_id, status,
                    payload_json, source_files_json, job_dir, created_at, updated_at,
                    worker_id, claimed_at, completed_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    task_id,
                    feishu_message_id,
                    chat_id,
                    root_id,
                    thread_id,
                    "ack_sent",
                    _json_dump(dict(payload)),
                    _json_dump(source_files),
                    str(job_dir),
                    now,
                    now,
                ),
            ).rowcount == 1
            row = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (task_id,)).fetchone()
        row_dict = dict(row) if row is not None else {}
        return {
            "task_id": str(row_dict.get("task_id") or task_id),
            "status": str(row_dict.get("status") or "ack_sent"),
            "chat_id": str(row_dict.get("chat_id") or chat_id),
            "root_id": str(row_dict.get("root_id") or root_id),
            "thread_id": str(row_dict.get("thread_id") or thread_id),
            "job_dir": str(row_dict.get("job_dir") or job_dir),
            "already_existed": not inserted,
        }

    def get_job(self, task_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (str(task_id),)).fetchone()
            return dict(row) if row is not None else None

    def claim_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        claimable_statuses: Sequence[str] = CLAIMABLE_STATUSES,
    ) -> dict[str, Any] | None:
        """Claim exactly ``task_id`` if it is claimable; never fall back to older jobs."""
        self._ensure_schema()
        statuses = tuple(str(status) for status in claimable_statuses)
        if not statuses:
            return None
        placeholders = ",".join("?" for _ in statuses)
        now = _utc_now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (str(task_id),)).fetchone()
            if row is None or str(row["status"] or "") not in statuses:
                conn.rollback()
                return None
            params = ("processing", str(worker_id), now, now, str(task_id), *statuses)
            updated = conn.execute(
                f"""
                UPDATE image2_jobs
                   SET status = ?, worker_id = ?, claimed_at = ?, updated_at = ?, last_error = NULL
                 WHERE task_id = ? AND status IN ({placeholders})
                """,
                params,
            )
            if updated.rowcount != 1:
                conn.rollback()
                return None
            claimed = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (str(task_id),)).fetchone()
            conn.commit()
            return dict(claimed) if claimed is not None else None

    def mark_status(
        self,
        *,
        task_id: str,
        status: str,
        worker_id: str | None = None,
        last_error: str | None = None,
        completed: bool = False,
    ) -> dict[str, Any] | None:
        self._ensure_schema()
        now = _utc_now()
        completed_at = now if completed else None
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                UPDATE image2_jobs
                   SET status = ?,
                       worker_id = COALESCE(?, worker_id),
                       last_error = ?,
                       completed_at = COALESCE(?, completed_at),
                       updated_at = ?
                 WHERE task_id = ?
                """,
                (str(status), worker_id, last_error, completed_at, now, str(task_id)),
            )
            row = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (str(task_id),)).fetchone()
            return dict(row) if row is not None else None

    def mark_failed_final(self, *, task_id: str, worker_id: str | None, last_error: str) -> dict[str, Any] | None:
        return self.mark_status(
            task_id=task_id,
            status="failed_final",
            worker_id=worker_id,
            last_error=last_error,
            completed=True,
        )

    def mark_readback_verified(self, *, task_id: str, worker_id: str | None) -> dict[str, Any] | None:
        return self.mark_status(
            task_id=task_id,
            status="readback_verified",
            worker_id=worker_id,
            last_error="",
            completed=True,
        )

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS image2_jobs (
                    task_id TEXT PRIMARY KEY,
                    feishu_message_id TEXT,
                    chat_id TEXT,
                    root_id TEXT,
                    thread_id TEXT,
                    status TEXT,
                    payload_json TEXT,
                    source_files_json TEXT,
                    job_dir TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    worker_id TEXT,
                    claimed_at TEXT,
                    completed_at TEXT,
                    last_error TEXT
                )
                """
            )
            existing = {row[1] for row in conn.execute("PRAGMA table_info(image2_jobs)")}
            migrations = {
                "worker_id": "TEXT",
                "claimed_at": "TEXT",
                "completed_at": "TEXT",
                "last_error": "TEXT",
            }
            allowed_migration_columns = set(migrations)
            allowed_migration_types = {"TEXT"}
            for column, ddl in migrations.items():
                if column not in allowed_migration_columns or ddl not in allowed_migration_types:
                    raise ValueError("unsupported Image2 job schema migration")
                if column not in existing:
                    conn.execute("ALTER TABLE image2_jobs ADD COLUMN " + column + " " + ddl)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_image2_jobs_chat_root ON image2_jobs(chat_id, root_id, thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_image2_jobs_status_updated ON image2_jobs(status, updated_at)")

    @staticmethod
    def _task_id(payload: Mapping[str, Any]) -> str:
        stable_parts = [
            str(payload.get("source_platform") or "feishu"),
            str(payload.get("feishu_message_id") or ""),
            str(payload.get("chat_id") or ""),
            str(payload.get("root_id") or ""),
            str(payload.get("thread_id") or ""),
            str(payload.get("text") or ""),
        ]
        seed = "\x1f".join(stable_parts)
        if seed.strip("\x1f"):
            digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        else:
            digest = uuid.uuid4().hex[:16]
        return f"img2_{digest}"
