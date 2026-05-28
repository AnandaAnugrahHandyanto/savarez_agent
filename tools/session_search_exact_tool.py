#!/usr/bin/env python3
"""
Session Search Exact Tool - Cross-Session Exact Recall

Returns raw message-level or session-grouped hits from the SQLite session store
without any LLM summarization. This is the exact-recall complement to
``session_search``: use it for keys, hashes, UUIDs, long paths, long error
strings, and exact quoted phrases that must be recovered verbatim.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import sqlite3

from tools.registry import registry, tool_error


_MATCH_MODES = {"auto", "fts", "substring"}


def _score_hit(result: Dict[str, Any], query: str) -> tuple:
    snippet = str(result.get("snippet") or "")
    role = str(result.get("role") or "")
    source = str(result.get("source") or "")
    content = str(result.get("content") or "")
    text = content or snippet
    lower = text.lower()
    q = query.lower()

    plain_text_bonus = 0
    if q in lower:
        plain_text_bonus += 4
    if "\\\"query\\\"" in snippet or '"function"' in snippet or 'call_' in snippet:
        plain_text_bonus -= 5
    if snippet.lstrip().startswith("[") or snippet.lstrip().startswith("{"):
        plain_text_bonus -= 3
    if "session_search" in lower or "session_search_exact" in lower:
        plain_text_bonus -= 3
    if "当前能搜到的历史会话里，没找到" in text:
        plain_text_bonus -= 4
    if "key_plaintext" in text or "remote-management.secret-key" in text:
        plain_text_bonus += 2
    if role == "user":
        plain_text_bonus += 2
    elif role == "assistant":
        plain_text_bonus += 1
    elif role == "tool":
        plain_text_bonus -= 2
    if source == "feishu":
        plain_text_bonus += 1
    return (plain_text_bonus, float(result.get("timestamp") or 0.0), int(result.get("id") or 0))


def _split_csv(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",") if p and p.strip()]
    return parts or None


def _format_exact_hit(result: Dict[str, Any], match_mode: str) -> Dict[str, Any]:
    return {
        "message_id": result.get("id"),
        "session_id": result.get("session_id"),
        "role": result.get("role"),
        "source": result.get("source"),
        "model": result.get("model"),
        "when": result.get("timestamp"),
        "session_started": result.get("session_started"),
        "snippet": result.get("snippet") or (result.get("content") or "")[:240],
        "content": result.get("content") or "",
        "tool_name": result.get("tool_name"),
        "context": result.get("context") if isinstance(result.get("context"), list) else [],
        "match_type": match_mode,
    }


def _search_messages_substring(
    db,
    query: str,
    source_filter: Optional[List[str]],
    role_filter: Optional[List[str]],
    limit: int,
) -> List[Dict[str, Any]]:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    where = ["m.content LIKE ? ESCAPE '\\'"]
    params: List[Any] = [f"%{escaped}%"]
    if source_filter is not None:
        where.append(f"s.source IN ({','.join('?' for _ in source_filter)})")
        params.extend(source_filter)
    if role_filter:
        where.append(f"m.role IN ({','.join('?' for _ in role_filter)})")
        params.extend(role_filter)
    sql = f"""
        SELECT m.id, m.session_id, m.role,
               substr(m.content, max(1, instr(m.content, ?) - 40), 160) AS snippet,
               m.content, m.timestamp, m.tool_name,
               s.source, s.model, s.started_at AS session_started
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE {' AND '.join(where)}
        ORDER BY m.timestamp DESC
        LIMIT ?
    """
    bind = [query] + params + [limit]
    with db._lock:
        cursor = db._conn.execute(sql, bind)
        matches = [dict(row) for row in cursor.fetchall()]
    for match in matches:
        match.setdefault("context", [])
    return matches


def check_session_search_exact_requirements() -> bool:
    try:
        from hermes_state import DEFAULT_DB_PATH
        return DEFAULT_DB_PATH.parent.exists()
    except ImportError:
        return False


def session_search_exact(
    query: str,
    role_filter: str = None,
    source_filter: str = None,
    limit: int = 10,
    group_by_session: bool = True,
    match_mode: str = "auto",
    db=None,
) -> str:
    if db is None:
        return tool_error("Session database not available.", success=False)

    query = (query or "").strip()
    if not query:
        return tool_error("query is required for session_search_exact.", success=False)

    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
    limit = max(1, min(limit, 50))

    if not isinstance(group_by_session, bool):
        group_by_session = bool(group_by_session)

    match_mode = str(match_mode or "auto").strip().lower()
    if match_mode not in _MATCH_MODES:
        return tool_error(
            "match_mode must be one of: auto, fts, substring",
            success=False,
        )

    role_list = _split_csv(role_filter)
    source_list = _split_csv(source_filter)

    def _normalize_substring_query(value: str) -> str:
        stripped = value.strip()
        if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
            return stripped[1:-1]
        return stripped

    fetch_limit = limit if not group_by_session else min(max(limit * 3, limit), 200)

    try:
        primary_query = _normalize_substring_query(query) if match_mode == "substring" else query
        raw_results = db.search_messages(
            query=primary_query,
            source_filter=source_list,
            role_filter=role_list,
            limit=fetch_limit,
            offset=0,
        )
        effective_match_mode = match_mode
        if match_mode == "auto" and not raw_results:
            fallback_query = _normalize_substring_query(query)
            raw_results = _search_messages_substring(
                db=db,
                query=fallback_query,
                source_filter=source_list,
                role_filter=role_list,
                limit=fetch_limit,
            )
            if raw_results:
                effective_match_mode = "substring"
        elif match_mode == "substring":
            raw_results = _search_messages_substring(
                db=db,
                query=_normalize_substring_query(query),
                source_filter=source_list,
                role_filter=role_list,
                limit=fetch_limit,
            )
            effective_match_mode = "substring"
    except (sqlite3.Error, Exception) as e:
        return tool_error(f"Exact session search failed: {e}", success=False)

    ranked_rows = sorted(raw_results or [], key=lambda row: _score_hit(row, query), reverse=True)

    results: List[Dict[str, Any]] = []
    seen_sessions = set()
    for row in ranked_rows:
        item = _format_exact_hit(row, effective_match_mode)
        if group_by_session:
            sid = item.get("session_id")
            if sid in seen_sessions:
                continue
            seen_sessions.add(sid)
        results.append(item)
        if len(results) >= limit:
            break

    return json.dumps(
        {
            "success": True,
            "query": query,
            "mode": "exact",
            "match_mode": effective_match_mode,
            "group_by_session": group_by_session,
            "results": results,
            "count": len(results),
            "message": "No exact matches found." if not results else None,
        },
        ensure_ascii=False,
    )


SESSION_SEARCH_EXACT_SCHEMA = {
    "name": "session_search_exact",
    "description": (
        "Cross-session exact recall for raw strings and message-level evidence. "
        "Use this for keys, hashes, UUIDs, long paths, long error strings, and quoted phrases "
        "when you need the original snippet, not a summary. Unlike session_search, this tool does "
        "NOT summarize with an LLM — it returns exact hits from the session database."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Exact string, phrase, path, key, hash, UUID, or search expression to recover from past sessions.",
            },
            "role_filter": {
                "type": "string",
                "description": "Optional roles to search, comma-separated. Example: 'user,assistant'.",
            },
            "source_filter": {
                "type": "string",
                "description": "Optional session sources to search, comma-separated. Example: 'feishu,cli'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max exact hits to return (default 10, max 50).",
                "default": 10,
            },
            "group_by_session": {
                "type": "boolean",
                "description": "When true (default), return the best hit per session. When false, return message-level hits.",
                "default": True,
            },
            "match_mode": {
                "type": "string",
                "description": "Search mode hint: 'auto' (default), 'fts', or 'substring'.",
                "enum": ["auto", "fts", "substring"],
                "default": "auto",
            },
        },
        "required": ["query"],
    },
}


registry.register(
    name="session_search_exact",
    toolset="session_search",
    schema=SESSION_SEARCH_EXACT_SCHEMA,
    handler=lambda args, **kw: session_search_exact(
        query=args.get("query") or "",
        role_filter=args.get("role_filter"),
        source_filter=args.get("source_filter"),
        limit=args.get("limit", 10),
        group_by_session=args.get("group_by_session", True),
        match_mode=args.get("match_mode", "auto"),
        db=kw.get("db"),
    ),
    check_fn=check_session_search_exact_requirements,
    emoji="🧷",
)
