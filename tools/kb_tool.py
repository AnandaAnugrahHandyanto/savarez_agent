#!/usr/bin/env python3
"""
Knowledge Base (Wiki) Tool — Search, read, and write to the persistent wiki.

The wiki at ~/hermes-kb/ is a compounding knowledge artifact. Unlike MEMORY.md
(hot, small, frozen snapshot) or the knowledge DB (structured, session-level),
the wiki holds comprehensive, interlinked markdown articles that grow over time.

Three-layer architecture:
  - raw/    — immutable ingested sources (articles, papers, data)
  - wiki/   — LLM-generated markdown (concepts, articles, _index.md, _tags.md)
  - schema  — AGENTS.md + _tags.md define structure and taxonomy

Operations:
  - search: full-text search across wiki pages
  - list:   browse the wiki index
  - read:   read a specific wiki page
  - file:   write a new concept or article back into the wiki (feedback loop)
  - log:    append to the chronological _log.md

Storage: ~/hermes-kb/ (git-versioned, Obsidian-compatible)
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

KB_HOME = Path(os.path.expanduser("~/hermes-kb"))
WIKI_DIR = KB_HOME / "wiki"
RAW_DIR = KB_HOME / "raw"
LOG_FILE = WIKI_DIR / "_log.md"
INDEX_FILE = WIKI_DIR / "_index.md"
TAGS_FILE = WIKI_DIR / "_tags.md"


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def check_kb_requirements() -> bool:
    """Return True if the wiki directory exists."""
    return WIKI_DIR.is_dir()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> Dict[str, str]:
    """Extract YAML frontmatter from markdown text."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _collect_wiki_files() -> List[Path]:
    """Collect all .md files in wiki/ excluding navigation files."""
    if not WIKI_DIR.is_dir():
        return []
    files = []
    for md_file in WIKI_DIR.rglob("*.md"):
        name = md_file.name
        if name.startswith("_"):
            continue
        files.append(md_file)
    return sorted(files)


def _truncate(text: str, max_chars: int = 2000) -> str:
    """Truncate text with indicator."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... (truncated, {len(text)} chars total)"


def _relative_path(path: Path) -> str:
    """Return path relative to KB_HOME for display."""
    try:
        return str(path.relative_to(KB_HOME))
    except ValueError:
        return str(path)


def _is_within_wiki(path: Path) -> bool:
    """Verify a resolved path is within the wiki directory (path traversal guard)."""
    try:
        resolved = path.resolve()
        return resolved.is_relative_to(WIKI_DIR.resolve())
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# Content scanning — delegates to consolidated guardrails module
# ---------------------------------------------------------------------------

try:
    from agent.guardrails import scan_content as _scan_content
except ImportError:
    _scan_content = None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _search(query: str, max_results: int = 10) -> str:
    """Full-text search across wiki markdown files."""
    files = _collect_wiki_files()
    if not files:
        return json.dumps({"results": [], "message": "Wiki is empty."})

    query_lower = query.lower()
    query_terms = query_lower.split()
    results = []

    for md_file in files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        content_lower = content.lower()
        score = 0
        for term in query_terms:
            count = content_lower.count(term)
            if count > 0:
                score += count

        if score == 0:
            continue

        frontmatter = _parse_frontmatter(content)
        title = frontmatter.get("title", md_file.stem.replace("_", " ").title())
        tags = frontmatter.get("tags", "")

        # Extract matching context (first match with surrounding lines)
        context_lines = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if any(term in line.lower() for term in query_terms):
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                snippet = "\n".join(lines[start:end])
                context_lines.append(snippet)
                if len(context_lines) >= 2:
                    break

        results.append({
            "file": _relative_path(md_file),
            "title": title,
            "tags": tags,
            "score": score,
            "context": "\n---\n".join(context_lines)[:500],
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:max_results]

    return json.dumps({
        "results": results,
        "total_files_searched": len(files),
        "matches": len(results),
    }, indent=2)


def _list_pages() -> str:
    """Return the wiki index content."""
    if not INDEX_FILE.is_file():
        return json.dumps({"error": "No _index.md found in wiki."})
    content = INDEX_FILE.read_text(encoding="utf-8")
    return content


def _read_page(page: str) -> str:
    """Read a specific wiki page by name or relative path."""
    # Try exact path first
    candidates = [
        WIKI_DIR / page,
        WIKI_DIR / f"{page}.md",
        WIKI_DIR / "concepts" / f"{page}.md",
        WIKI_DIR / "articles" / f"{page}.md",
    ]

    for candidate in candidates:
        if not _is_within_wiki(candidate):
            continue
        if candidate.resolve().is_file():
            content = candidate.read_text(encoding="utf-8")
            return _truncate(content, 4000)

    # Fuzzy match: search for files containing the query in their name
    page_lower = page.lower().replace(" ", "_")
    for md_file in _collect_wiki_files():
        if page_lower in md_file.stem.lower():
            content = md_file.read_text(encoding="utf-8")
            return _truncate(content, 4000)

    return json.dumps({"error": f"Page not found: {page}"})


def _file_page(
    title: str,
    content: str,
    page_type: str = "concept",
    tags: str = "",
) -> str:
    """File a new concept or article into the wiki. Creates the markdown file
    with frontmatter and appends to _log.md and _index.md."""

    if page_type not in ("concept", "article"):
        return json.dumps({"error": "page_type must be 'concept' or 'article'"})

    # Content guardrails
    if _scan_content:
        for field_name, field_value in [("title", title), ("content", content)]:
            violation = _scan_content(field_value)
            if violation:
                return json.dumps({"error": f"Content blocked ({field_name}): {violation}"})

    # Sanitize filename
    slug = re.sub(r"[^a-z0-9_]", "_", title.lower().strip())
    slug = re.sub(r"_+", "_", slug).strip("_")

    subdir = "concepts" if page_type == "concept" else "articles"
    target_dir = WIKI_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{slug}.md"

    ts = datetime.now()
    now = ts.strftime("%Y-%m-%d")

    # Build frontmatter
    frontmatter = f"""---
title: "{title}"
tags: {tags if tags else "[]"}
updated: {now}
source: "agent-feedback-loop"
---

"""
    full_content = frontmatter + content

    # Write or append
    if target_file.exists():
        existing = target_file.read_text(encoding="utf-8")
        # Append new content after existing
        updated = existing.rstrip() + "\n\n---\n\n" + f"## Update ({now})\n\n" + content
        target_file.write_text(updated, encoding="utf-8")
        action = "UPDATED"
    else:
        target_file.write_text(full_content, encoding="utf-8")
        action = "CREATED"

    # Append to _log.md
    _append_log(f"{action}: {subdir}/{slug}.md — {title}")

    # Update _index.md if new file
    if action == "CREATED":
        _update_index(slug, title, tags, now, page_type)

    return json.dumps({
        "success": True,
        "action": action.lower(),
        "file": f"wiki/{subdir}/{slug}.md",
        "title": title,
    })


def _append_log(message: str) -> str:
    """Append a timestamped entry to _log.md."""
    ts = datetime.now()
    now = ts.strftime("%Y-%m-%d %H:%M")
    today = ts.strftime("%Y-%m-%d")
    entry = f"[{now}] {message}\n"

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not LOG_FILE.exists():
        header = f"---\ntitle: Knowledge Base Log\nupdated: {today}\n---\n\n# Knowledge Base Log\n\nChronological record of all wiki changes.\n\n"
        LOG_FILE.write_text(header + entry, encoding="utf-8")
    else:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    return json.dumps({"success": True, "entry": entry.strip()})


def _update_index(slug: str, title: str, tags: str, date: str, page_type: str) -> None:
    """Add a new entry to _index.md under the appropriate section."""
    if not INDEX_FILE.is_file():
        return

    content = INDEX_FILE.read_text(encoding="utf-8")
    subdir = "concepts" if page_type == "concept" else "articles"
    section_header = "## Concepts" if page_type == "concept" else "## Articles"

    new_row = f"| [{slug}]({subdir}/{slug}.md) | {title} | {tags} | {date} |"

    # Find the section and its table, insert before the empty line after the table
    lines = content.splitlines()
    insert_at = None
    in_section = False
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            in_section = True
            continue
        if in_section and line.startswith("##"):
            insert_at = i
            break
        if in_section and line.strip() == "":
            # Could be end of table
            if i > 0 and lines[i - 1].startswith("|"):
                insert_at = i
                break

    if insert_at is not None:
        lines.insert(insert_at, new_row)
        has_trailing_newline = content.endswith("\n")
        result = "\n".join(lines)
        if has_trailing_newline and not result.endswith("\n"):
            result += "\n"
        INDEX_FILE.write_text(result, encoding="utf-8")
    else:
        logger.warning("Could not find section '%s' in _index.md to insert new entry", section_header)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def kb_tool(
    action: str,
    query: str = None,
    page: str = None,
    title: str = None,
    content: str = None,
    page_type: str = "concept",
    tags: str = "",
    message: str = None,
    max_results: int = 10,
) -> str:
    """Single entry point for the KB wiki tool."""

    if action == "search":
        if not query:
            return json.dumps({"error": "query is required for search action"})
        return _search(query, max_results)

    elif action == "list":
        return _list_pages()

    elif action == "read":
        if not page:
            return json.dumps({"error": "page is required for read action"})
        return _read_page(page)

    elif action == "file":
        if not title or not content:
            return json.dumps({"error": "title and content are required for file action"})
        return _file_page(title, content, page_type, tags)

    elif action == "log":
        if not message:
            return json.dumps({"error": "message is required for log action"})
        return _append_log(message)

    else:
        return json.dumps({
            "error": f"Unknown action '{action}'. Use: search, list, read, file, log"
        })


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

KB_SCHEMA = {
    "name": "kb",
    "description": (
        "Search, read, and write to the persistent knowledge base wiki at ~/hermes-kb/. "
        "The wiki is a compounding knowledge artifact — concepts and articles that grow "
        "richer over time through ingestion, compilation, and feedback.\n\n"
        "Actions:\n"
        "- search: Full-text search across wiki pages (query required)\n"
        "- list: Browse the wiki index (shows all concepts, articles, drafts)\n"
        "- read: Read a specific wiki page by name or path (page required)\n"
        "- file: Write a new concept or article into the wiki (title + content required, "
        "use this when you synthesize valuable knowledge worth preserving)\n"
        "- log: Append a timestamped entry to the knowledge evolution log\n\n"
        "Use 'file' to feed valuable query results back into the wiki — this is how "
        "knowledge compounds. Prefer updating existing pages over creating new ones."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "list", "read", "file", "log"],
                "description": "The action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action). Searches across all wiki content.",
            },
            "page": {
                "type": "string",
                "description": "Page name or relative path (for read action). Examples: 'macos_mastery_assistant', 'articles/competitive_research'.",
            },
            "title": {
                "type": "string",
                "description": "Title for new page (for file action).",
            },
            "content": {
                "type": "string",
                "description": "Markdown content for new page (for file action).",
            },
            "page_type": {
                "type": "string",
                "enum": ["concept", "article"],
                "description": "Type of page to create (for file action). Concepts are atomic notes, articles are synthesis pieces.",
            },
            "tags": {
                "type": "string",
                "description": "Comma-separated tags (for file action). Use controlled taxonomy from _tags.md.",
            },
            "message": {
                "type": "string",
                "description": "Log message (for log action).",
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

from tools.registry import registry

registry.register(
    name="kb",
    toolset="knowledge",
    schema=KB_SCHEMA,
    handler=lambda args, **kw: kb_tool(
        action=args.get("action", ""),
        query=args.get("query"),
        page=args.get("page"),
        title=args.get("title"),
        content=args.get("content"),
        page_type=args.get("page_type", "concept"),
        tags=args.get("tags", ""),
        message=args.get("message"),
        max_results=args.get("max_results", 10),
    ),
    check_fn=check_kb_requirements,
    emoji="📖",
    description="Search, read, and write to the persistent wiki knowledge base",
    mutates=True,
    requires_confirmation=False,
)
