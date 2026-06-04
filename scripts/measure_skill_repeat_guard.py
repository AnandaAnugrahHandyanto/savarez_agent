#!/usr/bin/env python3
"""Measure skill-repeat-guard-v0 by marker cohort.

This script intentionally does not rely on wall-clock windows alone. It splits
sessions by whether their stored system prompt contains the repeat-guard marker,
then reports same-session skill_view repeats for guard-present, guard-absent,
after-compression, and hard-gate/new-phase cohorts.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

MARKER = "skill-repeat-guard-v0"
COMPRESSION_RE = re.compile(
    r"context compaction|context compression|\[context compaction|\[context compression",
    re.IGNORECASE,
)
HARD_GATE_RE = re.compile(
    r"\b(hard[- ]?gate|owner gate|authority|new phase|audit|review|commit|push|merge|"
    r"ci|pr|deploy|live|credential|security|destructive|irreversible)\b",
    re.IGNORECASE,
)


def _default_state_db() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    return hermes_home / "state.db"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if table not in {"sessions", "messages"}:
        raise ValueError(f"unsupported table for measurement: {table}")
    return {row[1] for row in conn.execute("pragma table_info(" + table + ")")}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _parse_jsonish(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _iter_tool_calls(tool_calls_raw: str | None) -> Iterable[tuple[str | None, dict[str, Any]]]:
    calls = _as_list(_parse_jsonish(tool_calls_raw))
    for call in calls:
        if not isinstance(call, dict):
            continue
        function_obj = call.get("function")
        function: dict[str, Any] = function_obj if isinstance(function_obj, dict) else {}
        name = function.get("name") or call.get("name")
        args = function.get("arguments") or call.get("arguments") or {}
        args = _parse_jsonish(args)
        if not isinstance(args, dict):
            args = {}
        yield name, args


def _session_rows(conn: sqlite3.Connection, start: float | None, end: float | None) -> list[sqlite3.Row]:
    session_cols = _table_columns(conn, "sessions")
    wanted = ["id", "started_at"]
    optional = ["ended_at", "title", "system_prompt"]
    select_cols = wanted + [col for col in optional if col in session_cols]
    query = f"select {', '.join(select_cols)} from sessions where 1=1"
    params: list[Any] = []
    if start is not None:
        query += " and started_at >= ?"
        params.append(start)
    if end is not None:
        query += " and started_at < ?"
        params.append(end)
    query += " order by started_at, id"
    return list(conn.execute(query, params))


def _message_rows(conn: sqlite3.Connection, session_ids: set[str]) -> list[sqlite3.Row]:
    if not session_ids:
        return []
    message_cols = _table_columns(conn, "messages")
    required = ["id", "session_id", "role", "timestamp"]
    optional = ["content", "tool_calls", "active"]
    select_cols = required + [col for col in optional if col in message_cols]
    placeholders = ",".join("?" for _ in session_ids)
    query = f"select {', '.join(select_cols)} from messages where session_id in ({placeholders})"
    if "active" in message_cols:
        query += " and active = 1"
    query += " order by timestamp, id"
    return list(conn.execute(query, sorted(session_ids)))


def _summarize_sessions(
    session_ids: set[str],
    skill_events: list[dict[str, Any]],
    *,
    since_by_session: dict[str, float] | None = None,
) -> dict[str, Any]:
    cohort_events = []
    for event in skill_events:
        sid = event["session_id"]
        if sid not in session_ids:
            continue
        if since_by_session is not None and event["timestamp"] < since_by_session[sid]:
            continue
        cohort_events.append(event)
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in cohort_events:
        by_session[event["session_id"]].append(event)

    exact_repeats = 0
    same_skill_repeats = 0
    exact_counter: Counter[tuple[str | None, str | None]] = Counter()
    skill_counter: Counter[str | None] = Counter()
    total_counter: Counter[tuple[str | None, str | None]] = Counter()

    for events in by_session.values():
        seen_exact: set[tuple[str | None, str | None]] = set()
        seen_skills: set[str | None] = set()
        for event in events:
            exact_key = (event.get("skill"), event.get("file_path"))
            skill_key = event.get("skill")
            total_counter[exact_key] += 1
            if exact_key in seen_exact:
                exact_repeats += 1
                exact_counter[exact_key] += 1
            else:
                seen_exact.add(exact_key)
            if skill_key in seen_skills:
                same_skill_repeats += 1
                skill_counter[skill_key] += 1
            else:
                seen_skills.add(skill_key)

    skill_view_count = len(cohort_events)
    return {
        "session_count": len(session_ids),
        "skill_view_count": skill_view_count,
        "skill_view_sessions": len(by_session),
        "exact_repeat_count": exact_repeats,
        "same_skill_repeat_count": same_skill_repeats,
        "exact_repeat_rate": exact_repeats / skill_view_count if skill_view_count else 0.0,
        "same_skill_repeat_rate": same_skill_repeats / skill_view_count if skill_view_count else 0.0,
        "top_skill_views": [
            {"skill": skill, "file_path": file_path, "count": count}
            for (skill, file_path), count in total_counter.most_common(10)
        ],
        "top_exact_repeats": [
            {"skill": skill, "file_path": file_path, "count": count}
            for (skill, file_path), count in exact_counter.most_common(10)
        ],
        "top_same_skill_repeats": [
            {"skill": skill, "count": count}
            for skill, count in skill_counter.most_common(10)
        ],
    }


def analyze_skill_repeat_guard(
    db_path: str | Path | None = None,
    *,
    marker: str = MARKER,
    start: float | None = None,
    end: float | None = None,
) -> dict[str, Any]:
    """Analyze skill_view repeat rates by prompt-marker and risk cohorts."""
    path = Path(db_path) if db_path is not None else _default_state_db()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sessions = _session_rows(conn, start, end)
        session_ids = {str(row["id"]) for row in sessions}
        messages = _message_rows(conn, session_ids)
    finally:
        conn.close()

    guard_present: set[str] = set()
    guard_absent: set[str] = set()
    for row in sessions:
        system_prompt = row["system_prompt"] if "system_prompt" in row.keys() else ""
        sid = str(row["id"])
        if marker in (system_prompt or ""):
            guard_present.add(sid)
        else:
            guard_absent.add(sid)

    compression_since: dict[str, float] = {}
    hard_gate_since: dict[str, float] = {}
    skill_events: list[dict[str, Any]] = []
    all_tool_call_count = 0
    for row in messages:
        sid = str(row["session_id"])
        timestamp = float(row["timestamp"])
        content = row["content"] if "content" in row.keys() else ""
        if content and COMPRESSION_RE.search(content):
            compression_since[sid] = min(timestamp, compression_since.get(sid, timestamp))
        if content and HARD_GATE_RE.search(content):
            hard_gate_since[sid] = min(timestamp, hard_gate_since.get(sid, timestamp))
        tool_calls_raw = row["tool_calls"] if "tool_calls" in row.keys() else None
        for tool_name, args in _iter_tool_calls(tool_calls_raw):
            all_tool_call_count += 1
            if tool_name != "skill_view":
                continue
            skill_events.append(
                {
                    "session_id": sid,
                    "message_id": row["id"],
                    "timestamp": row["timestamp"],
                    "skill": args.get("name"),
                    "file_path": args.get("file_path"),
                }
            )

    cohorts = {
        "guard_present": _summarize_sessions(guard_present, skill_events),
        "guard_absent": _summarize_sessions(guard_absent, skill_events),
        "after_compression": _summarize_sessions(
            set(compression_since), skill_events, since_by_session=compression_since
        ),
        "hard_gate_or_new_phase": _summarize_sessions(
            set(hard_gate_since), skill_events, since_by_session=hard_gate_since
        ),
    }
    return {
        "marker": marker,
        "db_path": str(path),
        "start": start,
        "end": end,
        "session_count": len(session_ids),
        "message_count": len(messages),
        "tool_call_count": all_tool_call_count,
        "skill_view_count": len(skill_events),
        "cohorts": cohorts,
    }


def _format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_report(report: dict[str, Any]) -> str:
    labels = {
        "guard_present": "guard-present sessions",
        "guard_absent": "guard-absent sessions",
        "after_compression": "after-compression sessions",
        "hard_gate_or_new_phase": "hard-gate/new-phase sessions",
    }
    lines = [
        f"Skill repeat guard marker-cohort report ({report['marker']})",
        f"DB: {report['db_path']}",
        f"Sessions: {report['session_count']}",
        f"Messages: {report['message_count']}",
        f"Tool calls parsed: {report['tool_call_count']}",
        f"skill_view calls: {report['skill_view_count']}",
        "",
    ]
    for key, label in labels.items():
        cohort = report["cohorts"][key]
        lines.extend(
            [
                f"{label}:",
                f"  sessions: {cohort['session_count']}",
                f"  skill_view calls: {cohort['skill_view_count']}",
                f"  exact repeats: {cohort['exact_repeat_count']} ({_format_pct(cohort['exact_repeat_rate'])})",
                f"  same-skill repeats: {cohort['same_skill_repeat_count']} ({_format_pct(cohort['same_skill_repeat_rate'])})",
            ]
        )
        if cohort["top_exact_repeats"]:
            top = ", ".join(
                f"{item['skill']}:{item['file_path'] or '<main>'}={item['count']}"
                for item in cohort["top_exact_repeats"][:5]
            )
            lines.append(f"  top exact repeats: {top}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        dt = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.timestamp()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=_default_state_db())
    parser.add_argument("--marker", default=MARKER)
    parser.add_argument("--start", help="Unix timestamp or ISO datetime")
    parser.add_argument("--end", help="Unix timestamp or ISO datetime")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    report = analyze_skill_repeat_guard(
        args.db,
        marker=args.marker,
        start=_parse_time(args.start),
        end=_parse_time(args.end),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by CLI users
    raise SystemExit(main())
