"""Goblin quote extraction from Hermes session history.

This is intentionally tiny and boring: scan stored messages for the word
"goblin", extract the matching sentence-ish chunks, and append new finds to a
profile-local Markdown log. No LLM needed; the goblin trap is regex-powered.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

from hermes_constants import get_hermes_home

_GOBLIN_RE = re.compile(r"\bgoblins?\b", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[^.!?\n]*\bgoblins?\b[^.!?\n]*(?:[.!?]|$)", re.IGNORECASE)
_FINGERPRINT_RE = re.compile(r"<!--\s*goblin:([0-9a-f]{16,64})\s*-->")


def _content_to_text(content: Any) -> str:
    """Flatten stored message content into searchable text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bytes)):
        return str(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif item.get("type") == "input_text" and isinstance(item.get("content"), str):
                    parts.append(item["content"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    if isinstance(content, dict):
        text = content.get("text")
        return text if isinstance(text, str) else str(content)
    return str(content)


def _extract_goblin_quotes(text: str) -> list[str]:
    """Return sentence-ish chunks containing goblin/goblins, preserving order."""
    if not _GOBLIN_RE.search(text):
        return []
    quotes: list[str] = []
    seen: set[str] = set()
    for match in _SENTENCE_RE.finditer(text):
        quote = " ".join(match.group(0).strip().split())
        if quote and quote not in seen:
            seen.add(quote)
            quotes.append(quote)
    if quotes:
        return quotes
    # Fallback for weird punctuation/control text: log the matching line.
    for line in text.splitlines() or [text]:
        if _GOBLIN_RE.search(line):
            quote = " ".join(line.strip().split())
            if quote and quote not in seen:
                seen.add(quote)
                quotes.append(quote)
    return quotes


def iter_goblin_quotes(db, source: Optional[str] = None, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
    """Yield goblin quote records from a ``SessionDB``.

    Only user/assistant messages are scanned. Tool output can contain arbitrary
    web/code junk, and this log is for conversational goblin lore, not every
    npm package that accidentally summons a cave creature.
    """
    params: list[Any] = []
    source_sql = ""
    if source:
        source_sql = " AND s.source = ?"
        params.append(source)
    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT ?"
        params.append(max(0, int(limit)))

    # Do the goblin match in Python instead of SQL LIKE. Multimodal messages are
    # stored with a NUL-prefixed JSON sentinel; SQLite LIKE treats embedded NULs
    # like a tiny string guillotine. Python doesn't care, because it has manners.
    query = f"""
        SELECT
            m.id AS message_id,
            m.session_id,
            m.role,
            m.content,
            s.source,
            s.title
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE m.role IN ('user', 'assistant')
          {source_sql}
        ORDER BY m.id ASC
        {limit_sql}
    """

    with db._lock:  # SessionDB exposes no arbitrary query helper; keep reads locked.
        rows = [dict(row) for row in db._conn.execute(query, params).fetchall()]

    for row in rows:
        text = _content_to_text(db._decode_content(row.get("content")))
        for quote in _extract_goblin_quotes(text):
            yield {
                "session_id": row["session_id"],
                "message_id": row["message_id"],
                "role": row["role"],
                "source": row["source"],
                "title": row.get("title"),
                "quote": quote,
            }


def _fingerprint(record: Dict[str, Any]) -> str:
    raw = f"{record['session_id']}\0{record['message_id']}\0{record['quote']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _existing_fingerprints(log_path: Path) -> set[str]:
    if not log_path.exists():
        return set()
    text = log_path.read_text(encoding="utf-8")
    return set(_FINGERPRINT_RE.findall(text))


def _format_entry(record: Dict[str, Any], fingerprint: str) -> str:
    title = record.get("title") or "untitled"
    return (
        f"<!-- goblin:{fingerprint} -->\n"
        f"- **{record['role']}** — {record['quote']}\n"
        f"  - session: `{record['session_id']}`; message: `{record['message_id']}`; "
        f"source: `{record['source']}`; title: {title}\n"
    )


def append_goblin_log(
    db,
    log_path: Optional[Path | str] = None,
    source: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Append newly discovered goblin quotes to a Markdown log.

    Returns a small summary dict so CLI/cron callers can report what changed.
    """
    path = Path(log_path) if log_path is not None else get_hermes_home() / "goblin-quotes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_fingerprints(path)
    entries: list[str] = []
    scanned = 0

    for record in iter_goblin_quotes(db, source=source, limit=limit):
        scanned += 1
        fp = _fingerprint(record)
        if fp in existing:
            continue
        existing.add(fp)
        entries.append(_format_entry(record, fp))

    if not path.exists():
        path.write_text("# Goblin Quote Log\n\n", encoding="utf-8")
    if entries:
        with path.open("a", encoding="utf-8") as f:
            f.write("".join(entries))

    return {"path": str(path), "scanned": scanned, "added": len(entries)}
