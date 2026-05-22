#!/usr/bin/env python3
"""
Vault Tool Module - Development Ideas Vault Search

Provides search and Q&A over a local vault of development ideas stored as
Markdown files and JSONL entries. No LLM is involved — results are purely
extractive (substring scoring over local files).

Vault layout (default: HERMES_HOME/data/development_ideas/):
  README.md          — top-level description / index
  ideas.jsonl        — one JSON object per line (each may have 'title', 'body', 'tags', ...)
  sources/           — optional *.md files with reference material
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vault root helpers
# ---------------------------------------------------------------------------


def _default_vault_root() -> Path:
    """Return the default vault root directory."""
    return get_hermes_home() / "data" / "development_ideas"


def _resolve_vault_root(path: str | None) -> tuple[Path, str | None]:
    """Resolve the effective vault root from the optional *path* argument.

    Returns ``(resolved_path, error_message_or_None)``.  If error is set the
    caller should return a JSON error to the user immediately.

    Rules
    -----
    * ``path=None`` → use the default vault root (no validation).
    * Absolute path → expand user home (``~``), require the result is an
      existing directory.
    * Relative path → resolve against the default vault root, block ``..``
      components (path-traversal guard), require the result is an existing
      directory.
    """
    if path is None:
        return _default_vault_root(), None

    p = Path(path)

    if p.is_absolute():
        resolved = p.expanduser().resolve()
        if not resolved.exists():
            return resolved, f"Path does not exist: {path}"
        if not resolved.is_dir():
            return resolved, f"Path is not a directory: {path}"
        return resolved, None

    # Relative path — anchor to default vault root, block traversal.
    if ".." in p.parts:
        return _default_vault_root(), f"Relative path traversal is not allowed: {path}"

    default_root = _default_vault_root()
    resolved = (default_root / p).resolve()
    # Ensure it stays inside the default vault root.
    try:
        resolved.relative_to(default_root.resolve())
    except ValueError:
        return default_root, f"Relative path escapes vault root: {path}"

    if not resolved.exists():
        return resolved, f"Path does not exist (relative to vault root): {path}"
    if not resolved.is_dir():
        return resolved, f"Path is not a directory: {path}"

    return resolved, None


# ---------------------------------------------------------------------------
# Scoring / search helpers
# ---------------------------------------------------------------------------


def _score_text(text: str, query: str, terms: list[str]) -> float:
    """Return a simple relevance score for *text* against the query."""
    lower = text.lower()
    score = 0.0
    # Exact query match (higher weight)
    if query.lower() in lower:
        score += 5.0
    # Per-term frequency
    for term in terms:
        score += lower.count(term)
    return score


def _snippet(line: str, max_len: int = 200) -> str:
    """Return a trimmed snippet of *line*."""
    stripped = line.strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[:max_len] + "…"


def _search_markdown(
    file_path: Path,
    query: str,
    terms: list[str],
    file_type: str,
) -> list[dict[str, Any]]:
    """Return per-line matches from a Markdown file."""
    matches: list[dict[str, Any]] = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return matches

    for lineno, line in enumerate(text.splitlines(), start=1):
        score = _score_text(line, query, terms)
        if score > 0:
            matches.append(
                {
                    "path": str(file_path),
                    "type": file_type,
                    "line": lineno,
                    "snippet": _snippet(line),
                    "score": score,
                }
            )
    return matches


def _search_jsonl(
    file_path: Path,
    query: str,
    terms: list[str],
) -> list[dict[str, Any]]:
    """Return per-entry matches from an ideas.jsonl file."""
    matches: list[dict[str, Any]] = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return matches

    for lineno, raw in enumerate(lines, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            obj = {}

        # Collect searchable text: all string values in the object.
        text_parts: list[str] = []
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str):
                    text_parts.append(v)
                elif isinstance(v, list):
                    text_parts.extend(str(i) for i in v if isinstance(i, str))
        else:
            text_parts.append(str(obj))

        combined = " ".join(text_parts)
        score = _score_text(combined, query, terms)
        if score > 0:
            # Build a human-readable snippet from the most relevant fields.
            title = obj.get("title", "") if isinstance(obj, dict) else ""
            body = obj.get("body", obj.get("description", combined)) if isinstance(obj, dict) else combined
            snip = f"{title}: {body}" if title else body
            matches.append(
                {
                    "path": str(file_path),
                    "type": "jsonl",
                    "line": lineno,
                    "snippet": _snippet(snip),
                    "score": score,
                }
            )
    return matches


def _run_search(
    query: str,
    include_sources: bool,
    vault_root: Path,
) -> list[dict[str, Any]]:
    """Run the full search and return an unsorted-then-sorted match list."""
    terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
    all_matches: list[dict[str, Any]] = []

    # 1. README.md
    readme = vault_root / "README.md"
    if readme.is_file():
        all_matches.extend(_search_markdown(readme, query, terms, "readme"))

    # 2. ideas.jsonl
    ideas = vault_root / "ideas.jsonl"
    if ideas.is_file():
        all_matches.extend(_search_jsonl(ideas, query, terms))

    # 3. sources/*.md
    if include_sources:
        sources_dir = vault_root / "sources"
        if sources_dir.is_dir():
            for md_file in sorted(sources_dir.glob("*.md")):
                all_matches.extend(_search_markdown(md_file, query, terms, "source"))

    # Sort descending by score, stable (preserves file order for ties).
    all_matches.sort(key=lambda m: m["score"], reverse=True)
    return all_matches


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def vault_search(
    query: str,
    limit: int = 10,
    include_sources: bool = True,
    path: str | None = None,
) -> str:
    """Search the development-ideas vault and return a JSON string.

    Parameters
    ----------
    query:
        Free-text search query.  Terms are split on whitespace and matched
        case-insensitively against vault content.
    limit:
        Maximum number of matches to return.
    include_sources:
        Whether to search ``sources/*.md`` files in addition to README.md and
        ideas.jsonl.
    path:
        Optional override for the vault root directory.  Absolute paths must
        exist and be a directory.  Relative paths are resolved against the
        default vault root and must not escape it (no ``..`` components).
    """
    vault_root, err = _resolve_vault_root(path)
    if err:
        return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    if not query or not query.strip():
        return json.dumps(
            {"success": False, "error": "query must not be empty"},
            ensure_ascii=False,
        )

    if limit < 1:
        return json.dumps(
            {"success": False, "error": "limit must be >= 1"},
            ensure_ascii=False,
        )

    all_matches = _run_search(query, include_sources, vault_root)
    total = len(all_matches)
    truncated = total > limit
    returned = all_matches[:limit]

    return json.dumps(
        {
            "success": True,
            "query": query,
            "root": str(vault_root),
            "matches": returned,
            "total": total,
            "truncated": truncated,
        },
        ensure_ascii=False,
        indent=None,
    )


def ask_vault(
    question: str,
    limit: int = 8,
    path: str | None = None,
) -> str:
    """Answer a question about the vault using extractive search (no LLM).

    Reuses the same scoring logic as ``vault_search`` and surfaces the top
    matching snippets as the "answer".  This is intentionally lightweight:
    no model call is made; the returned ``answer_summary`` explains this.

    Parameters
    ----------
    question:
        Natural-language question about the vault content.
    limit:
        Number of top matching snippets to include in the context.
    path:
        Optional override for the vault root directory (same rules as
        ``vault_search``).
    """
    vault_root, err = _resolve_vault_root(path)
    if err:
        return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    if not question or not question.strip():
        return json.dumps(
            {"success": False, "error": "question must not be empty"},
            ensure_ascii=False,
        )

    if limit < 1:
        return json.dumps(
            {"success": False, "error": "limit must be >= 1"},
            ensure_ascii=False,
        )

    all_matches = _run_search(question, include_sources=True, vault_root=vault_root)
    top = all_matches[:limit]

    # Collect unique source files for attribution.
    seen_sources: list[str] = []
    seen_set: set[str] = set()
    for m in top:
        if m["path"] not in seen_set:
            seen_set.add(m["path"])
            seen_sources.append(m["path"])

    candidate_context = [
        {"source": m["path"], "line": m["line"], "text": m["snippet"], "score": m["score"]}
        for m in top
    ]

    if top:
        answer_summary = (
            f"Based on {len(top)} local matching snippet(s) from the vault "
            f"(extractive search — no LLM inference): the top result is: "
            f'"{top[0]["snippet"]}"'
        )
    else:
        answer_summary = (
            "No matching content found in the vault for this question "
            "(extractive search — no LLM inference)."
        )

    return json.dumps(
        {
            "success": True,
            "question": question,
            "mode": "extractive",
            "answer_summary": answer_summary,
            "candidate_context": candidate_context,
            "sources": seen_sources,
        },
        ensure_ascii=False,
        indent=None,
    )


# ---------------------------------------------------------------------------
# JSON schemas
# ---------------------------------------------------------------------------

VAULT_SEARCH_SCHEMA = {
    "name": "vault_search",
    "description": (
        "Search the local development-ideas vault for content matching a query. "
        "Searches README.md, ideas.jsonl, and optionally sources/*.md using "
        "case-insensitive substring scoring. Returns ranked snippets with file "
        "paths, line numbers, and relevance scores. Useful for quickly locating "
        "ideas, notes, or references stored in the vault."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Terms are matched case-insensitively.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 10).",
                "default": 10,
                "minimum": 1,
            },
            "include_sources": {
                "type": "boolean",
                "description": (
                    "Include sources/*.md files in the search (default true). "
                    "Set to false to search only README.md and ideas.jsonl."
                ),
                "default": True,
            },
            "path": {
                "type": "string",
                "description": (
                    "Optional override for the vault root directory. "
                    "Absolute paths must exist and be a directory. "
                    "Relative paths are resolved under the default vault root "
                    "and must not contain '..' components."
                ),
            },
        },
        "required": ["query"],
    },
}

ASK_VAULT_SCHEMA = {
    "name": "ask_vault",
    "description": (
        "Answer a question about the local development-ideas vault using "
        "extractive search (no LLM). Returns the top matching snippets and a "
        "brief answer summary based purely on local content. Useful for "
        "quick lookups when you want the raw context rather than a synthesised "
        "answer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural-language question about the vault content.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of top snippets to include in context (default 8).",
                "default": 8,
                "minimum": 1,
            },
            "path": {
                "type": "string",
                "description": (
                    "Optional override for the vault root directory. "
                    "Same rules as vault_search: absolute paths must exist; "
                    "relative paths resolve under the default vault root "
                    "without '..' traversal."
                ),
            },
        },
        "required": ["question"],
    },
}


# ---------------------------------------------------------------------------
# check_fn
# ---------------------------------------------------------------------------


def _check_vault_available() -> bool:
    """Return True if the default vault root directory exists."""
    return _default_vault_root().exists()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

registry.register(
    name="vault_search",
    toolset="vault",
    schema=VAULT_SEARCH_SCHEMA,
    handler=lambda args, **kw: vault_search(
        query=args.get("query", ""),
        limit=int(args.get("limit", 10)),
        include_sources=bool(args.get("include_sources", True)),
        path=args.get("path"),
    ),
    check_fn=_check_vault_available,
    emoji="🗄️",
    description="Search the local development-ideas vault",
)

registry.register(
    name="ask_vault",
    toolset="vault",
    schema=ASK_VAULT_SCHEMA,
    handler=lambda args, **kw: ask_vault(
        question=args.get("question", ""),
        limit=int(args.get("limit", 8)),
        path=args.get("path"),
    ),
    check_fn=_check_vault_available,
    emoji="💡",
    description="Answer questions about the vault using extractive search",
)
