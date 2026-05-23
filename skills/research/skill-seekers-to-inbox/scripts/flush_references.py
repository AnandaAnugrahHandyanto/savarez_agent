#!/usr/bin/env python3
"""
Convert a ``skill-seekers create`` output directory's ``references/*.md``
files into one ``InboxRecord`` JSON line each, appended to the neuro-os
research inbox at ``~/.neuro_os_research/inbox.jsonl``.

Composes with the ``url-to-inbox`` skill — this script does NOT
re-implement the InboxRecord schema or the append logic; it imports
``append_inbox`` from the sibling skill so there's exactly one
producer in the codebase.

Skill-seekers writes:

    <output_dir>/
      SKILL.md
      references/
        index.md
        section_01.md
        section_02.md
        ...

Each section file usually has YAML front-matter with at least
``source_url`` and ``title``; if it doesn't (legacy versions of
skill-seekers), we fall back to filename-derived defaults.

Usage:
    python flush_references.py \\
      --references-dir <PATH> \\
      --base-url https://docs.example.com \\
      [--sender paul@example.com] \\
      [--urge-tag novelty] \\
      [--inbox-path ~/.neuro_os_research/inbox.jsonl] \\
      [--source-type blog]    # default 'blog'; passed to InboxRecord
      [--dry-run]             # parse + validate but do not append
      [--max-records N]       # cap (useful for first-time tests)

Output: a JSON summary {records_attempted, records_appended, records_skipped, errors}.
Exit codes: 0 success (even with some per-file skips), 1 IO/parse error, 2 bad args.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import the producer's schema + append logic from the sibling skill —
# both single-source-of-truth and zero-duplication. The sibling lives at
# ../../url-to-inbox/scripts/append_inbox.py.
SIBLING = Path(__file__).resolve().parents[2] / "url-to-inbox" / "scripts"
sys.path.insert(0, str(SIBLING))
try:
    import append_inbox  # type: ignore
except ImportError as e:  # pragma: no cover — defensive
    print(
        f"error: url-to-inbox sibling skill not found at {SIBLING}: {e}",
        file=sys.stderr,
    )
    sys.exit(1)


_FRONT_MATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*\n",
    re.DOTALL,
)


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Lightweight YAML-ish front-matter parser (no pyyaml dep). Same
    shape as the neuro-os ingest pipeline's parser so behaviour matches
    end-to-end."""
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        return ({}, text)
    block = m.group("body")
    body = text[m.end():]
    meta: dict = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return (meta, body)


def _derive_url(meta: dict, base_url: Optional[str], filename: str) -> str:
    """Pick a URL for the InboxRecord — front-matter wins; fall back to
    ``base_url + path`` shape; final fallback is a synthetic one so the
    record still passes neuro-os's Pydantic validation."""
    for key in ("source_url", "url", "permalink", "canonical"):
        v = meta.get(key)
        if v:
            return str(v)
    if base_url:
        slug = Path(filename).stem
        return base_url.rstrip("/") + "/" + slug
    return f"skill-seekers://{filename}"


def _derive_title(meta: dict, filename: str, body: str) -> str:
    """Title resolution: front-matter > first markdown heading > filename."""
    for key in ("title", "name"):
        v = meta.get(key)
        if v:
            return str(v)[:400]
    # First Markdown H1 (`# Title`) line:
    for line in body.splitlines()[:20]:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:400] or filename
    return Path(filename).stem.replace("-", " ").replace("_", " ").strip().title()[:400] or filename


def flush(
    *,
    references_dir: Path,
    base_url: Optional[str],
    inbox_path: Path,
    source_type: str = "blog",
    sender: Optional[str] = None,
    urge_tag: Optional[str] = None,
    topic_tags: Optional[list[str]] = None,
    dry_run: bool = False,
    max_records: Optional[int] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Walk ``references_dir`` for .md files, build InboxRecords, append.

    Returns a summary dict (machine-readable). ``index.md`` is always
    skipped — it's a navigation file, not source content.
    """
    if not references_dir.exists():
        raise FileNotFoundError(f"references dir not found: {references_dir}")
    if not references_dir.is_dir():
        raise NotADirectoryError(f"not a directory: {references_dir}")

    when = now or datetime.now(timezone.utc)

    files = sorted(p for p in references_dir.iterdir()
                   if p.is_file() and p.suffix.lower() == ".md"
                   and p.name.lower() != "index.md")
    if max_records is not None:
        files = files[:max_records]

    records_appended = 0
    records_skipped: list[dict] = []
    errors: list[dict] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            errors.append({"file": path.name, "error": f"read: {e}"})
            continue
        meta, body = _parse_front_matter(text)
        body_stripped = body.strip()
        if not body_stripped:
            records_skipped.append({"file": path.name, "reason": "empty body"})
            continue

        url = _derive_url(meta, base_url, path.name)
        title = _derive_title(meta, path.name, body_stripped)
        author = (meta.get("author") or "skill-seekers")[:200]

        try:
            record = append_inbox.build_record(
                url=url,
                source_type=source_type,
                title=title,
                extracted_text=body_stripped,
                author=author,
                sender=sender,
                urge_tag=urge_tag,
                topic_tags=list(topic_tags or []),
                extracted_at=when,
            )
        except ValueError as e:
            records_skipped.append({"file": path.name, "reason": f"schema: {e}"})
            continue

        if dry_run:
            records_appended += 1  # count what WOULD have been appended
            continue

        try:
            append_inbox.append(record, inbox_path)
            records_appended += 1
        except OSError as e:
            errors.append({"file": path.name, "error": f"write: {e}"})

    return {
        "references_dir": str(references_dir),
        "inbox_path": str(inbox_path),
        "records_attempted": len(files),
        "records_appended": records_appended,
        "records_skipped": records_skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Flush skill-seekers references/*.md into the neuro-os inbox. "
            "Composes with the url-to-inbox sibling skill."
        ),
    )
    parser.add_argument(
        "--references-dir", required=True,
        help="Path to <skill-seekers-output>/references/ (contains *.md files)",
    )
    parser.add_argument(
        "--base-url", default=None,
        help="Base URL used when individual files lack front-matter URLs",
    )
    parser.add_argument(
        "--inbox-path", default="~/.neuro_os_research/inbox.jsonl",
        help="Inbox JSONL path (default: ~/.neuro_os_research/inbox.jsonl)",
    )
    parser.add_argument(
        "--source-type", default="blog",
        choices=["youtube", "blog", "twitter", "pdf", "email-body", "other"],
        help="source_type to set on every record (default 'blog')",
    )
    parser.add_argument(
        "--sender", default=None,
        help="Optional sender identity (checked against inbox_allowlist.json)",
    )
    parser.add_argument(
        "--urge-tag", default=None,
        help="Optional founder-loop drift mode tag",
    )
    parser.add_argument(
        "--topic-tag", action="append", default=[], dest="topic_tags",
        help="Optional topic tag (may be repeated)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse + validate but do not append")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Cap on records processed (useful for first-time tests)")
    args = parser.parse_args(argv)

    try:
        summary = flush(
            references_dir=Path(args.references_dir).expanduser(),
            base_url=args.base_url,
            inbox_path=Path(args.inbox_path).expanduser(),
            source_type=args.source_type,
            sender=args.sender,
            urge_tag=args.urge_tag,
            topic_tags=args.topic_tags,
            dry_run=args.dry_run,
            max_records=args.max_records,
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
