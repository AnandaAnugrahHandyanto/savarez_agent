"""Shared helpers for the /notebooklm slash command."""

from __future__ import annotations

import re
from datetime import datetime


_KNOWN_SHARED_DIRS = (
    "macOS: /Users/myartings/Sync",
    "Linux: /home/myartings/Sync",
    r"Windows: C:\Users\myartings\Sync",
)


def notebooklm_usage() -> str:
    """Return concise usage for the NotebookLM LearnPack command."""
    return (
        "Usage: /notebooklm <topic|url|repo|kb topic|inbox name>\n"
        "Aliases: /nlm, /learnpack\n"
        "Examples:\n"
        "  /notebooklm vibe coding\n"
        "  /notebooklm kb agentic engineering\n"
        "  /notebooklm repo https://github.com/user/project\n"
        "  /notebooklm url https://example.com/article\n"
        "  /notebooklm inbox ai-memory"
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug[:80] or "learnpack"


def _route_hint(args: str) -> str:
    lowered = args.strip().lower()
    if lowered.startswith("kb "):
        return (
            "Treat this as a local knowledge-base topic. Search/read the local "
            "knowledge base first and use the kb-notebooklm-bundler Flow B "
            "(KB topic -> source selection -> bundle/manifest/prompts) when available."
        )
    if lowered.startswith("inbox "):
        return (
            "Treat this as a NotebookLM inbox request. Look under "
            "<shared-dir>/docs/notebooklm-inbox/<name>/ for source material."
        )
    if lowered.startswith("repo ") or "github.com/" in lowered:
        return (
            "Treat this as a repository source. Build or fetch a repo digest "
            "first, for example with Gitingest or an equivalent local digest."
        )
    if lowered.startswith("url ") or re.match(r"https?://", args.strip(), re.I):
        return "Treat this as a URL source. Fetch and convert it into clean source material first."
    return "Treat this as a topic. Search the local knowledge base first, then gather external sources if needed."


def build_notebooklm_learnpack_prompt(args: str) -> str:
    """Build the agent prompt for a NotebookLM LearnPack task.

    Empty args intentionally return ``""`` so callers can show
    :func:`notebooklm_usage` without starting an agent turn.
    """
    subject = (args or "").strip()
    if not subject:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    slug = _slugify(subject)
    shared_dirs = "\n".join(f"- {line}" for line in _KNOWN_SHARED_DIRS)
    route_hint = _route_hint(subject)

    return f"""Run the NotebookLM LearnPack workflow for: {subject}

Goal:
- Prepare a complete learning pack suitable for NotebookLM-style study and review.
- Produce a Research Handoff draft before any KB write or project execution.

Input routing:
- {route_hint}
- Preserve the user's original topic/source text exactly: {subject}

Save location:
- Use the platform shared directory when known:
{shared_dirs}
- Save outputs under: <shared-dir>/docs/notebooklm-learning/{today}-{slug}/
- Save the Research Handoff draft under: <shared-dir>/docs/handoffs/{today}-{slug}-research-handoff.md

Required outputs:
- Research Handoff draft with these sections:
  - Review Status
  - Question
  - Sources
  - Source Processing
  - NotebookLM Findings
  - Gemini / Agent Analysis
  - Decisions / Conclusions
  - Non-goals
  - Candidate KB Updates
  - Next Actions
  - Risks / Boundaries
- Study Guide
- Slide Deck
- Quiz
- Flashcards
- Mind Map
- concise summary
- candidate KB updates only when supported by sources

Knowledge-base policy:
- Do not directly overwrite long-term wiki pages from NotebookLM output.
- NotebookLM/Gemini output may only become candidate KB updates.
- Save artifacts and the Research Handoff first.
- Ask before formal wiki ingest unless the user explicitly asked 入库 or 写入 wiki.
- Formal KB ingest must go through the existing KB preflight/review/check/sync flow.

Automation boundaries:
- Do not run NotebookLM upload/generate unless explicitly needed and allowed in context.
- Do not start Happy/Codex project execution automatically from this task.
- Do not store Google auth state, cookies, tokens, or restricted source packs in repo/docs.

Verification:
- Report concrete artifact paths or URLs.
- Surface exact auth, quota, automation, browser, or source-access blockers.
"""
