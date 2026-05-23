#!/usr/bin/env python3
"""
Append one ``InboxRecord`` JSON line to the neuro-os research inbox.

The neuro-os repo lives in a separate codebase; this helper writes the
JSONL contract documented in
``neuro-os/agent/research/inbox.py::InboxRecord``. We deliberately keep
this script dependency-free (stdlib only) so the skill works on any
machine where Hermes is installed regardless of whether neuro-os is
also installed there.

Schema (mirrors the Pydantic model verbatim — keep in sync if the
neuro-os schema evolves):

  {
    "url": str (1..2000),
    "source_type": "youtube"|"blog"|"twitter"|"pdf"|"email-body"|"other",
    "title": str (1..400),
    "author": str (1..200, default "unknown"),
    "extracted_text": str (1..400_000),
    "extracted_at": ISO-8601 datetime with tz,
    "sender": str|null (max 200),
    "urge_tag": str|null (max 64),
    "topic_tags": list[str] (max 20)
  }

Usage:
    python append_inbox.py \\
      --url https://youtube.com/... \\
      --source-type youtube \\
      --title "Distribution is the moat" \\
      --text-file /tmp/transcript.txt \\
      [--author "Speaker Name"] \\
      [--sender paul@example.com] \\
      [--urge-tag novelty] \\
      [--topic-tag mlops] [--topic-tag agents] \\
      [--inbox-path ~/.neuro_os_research/inbox.jsonl]

Output: a JSON object on stdout summarising what was appended.
Exit codes: 0 success, 1 file/IO error, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


VALID_SOURCE_TYPES = (
    "youtube", "blog", "twitter", "pdf", "email-body", "other",
)
DEFAULT_INBOX_PATH = "~/.neuro_os_research/inbox.jsonl"

# Limits that mirror the Pydantic constraints in
# neuro-os/agent/research/inbox.py. If neuro-os tightens these, update
# here too — the downstream Pydantic validator will reject overflows
# anyway, but failing loud at the producer is friendlier.
_LIMITS = {
    "url":            (1, 2000),
    "source_type":    None,  # validated against VALID_SOURCE_TYPES
    "title":          (1, 400),
    "author":         (1, 200),
    "extracted_text": (1, 400_000),
    "sender":         (0, 200),
    "urge_tag":       (0, 64),
}


def _ensure_len(name: str, value: Optional[str]) -> Optional[str]:
    """Validate string length against the schema limits. Empty/None
    permissible for optional fields; required fields raise."""
    bounds = _LIMITS.get(name)
    if bounds is None:
        return value
    lo, hi = bounds
    if value is None:
        if lo == 0:
            return None
        raise ValueError(f"{name!r} is required")
    if not isinstance(value, str):
        raise ValueError(f"{name!r} must be a string")
    n = len(value)
    if n < lo:
        raise ValueError(f"{name!r} must be at least {lo} char(s)")
    if n > hi:
        raise ValueError(f"{name!r} must be at most {hi} chars (got {n})")
    return value


def build_record(
    *,
    url: str,
    source_type: str,
    title: str,
    extracted_text: str,
    author: str = "unknown",
    sender: Optional[str] = None,
    urge_tag: Optional[str] = None,
    topic_tags: Optional[list[str]] = None,
    extracted_at: Optional[datetime] = None,
) -> dict:
    """Build the InboxRecord dict. Raises ValueError on schema violation
    so producers see the bug at the boundary, not after writing a bad
    line to the queue."""
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            f"source_type must be one of {VALID_SOURCE_TYPES!r}, got {source_type!r}"
        )
    _ensure_len("url", url)
    _ensure_len("title", title)
    _ensure_len("author", author)
    _ensure_len("extracted_text", extracted_text)
    _ensure_len("sender", sender)
    _ensure_len("urge_tag", urge_tag)
    tags = list(topic_tags or [])
    if len(tags) > 20:
        raise ValueError(f"topic_tags must have ≤20 entries (got {len(tags)})")
    when = extracted_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return {
        "url": url,
        "source_type": source_type,
        "title": title,
        "author": author,
        "extracted_text": extracted_text,
        "extracted_at": when.isoformat(),
        "sender": sender,
        "urge_tag": urge_tag,
        "topic_tags": tags,
    }


def append(record: dict, inbox_path: Path) -> int:
    """Append the record as one JSON line. Returns the new 0-indexed
    line offset. Creates the parent directory as needed."""
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with inbox_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    with inbox_path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def _read_text_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"text file not found: {path}")
    body = path.read_text(encoding="utf-8", errors="replace")
    if not body.strip():
        raise ValueError(f"text file is empty: {path}")
    return body


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append one InboxRecord JSON line to the neuro-os research inbox.",
    )
    parser.add_argument("--url", required=True, help="Original source URL")
    parser.add_argument(
        "--source-type", required=True, choices=VALID_SOURCE_TYPES,
        help="Producer-attested source type",
    )
    parser.add_argument("--title", required=True, help="Source title (1..400 chars)")
    parser.add_argument(
        "--text-file", required=True,
        help="Path to a file containing the pre-extracted body text",
    )
    parser.add_argument("--author", default="unknown", help="Source author")
    parser.add_argument(
        "--sender", default=None,
        help="Optional sender identity (checked against inbox_allowlist.json by neuro-os)",
    )
    parser.add_argument(
        "--urge-tag", default=None,
        help="Optional active drift mode (novelty/social/frustration/fatigue/decision_fatigue/embodied)",
    )
    parser.add_argument(
        "--topic-tag", action="append", default=[], dest="topic_tags",
        help="Optional topic tag (may be repeated, max 20 total)",
    )
    parser.add_argument(
        "--inbox-path", default=DEFAULT_INBOX_PATH,
        help=f"Inbox JSONL path (default: {DEFAULT_INBOX_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        body = _read_text_file(Path(args.text_file).expanduser())
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        record = build_record(
            url=args.url,
            source_type=args.source_type,
            title=args.title,
            author=args.author,
            extracted_text=body,
            sender=args.sender,
            urge_tag=args.urge_tag,
            topic_tags=args.topic_tags,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        offset = append(record, Path(args.inbox_path).expanduser())
    except OSError as e:
        print(f"error: failed to write inbox: {e}", file=sys.stderr)
        return 1

    print(json.dumps({
        "appended_offset": offset,
        "inbox_path": str(Path(args.inbox_path).expanduser()),
        "source_type": record["source_type"],
        "url": record["url"],
        "byte_count": len(body.encode("utf-8")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
