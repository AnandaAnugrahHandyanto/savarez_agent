"""PostgreSQL-backed Judy calendar.

This module is intentionally small and synchronous, matching the existing
Gateway/tooling style. The calendar lives in the service PostgreSQL database
used by Hermes on this install.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional


VALID_STATUSES = {"pending", "firing", "done", "cancelled"}
VALID_RECURRENCES = {"daily", "weekly", "monthly"}
STALE_FIRING_SECONDS = 30 * 60


def _dsn() -> str:
    return (
        os.environ.get("HERMES_CALENDAR_POSTGRES_DSN", "").strip()
        or os.environ.get("HERMES_KANBAN_POSTGRES_DSN", "").strip()
    )


def _connect():
    dsn = _dsn()
    if not dsn:
        raise RuntimeError(
            "Calendar PostgreSQL runtime requires HERMES_CALENDAR_POSTGRES_DSN "
            "or HERMES_KANBAN_POSTGRES_DSN"
        )
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception as exc:
        raise RuntimeError(f"Calendar PostgreSQL runtime requires psycopg: {exc}") from exc
    conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    ensure_schema(conn)
    return conn


def _jsonb(value: dict[str, Any]):
    try:
        from psycopg.types.json import Jsonb
    except Exception:
        return json.dumps(value)
    return Jsonb(value)


def ensure_schema(conn: Any | None = None) -> None:
    own_conn = conn is None
    if conn is None:
        conn = _connect_without_schema()
    ddl = """
    CREATE TABLE IF NOT EXISTS judy_calendar (
        id BIGSERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        scheduled_at TIMESTAMPTZ NOT NULL,
        recurrence TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_by TEXT DEFAULT 'judy',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        fired_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        session_id TEXT,
        context JSONB NOT NULL DEFAULT '{}'::jsonb,
        tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
        notes TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_judy_calendar_status_due
        ON judy_calendar (status, scheduled_at);
    CREATE INDEX IF NOT EXISTS idx_judy_calendar_tags
        ON judy_calendar USING GIN (tags);
    """
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
    finally:
        if own_conn:
            conn.close()


def _connect_without_schema():
    dsn = _dsn()
    if not dsn:
        raise RuntimeError(
            "Calendar PostgreSQL runtime requires HERMES_CALENDAR_POSTGRES_DSN "
            "or HERMES_KANBAN_POSTGRES_DSN"
        )
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(dsn, row_factory=dict_row, autocommit=True)


def _parse_dt(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return dt.astimezone(timezone.utc)


def _normalize_recurrence(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text not in VALID_RECURRENCES:
        raise ValueError("recurrence must be one of: daily, weekly, monthly")
    return text


def _normalize_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text not in VALID_STATUSES:
        raise ValueError("invalid calendar status")
    return text


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [p.strip() for p in value.split(",")]
    elif isinstance(value, Iterable):
        items = [str(p).strip() for p in value]
    else:
        raise ValueError("tags must be a list of strings")
    return [p for p in items if p]


def _normalize_context(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("context must be a JSON object") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("context must be a JSON object")


def _row_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    for key in ("scheduled_at", "created_at", "fired_at", "completed_at"):
        val = d.get(key)
        if isinstance(val, datetime):
            d[key] = val.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    d["context"] = d.get("context") or {}
    d["tags"] = list(d.get("tags") or [])
    return d


def add_event(
    *,
    title: str,
    scheduled_at: Any,
    description: Optional[str] = None,
    recurrence: Optional[str] = None,
    tags: Any = None,
    context: Any = None,
    created_by: str = "judy",
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    title = str(title or "").strip()
    if not title:
        raise ValueError("title is required")
    scheduled = _parse_dt(scheduled_at, field="scheduled_at")
    recurrence_norm = _normalize_recurrence(recurrence)
    tags_norm = _normalize_tags(tags)
    context_norm = _normalize_context(context)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO judy_calendar
                    (title, description, scheduled_at, recurrence, tags, context,
                     created_by, session_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    title,
                    description,
                    scheduled,
                    recurrence_norm,
                    tags_norm,
                    _jsonb(context_norm),
                    created_by or "judy",
                    session_id,
                ),
            )
            return _row_dict(cur.fetchone())


def list_events(
    *,
    status: Optional[str] = None,
    from_: Any = None,
    to: Any = None,
    tags: Any = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    status_norm = _normalize_status(status)
    from_dt = _parse_dt(from_, field="from") if from_ else None
    to_dt = _parse_dt(to, field="to") if to else None
    tags_norm = _normalize_tags(tags) if tags is not None else []
    limit = max(1, min(int(limit or 50), 200))
    clauses: list[str] = []
    params: list[Any] = []
    if status_norm:
        clauses.append("status = %s")
        params.append(status_norm)
    if from_dt:
        clauses.append("scheduled_at >= %s")
        params.append(from_dt)
    if to_dt:
        clauses.append("scheduled_at <= %s")
        params.append(to_dt)
    if tags_norm:
        clauses.append("tags && %s")
        params.append(tags_norm)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM judy_calendar
                {where}
                ORDER BY scheduled_at ASC, id ASC
                LIMIT %s
                """,
                tuple(params),
            )
            return [_row_dict(row) for row in cur.fetchall()]


def upcoming_events(*, limit: int = 5) -> list[dict[str, Any]]:
    return list_events(status="pending", from_=datetime.now(timezone.utc), limit=limit)


def get_event(event_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM judy_calendar WHERE id = %s", (int(event_id),))
            row = cur.fetchone()
            return _row_dict(row) if row else None


def update_event(event_id: int, **updates: Any) -> Optional[dict[str, Any]]:
    allowed = {"title", "scheduled_at", "description", "tags", "context", "recurrence"}
    fields: list[str] = []
    params: list[Any] = []
    for key, value in updates.items():
        if key not in allowed or value is None:
            continue
        if key == "title":
            value = str(value).strip()
            if not value:
                raise ValueError("title cannot be empty")
        elif key == "scheduled_at":
            value = _parse_dt(value, field="scheduled_at")
        elif key == "tags":
            value = _normalize_tags(value)
        elif key == "context":
            value = _jsonb(_normalize_context(value))
        elif key == "recurrence":
            value = _normalize_recurrence(value)
        fields.append(f"{key} = %s")
        params.append(value)
    if not fields:
        return get_event(event_id)
    params.append(int(event_id))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE judy_calendar SET {', '.join(fields)} WHERE id = %s RETURNING *",
                tuple(params),
            )
            row = cur.fetchone()
            return _row_dict(row) if row else None


def cancel_event(event_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE judy_calendar
                SET status = 'cancelled'
                WHERE id = %s AND status != 'cancelled'
                RETURNING *
                """,
                (int(event_id),),
            )
            row = cur.fetchone()
            return _row_dict(row) if row else None


def _advance(dt: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return dt + timedelta(days=1)
    if recurrence == "weekly":
        return dt + timedelta(weeks=1)
    if recurrence == "monthly":
        month = dt.month + 1
        year = dt.year
        if month > 12:
            month = 1
            year += 1
        day = min(dt.day, _days_in_month(year, month))
        return dt.replace(year=year, month=month, day=day)
    return dt


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    cur = datetime(year, month, 1, tzinfo=timezone.utc)
    return (nxt - cur).days


def mark_done(event_id: int, notes: Optional[str] = None, session_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    event = get_event(event_id)
    if not event:
        return None
    recurrence = event.get("recurrence")
    completed = datetime.now(timezone.utc)
    scheduled = _parse_dt(event["scheduled_at"], field="scheduled_at")
    with _connect() as conn:
        with conn.cursor() as cur:
            if recurrence:
                next_at = _advance(scheduled, recurrence)
                while next_at <= completed:
                    next_at = _advance(next_at, recurrence)
                cur.execute(
                    """
                    UPDATE judy_calendar
                    SET status = 'pending',
                        scheduled_at = %s,
                        fired_at = NULL,
                        completed_at = %s,
                        notes = %s,
                        session_id = COALESCE(%s, session_id)
                    WHERE id = %s
                    RETURNING *
                    """,
                    (next_at, completed, notes, session_id, int(event_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE judy_calendar
                    SET status = 'done',
                        completed_at = %s,
                        notes = %s,
                        session_id = COALESCE(%s, session_id)
                    WHERE id = %s
                    RETURNING *
                    """,
                    (completed, notes, session_id, int(event_id)),
                )
            row = cur.fetchone()
            return _row_dict(row) if row else None


def claim_due_events(*, now: Any = None, limit: int = 10) -> list[dict[str, Any]]:
    now_dt = _parse_dt(now, field="now") if now else datetime.now(timezone.utc)
    limit = max(1, min(int(limit or 10), 50))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH due AS (
                    SELECT id FROM judy_calendar
                    WHERE status = 'pending' AND scheduled_at <= %s
                    ORDER BY scheduled_at ASC, id ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE judy_calendar c
                SET status = 'firing', fired_at = %s
                FROM due
                WHERE c.id = due.id
                RETURNING c.*
                """,
                (now_dt, limit, now_dt),
            )
            return [_row_dict(row) for row in cur.fetchall()]


def requeue_stale_firing(*, older_than_seconds: int = STALE_FIRING_SECONDS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(1, int(older_than_seconds)))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE judy_calendar
                SET status = 'pending', fired_at = NULL
                WHERE status = 'firing' AND fired_at < %s
                """,
                (cutoff,),
            )
            return int(cur.rowcount or 0)


def release_claim(event_id: int) -> Optional[dict[str, Any]]:
    """Return a firing event to pending when Gateway could not dispatch it."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE judy_calendar
                SET status = 'pending', fired_at = NULL
                WHERE id = %s AND status = 'firing'
                RETURNING *
                """,
                (int(event_id),),
            )
            row = cur.fetchone()
            return _row_dict(row) if row else None
