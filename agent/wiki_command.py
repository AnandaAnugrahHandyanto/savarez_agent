#!/usr/bin/env python3
"""Shared helpers for direct /wiki command flows in CLI and gateway."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from agent.wiki_paths import resolve_llm_wiki_path, resolve_obsidian_vault_path
from tools.kb_tool import kb_tool


def _count_markdown_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*.md"))


def _wiki_page_dirs(wiki_path: Path) -> Dict[str, Path]:
    page_dirs = {
        "entities": wiki_path / "entities",
        "concepts": wiki_path / "concepts",
        "comparisons": wiki_path / "comparisons",
        "queries": wiki_path / "queries",
        "articles": wiki_path / "articles",
    }
    if not any(path.exists() for path in page_dirs.values()):
        legacy_root = wiki_path / "wiki"
        legacy_dirs = {name: legacy_root / name for name in page_dirs}
        if any(path.exists() for path in legacy_dirs.values()):
            return legacy_dirs
    return page_dirs


def get_wiki_status() -> Dict[str, object]:
    wiki_path = resolve_llm_wiki_path()
    vault_path = resolve_obsidian_vault_path()
    page_dirs = _wiki_page_dirs(wiki_path)
    raw_root = wiki_path / "raw"
    return {
        "wiki_path": str(wiki_path),
        "vault_path": str(vault_path) if vault_path else None,
        "exists": wiki_path.exists(),
        "initialized": (wiki_path / "SCHEMA.md").exists()
        or (wiki_path / "wiki" / "_index.md").exists()
        or (wiki_path / "index.md").exists(),
        "pages": {name: _count_markdown_files(path) for name, path in page_dirs.items()},
        "raw_sources": _count_markdown_files(raw_root),
    }


def format_wiki_status() -> str:
    status = get_wiki_status()
    lines = [
        "Wiki Status",
        f"Path: {status['wiki_path']}",
        f"Obsidian Vault: {status['vault_path'] or 'Not configured'}",
        f"Exists: {'yes' if status['exists'] else 'no'}",
        f"Initialized: {'yes' if status['initialized'] else 'no'}",
        "",
        "Page Counts:",
    ]
    for name, count in status["pages"].items():
        lines.append(f"- {name}: {count}")
    lines.append(f"- raw sources: {status['raw_sources']}")
    return "\n".join(lines)


def _recent_wiki_pages(wiki_path: Path, limit: int = 5) -> List[str]:
    page_files: List[Path] = []
    for page_dir in _wiki_page_dirs(wiki_path).values():
        if not page_dir.exists():
            continue
        page_files.extend(path for path in page_dir.rglob("*.md") if path.is_file())

    recent = sorted(page_files, key=lambda path: path.stat().st_mtime, reverse=True)
    return [str(path.relative_to(wiki_path)) for path in recent[:limit]]


def format_wiki_map() -> str:
    wiki_path = resolve_llm_wiki_path()
    status = get_wiki_status()
    last_ingest = _load_last_ingest(wiki_path)
    recent_pages = _recent_wiki_pages(wiki_path)

    lines = [
        "Wiki Map",
        f"Path: {status['wiki_path']}",
        f"Initialized: {'yes' if status['initialized'] else 'no'}",
        "",
        "Graph Summary:",
    ]
    total_pages = 0
    for name, count in status["pages"].items():
        total_pages += int(count)
        lines.append(f"- {name}: {count}")
    lines.append(f"- total pages: {total_pages}")
    lines.append(f"- raw sources: {status['raw_sources']}")

    lines.extend(["", "Recent Pages:"])
    if recent_pages:
        for page in recent_pages:
            lines.append(f"- {page}")
    else:
        lines.append("- No wiki pages yet.")

    lines.extend(["", "Latest Ingest:"])
    if last_ingest:
        lines.append(f"- source: {last_ingest.get('source_label', 'unknown')}")
        lines.append(f"- article: {last_ingest.get('article_file', 'unknown')}")
        for item in (last_ingest.get("follow_ups") or [])[:3]:
            lines.append(f"- next: {item}")
    else:
        lines.append("- No ingest history yet.")

    lines.extend(["", "Suggested Actions:"])
    if not status["initialized"]:
        lines.append("- Run /wiki init to create the wiki structure.")
    elif total_pages == 0:
        lines.append("- Run /wiki ingest <url-or-local-file> to seed the first article and related pages.")
    else:
        if int(status["pages"].get("queries", 0)) == 0:
            lines.append("- File a durable answer with /wiki file-query so important conclusions stop living only in chat.")
        if int(status["pages"].get("comparisons", 0)) == 0:
            lines.append("- Capture a recurring tradeoff with /wiki compare to make decision criteria reusable.")
        if int(status["pages"].get("entities", 0)) == 0 or int(status["pages"].get("concepts", 0)) == 0:
            lines.append("- Deepen the graph with /wiki entity or /wiki concept so sources connect to stable nodes.")
        if last_ingest:
            lines.append("- Review the latest ingest and confirm its summary and linked pages before relying on it.")
    return "\n".join(lines)


def _slugify(text: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in text).split("-") if part) or "source"


def _extract_title_and_body(path: Path, text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines()]
    for line in lines:
        if line:
            return line.lstrip("#").strip()[:120] or path.stem.replace("-", " ").title(), text
    return path.stem.replace("-", " ").title(), text


def _wiki_raw_root(wiki_path: Path) -> Path:
    raw_root = wiki_path / "raw"
    if raw_root.exists():
        return raw_root
    legacy_raw = wiki_path / "raw"
    return legacy_raw


def _last_ingest_state_path(wiki_path: Path) -> Path:
    return wiki_path / ".hermes-wiki-last-ingest.json"


def _build_follow_ups(
    *,
    summary: str,
    entities: List[str],
    concepts: List[str],
    source_label: str,
    is_pdf: bool = False,
) -> List[str]:
    follow_ups = ["Review the article summary and linked pages for accuracy before relying on them."]
    if entities:
        follow_ups.append(f"Expand the seeded entity pages: {', '.join(entities)}.")
    if concepts:
        follow_ups.append(f"Refine the concept pages and add broader wikilinks: {', '.join(concepts)}.")
    if not summary and not is_pdf:
        follow_ups.append("Add a human-checked summary; this source was captured without a compiled synopsis.")
    if is_pdf:
        follow_ups.append("Run a PDF-aware review workflow to extract quotes, figures, and a structured summary.")
    if source_label.startswith("http://") or source_label.startswith("https://"):
        follow_ups.append("Confirm the web extract preserved the key sections and citations from the source page.")
    return follow_ups


def _record_last_ingest(
    *,
    wiki_path: Path,
    source_label: str,
    raw_copy: Path,
    article_file: str,
    related_files: List[str],
    entities: List[str],
    concepts: List[str],
    summary: str,
    follow_ups: List[str],
) -> None:
    state = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "source_label": source_label,
        "raw_copy": str(raw_copy),
        "raw_copy_relative": str(raw_copy.relative_to(wiki_path)),
        "article_file": article_file,
        "related_files": related_files,
        "entities": entities,
        "concepts": concepts,
        "summary": summary,
        "follow_ups": follow_ups,
        "touched_files": [article_file, *related_files],
    }
    _last_ingest_state_path(wiki_path).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_last_ingest(wiki_path: Path) -> Dict[str, Any] | None:
    state_path = _last_ingest_state_path(wiki_path)
    if not state_path.exists():
        return None
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def format_wiki_review() -> str:
    wiki_path = resolve_llm_wiki_path()
    state = _load_last_ingest(wiki_path)
    if not state:
        return (
            "Wiki review unavailable\n"
            f"Path: {wiki_path}\n"
            "No ingest history has been recorded yet. Run /wiki ingest <url-or-local-file> first."
        )

    lines = [
        "Wiki review",
        f"Path: {wiki_path}",
        f"Captured: {state.get('captured_at', 'unknown')}",
        f"Source: {state.get('source_label', 'unknown')}",
        f"Raw copy: {state.get('raw_copy', 'unknown')}",
        f"Article page: {state.get('article_file', 'unknown')}",
        "",
        "Touched files:",
    ]
    for path in state.get("touched_files") or []:
        lines.append(f"- {path}")
    summary = (state.get("summary") or "").strip()
    if summary:
        lines.extend(["", "Summary snapshot:", summary])
    lines.extend(["", "Suggested follow-ups:"])
    for item in state.get("follow_ups") or ["Review and expand the ingested pages."]:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _parse_file_query_argument(argument: str) -> Tuple[str, str] | None:
    if "::" not in argument:
        return None
    question, answer = argument.split("::", 1)
    question = question.strip()
    answer = answer.strip()
    if not question or not answer:
        return None
    return question, answer


def _parse_entity_argument(argument: str) -> Tuple[str, str] | None:
    if "::" not in argument:
        return None
    title, notes = argument.split("::", 1)
    title = title.strip()
    notes = notes.strip()
    if not title or not notes:
        return None
    return title, notes


def _parse_concept_argument(argument: str) -> Tuple[str, str] | None:
    if "::" not in argument:
        return None
    title, notes = argument.split("::", 1)
    title = title.strip()
    notes = notes.strip()
    if not title or not notes:
        return None
    return title, notes


def _title_from_relative_page(page: str) -> str:
    stem = Path(page).stem.replace("-", " ").strip()
    return stem.title() if stem else page


def _latest_ingest_context() -> Tuple[List[str], List[str], List[str], List[str]]:
    wiki_path = resolve_llm_wiki_path()
    state = _load_last_ingest(wiki_path)

    sources: List[str] = []
    support_lines: List[str] = []
    related_lines: List[str] = []
    tags: List[str] = []

    if state:
        article_file = str(state.get("article_file") or "").strip()
        raw_relative = str(state.get("raw_copy_relative") or "").strip()
        if raw_relative:
            sources.append(raw_relative)
            support_lines.append(f"- Raw source: `{raw_relative}`")
        if article_file:
            sources.append(article_file)
            article_title = _title_from_relative_page(article_file)
            support_lines.append(f"- Related article: [[{article_file}|{article_title}]]")
            related_lines.append(f"- Article: [[{article_file}|{article_title}]]")
        for page in state.get("related_files") or []:
            page_str = str(page).strip()
            if not page_str:
                continue
            page_title = _title_from_relative_page(page_str)
            related_lines.append(f"- Related page: [[{page_str}|{page_title}]]")
        if state.get("entities"):
            tags.append("ingest-linked")
    return sources, support_lines, related_lines, tags


def _file_query_page(question: str, answer: str) -> str:
    kb_tool(action="init", domain="General personal wiki")
    sources, support_lines, related_lines, ingest_tags = _latest_ingest_context()
    tags = ["query", "durable-answer", *ingest_tags]

    title = question.rstrip(" ?") + "?"
    if title == "?":
        title = question.strip()

    content_parts = [
        f"# {title}",
        "",
        "## Answer",
        answer.strip(),
        "",
        "## Supporting Context",
    ]
    if support_lines:
        content_parts.extend(support_lines)
    else:
        content_parts.append("- Add supporting sources or related pages if this answer should become canonical.")
    content_parts.extend(["", "## Related Pages"])
    if related_lines:
        content_parts.extend(related_lines)
    else:
        content_parts.append("- No linked wiki pages yet.")
    content_parts.extend(
        [
            "",
            "## Maintenance Notes",
            "- Revisit this page when new evidence changes the answer.",
            "- Add comparisons if the question becomes a recurring decision point.",
        ]
    )
    result = json.loads(
        kb_tool(
            action="file",
            title=title,
            page_type="query",
            tags=",".join(tags),
            sources=",".join(dict.fromkeys(sources)),
            content="\n".join(content_parts),
        )
    )
    return (
        "Wiki query filed\n"
        f"Question: {title}\n"
        f"Page: {result['file']}\n"
        f"Linked sources: {len(dict.fromkeys(sources))}\n"
        f"Related pages: {len(related_lines)}"
    )


def _file_entity_page(title: str, notes: str) -> str:
    kb_tool(action="init", domain="General personal wiki")
    sources, support_lines, related_lines, ingest_tags = _latest_ingest_context()
    tags = ["entity", "durable-page", *ingest_tags]

    content_parts = [
        f"# {title}",
        "",
        "## Overview",
        notes.strip(),
        "",
        "## Supporting Context",
    ]
    if support_lines:
        content_parts.extend(support_lines)
    else:
        content_parts.append("- Add supporting sources, articles, or related pages as this entity accumulates context.")
    content_parts.extend(["", "## Related Pages"])
    if related_lines:
        content_parts.extend(related_lines)
    else:
        content_parts.append("- No linked wiki pages yet.")
    content_parts.extend(
        [
            "",
            "## Maintenance Notes",
            "- Update this page as the entity's role, relationships, or significance changes.",
            "- Split recurring tradeoffs into comparisons and durable answers into query pages when helpful.",
        ]
    )
    result = json.loads(
        kb_tool(
            action="file",
            title=title,
            page_type="entity",
            tags=",".join(tags),
            sources=",".join(dict.fromkeys(sources)),
            content="\n".join(content_parts),
        )
    )
    return (
        "Wiki entity filed\n"
        f"Title: {title}\n"
        f"Page: {result['file']}\n"
        f"Linked sources: {len(dict.fromkeys(sources))}\n"
        f"Related pages: {len(related_lines)}"
    )


def _file_concept_page(title: str, notes: str) -> str:
    kb_tool(action="init", domain="General personal wiki")
    sources, support_lines, related_lines, ingest_tags = _latest_ingest_context()
    tags = ["concept", "durable-page", *ingest_tags]

    content_parts = [
        f"# {title}",
        "",
        "## Definition",
        notes.strip(),
        "",
        "## Supporting Context",
    ]
    if support_lines:
        content_parts.extend(support_lines)
    else:
        content_parts.append("- Add supporting sources, article links, or examples as this concept becomes more central.")
    content_parts.extend(["", "## Related Pages"])
    if related_lines:
        content_parts.extend(related_lines)
    else:
        content_parts.append("- No linked wiki pages yet.")
    content_parts.extend(
        [
            "",
            "## Maintenance Notes",
            "- Refine this definition as the concept becomes sharper across more sources.",
            "- Split recurring decisions into comparisons and durable answers into query pages when that adds clarity.",
        ]
    )
    result = json.loads(
        kb_tool(
            action="file",
            title=title,
            page_type="concept",
            tags=",".join(tags),
            sources=",".join(dict.fromkeys(sources)),
            content="\n".join(content_parts),
        )
    )
    return (
        "Wiki concept filed\n"
        f"Title: {title}\n"
        f"Page: {result['file']}\n"
        f"Linked sources: {len(dict.fromkeys(sources))}\n"
        f"Related pages: {len(related_lines)}"
    )


def _parse_compare_argument(argument: str) -> Tuple[str, str, str, str, str] | None:
    if "::" not in argument or "||" not in argument:
        return None
    title, remainder = argument.split("::", 1)
    sides = [part.strip() for part in remainder.split("||") if part.strip()]
    if len(sides) != 2:
        return None

    parsed_sides: List[Tuple[str, str]] = []
    for side in sides:
        if "=>" not in side:
            return None
        label, notes = side.split("=>", 1)
        label = label.strip()
        notes = notes.strip()
        if not label or not notes:
            return None
        parsed_sides.append((label, notes))

    title = title.strip()
    if not title:
        return None
    return title, parsed_sides[0][0], parsed_sides[0][1], parsed_sides[1][0], parsed_sides[1][1]


def _file_comparison_page(
    title: str,
    left_label: str,
    left_notes: str,
    right_label: str,
    right_notes: str,
) -> str:
    kb_tool(action="init", domain="General personal wiki")
    sources, support_lines, related_lines, ingest_tags = _latest_ingest_context()
    tags = ["comparison", "tradeoff", *ingest_tags]

    content_parts = [
        f"# {title}",
        "",
        "## Comparison",
        f"### {left_label}",
        left_notes.strip(),
        "",
        f"### {right_label}",
        right_notes.strip(),
        "",
        "## Working Takeaway",
        f"- Prefer `{left_label}` when the first set of conditions dominates.",
        f"- Prefer `{right_label}` when the second set of conditions dominates.",
        "",
        "## Supporting Context",
    ]
    if support_lines:
        content_parts.extend(support_lines)
    else:
        content_parts.append("- Add supporting sources before treating this comparison as canonical.")
    content_parts.extend(["", "## Related Pages"])
    if related_lines:
        content_parts.extend(related_lines)
    else:
        content_parts.append("- No linked wiki pages yet.")
    content_parts.extend(
        [
            "",
            "## Maintenance Notes",
            "- Revisit this comparison when new evidence changes the tradeoff.",
            "- Convert the working takeaway into a stronger recommendation after review if needed.",
        ]
    )
    result = json.loads(
        kb_tool(
            action="file",
            title=title,
            page_type="comparison",
            tags=",".join(tags),
            sources=",".join(dict.fromkeys(sources)),
            content="\n".join(content_parts),
        )
    )
    return (
        "Wiki comparison filed\n"
        f"Title: {title}\n"
        f"Page: {result['file']}\n"
        f"Linked sources: {len(dict.fromkeys(sources))}\n"
        f"Related pages: {len(related_lines)}"
    )


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, flags=re.DOTALL)


def _clean_markdown_line(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    return " ".join(text.strip().split())


def _extract_summary(text: str, max_paragraphs: int = 2) -> str:
    body = _strip_frontmatter(text)
    paragraphs: List[str] = []
    current: List[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraph = _clean_markdown_line(" ".join(current))
                if paragraph:
                    paragraphs.append(paragraph)
                current = []
            continue
        if line.startswith("#"):
            continue
        current.append(line)
    if current:
        paragraph = _clean_markdown_line(" ".join(current))
        if paragraph:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs[:max_paragraphs]).strip()


def _extract_heading_candidates(text: str) -> List[str]:
    headings: List[str] = []
    for line in _strip_frontmatter(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            heading = stripped.lstrip("#").strip()
            if heading and heading.lower() not in {"summary", "source", "intake notes"}:
                headings.append(heading[:120])
    return headings


def _extract_entity_candidates(text: str, title: str, limit: int = 3) -> List[str]:
    body = _strip_frontmatter(text)
    sentences: List[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cleaned = _clean_markdown_line(line)
        if not cleaned:
            continue
        sentences.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip())

    pattern = re.compile(
        r"\b("
        r"(?:[A-Z][a-zA-Z0-9]*|[A-Z]{2,})"
        r"(?:"
        r"(?:\s+(?:and|&|of|for|the)\s+(?:[A-Z][a-zA-Z0-9]*|[A-Z]{2,}))"
        r"|(?:\s+(?:[A-Z][a-zA-Z0-9]*|[A-Z]{2,}))"
        r"){0,4}"
        r")\b"
    )
    stop_phrases = {
        title.lower(),
        "intake notes",
        "source url",
        "original url",
    }
    seen: set[str] = set()
    candidates: List[str] = []
    for sentence in sentences:
        for match in pattern.findall(sentence):
            cleaned = " ".join(match.split()).strip(".,:;()[]")
            lowered = cleaned.lower()
            if len(cleaned) < 2:
                continue
            if lowered in stop_phrases:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            candidates.append(cleaned)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _extract_concept_candidates(text: str, title: str, limit: int = 3) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        cleaned = _clean_markdown_line(value).strip(".,:;()[]")
        if not cleaned:
            return
        lowered = cleaned.lower()
        if lowered == title.lower() or lowered in seen:
            return
        seen.add(lowered)
        candidates.append(cleaned)

    for heading in _extract_heading_candidates(text):
        add(heading)
        if len(candidates) >= limit:
            return candidates[:limit]

    for term in re.findall(r"`([^`]{2,80})`", text):
        add(term)
        if len(candidates) >= limit:
            return candidates[:limit]

    return candidates[:limit]


def _seed_related_pages(
    title: str,
    article_page_title: str,
    relative_raw: Path,
    summary: str,
    entities: List[str],
    concepts: List[str],
) -> List[str]:
    touched: List[str] = []
    source_ref = str(relative_raw)

    for entity in entities:
        content = (
            f"# {entity}\n\n"
            "## Overview\n"
            f"- First surfaced during ingest of [[{_slugify(article_page_title)}|{article_page_title}]].\n"
            f"- Source: `{source_ref}`\n\n"
            "## Notes\n"
            f"- Mentioned in relation to {title}.\n"
        )
        result = json.loads(
            kb_tool(
                action="file",
                title=entity,
                page_type="entity",
                tags="ingested,entity",
                sources=source_ref,
                content=content,
            )
        )
        touched.append(result["file"])

    for concept in concepts:
        content = (
            f"# {concept}\n\n"
            "## Definition\n"
            f"- Seeded from [[{_slugify(article_page_title)}|{article_page_title}]].\n"
            f"- Source: `{source_ref}`\n\n"
            "## Early Notes\n"
            f"- Related summary: {summary or 'Review the source for details.'}\n"
        )
        result = json.loads(
            kb_tool(
                action="file",
                title=concept,
                page_type="concept",
                tags="ingested,concept",
                sources=source_ref,
                content=content,
            )
        )
        touched.append(result["file"])

    return touched


def _seed_article_page(
    *,
    title: str,
    source_label: str,
    relative_raw: Path,
    summary: str,
    entities: List[str],
    concepts: List[str],
    tags: str,
) -> str:
    related_lines = []
    for entity in entities:
        related_lines.append(f"- Entity: [[entities/{_slugify(entity)}|{entity}]]")
    for concept in concepts:
        related_lines.append(f"- Concept: [[concepts/{_slugify(concept)}|{concept}]]")
    related_section = "\n".join(related_lines) if related_lines else "- No related pages were auto-detected."

    content = (
        f"# {title}\n\n"
        "## Source\n"
        f"- Original source: {source_label}\n"
        f"- Stored at: `{relative_raw}`\n"
        f"- Ingested: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        "## Summary\n"
        f"{summary or 'Summary pending review.'}\n\n"
        "## Related Pages\n"
        f"{related_section}\n\n"
        "## Intake Notes\n"
        "- Review the summary for accuracy.\n"
        "- Expand or refine the related pages.\n"
        "- Add wikilinks to broader themes and ongoing investigations.\n"
    )
    result = json.loads(
        kb_tool(
            action="file",
            title=title,
            page_type="article",
            tags=tags,
            sources=str(relative_raw),
            content=content,
        )
    )
    return result["file"]


def _ingest_compiled_pages(
    *,
    title: str,
    source_label: str,
    relative_raw: Path,
    raw_text: str,
    tags: str,
) -> Tuple[str, List[str], List[str], List[str], str]:
    summary = _extract_summary(raw_text)
    entities = _extract_entity_candidates(raw_text, title)
    concepts = _extract_concept_candidates(raw_text, title)
    article_file = _seed_article_page(
        title=title,
        source_label=source_label,
        relative_raw=relative_raw,
        summary=summary,
        entities=entities,
        concepts=concepts,
        tags=tags,
    )
    touched = _seed_related_pages(
        title=title,
        article_page_title=title,
        relative_raw=relative_raw,
        summary=summary,
        entities=entities,
        concepts=concepts,
    )
    return article_file, touched, entities, concepts, summary


def _save_local_source(source: str) -> str:
    source_path = Path(source).expanduser()
    if not source_path.exists():
        return f"Wiki ingest failed: local source not found: {source_path}"
    if not source_path.is_file():
        return f"Wiki ingest failed: local source is not a file: {source_path}"

    wiki_path = resolve_llm_wiki_path()
    kb_tool(action="init", domain="General personal wiki")
    raw_root = _wiki_raw_root(wiki_path)

    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        subdir = raw_root / "papers"
    elif suffix in {".md", ".txt", ".html", ".htm"}:
        subdir = raw_root / "articles"
    else:
        return (
            "Wiki ingest failed: unsupported local file type. "
            "Use a text-like file (.md, .txt, .html) or a PDF."
        )

    subdir.mkdir(parents=True, exist_ok=True)
    target_name = source_path.name if source_path.name else f"{_slugify(source_path.stem)}.md"
    target_path = subdir / target_name

    if suffix == ".pdf":
        target_path.write_bytes(source_path.read_bytes())
        title = source_path.stem.replace("-", " ").title()
        article_file = json.loads(
            kb_tool(
                action="file",
                title=title,
                page_type="article",
                tags="ingested,source,pdf",
                sources=str(target_path.relative_to(wiki_path)),
                content=(
                    f"# {title}\n\n"
                    "## Source\n"
                    f"- Captured from local PDF: `{source_path}`\n"
                    f"- Stored at: `{target_path.relative_to(wiki_path)}`\n"
                    f"- Ingested: {datetime.now().strftime('%Y-%m-%d')}\n\n"
                    "## Intake Notes\n"
                    "- PDF captured. Review and summarize manually or with a PDF-aware workflow.\n"
                ),
            )
        )["file"]
        related_files: List[str] = []
        entities: List[str] = []
        concepts: List[str] = []
        summary = ""
    else:
        text = source_path.read_text(encoding="utf-8")
        target_path.write_text(text, encoding="utf-8")
        title, _ = _extract_title_and_body(source_path, text)
        article_file, related_files, entities, concepts, summary = _ingest_compiled_pages(
            title=title,
            source_label=f"local file `{source_path}`",
            relative_raw=target_path.relative_to(wiki_path),
            raw_text=text,
            tags="ingested,source",
        )
    follow_ups = _build_follow_ups(
        summary=summary,
        entities=entities,
        concepts=concepts,
        source_label=str(source_path),
        is_pdf=suffix == ".pdf",
    )
    _record_last_ingest(
        wiki_path=wiki_path,
        source_label=str(source_path),
        raw_copy=target_path,
        article_file=article_file,
        related_files=related_files,
        entities=entities,
        concepts=concepts,
        summary=summary,
        follow_ups=follow_ups,
    )
    return (
        "Wiki ingest complete\n"
        f"Source: {source_path}\n"
        f"Raw copy: {target_path}\n"
        f"Article page: {article_file}\n"
        f"Related pages: {len(related_files)}\n"
        f"Entities: {', '.join(entities) if entities else 'none'}\n"
        f"Concepts: {', '.join(concepts) if concepts else 'none'}"
    )


async def _save_url_source(url: str) -> str:
    from tools.web_tools import web_extract_tool

    wiki_path = resolve_llm_wiki_path()
    kb_tool(action="init", domain="General personal wiki")
    raw_root = _wiki_raw_root(wiki_path)
    raw_articles = raw_root / "articles"
    raw_articles.mkdir(parents=True, exist_ok=True)

    extracted = json.loads(await web_extract_tool([url], format="markdown", use_llm_processing=False))
    results = extracted.get("results") or []
    if not results:
        return f"Wiki ingest failed: no extractable content returned for {url}"

    first = results[0]
    if first.get("error"):
        return f"Wiki ingest failed: {first['error']}"

    final_url = first.get("url") or url
    title = (first.get("title") or urlparse(final_url).netloc or "Web source").strip()
    content = first.get("content", "").strip()
    if not content:
        return f"Wiki ingest failed: extracted content was empty for {final_url}"

    slug = _slugify(title or final_url)
    target_path = raw_articles / f"{slug}.md"
    target_path.write_text(content + "\n", encoding="utf-8")

    article_file, related_files, entities, concepts, summary = _ingest_compiled_pages(
        title=title,
        source_label=final_url,
        relative_raw=target_path.relative_to(wiki_path),
        raw_text=content,
        tags="ingested,source,web",
    )
    follow_ups = _build_follow_ups(
        summary=summary,
        entities=entities,
        concepts=concepts,
        source_label=final_url,
    )
    _record_last_ingest(
        wiki_path=wiki_path,
        source_label=final_url,
        raw_copy=target_path,
        article_file=article_file,
        related_files=related_files,
        entities=entities,
        concepts=concepts,
        summary=summary,
        follow_ups=follow_ups,
    )
    return (
        "Wiki ingest complete\n"
        f"Source URL: {final_url}\n"
        f"Raw copy: {target_path}\n"
        f"Article page: {article_file}\n"
        f"Related pages: {len(related_files)}\n"
        f"Entities: {', '.join(entities) if entities else 'none'}\n"
        f"Concepts: {', '.join(concepts) if concepts else 'none'}"
    )


async def run_wiki_command_async(subcommand: str, argument: str = "") -> str:
    normalized = (subcommand or "status").strip().lower()
    argument = argument.strip()

    if normalized == "ingest":
        if not argument:
            return (
                "Usage: /wiki ingest <url-or-local-file>\n"
                "- URLs are extracted to raw/articles/, summarized, and compiled into article/entity/concept pages\n"
                "- Local .md/.txt/.html files are copied into raw/ and compiled the same way\n"
                "- PDFs are copied into raw/papers/ and seeded as article pages pending deeper review"
            )
        if argument.startswith(("http://", "https://")):
            return await _save_url_source(argument)
        return _save_local_source(argument)

    return run_wiki_command(subcommand, argument)


def run_wiki_command(subcommand: str, argument: str = "") -> str:
    normalized = (subcommand or "status").strip().lower()
    argument = argument.strip()

    if normalized in {"", "help"}:
        return (
            "Usage: /wiki [init|status|lint|ingest|review|map|file-query|compare|entity|concept] [domain|source]\n"
            "- /wiki init [domain]: initialize the persistent markdown wiki\n"
            "- /wiki status: show wiki path, vault path, and page counts\n"
            "- /wiki lint: audit the wiki for broken links, orphans, stale pages, and missing index entries\n"
            "- /wiki ingest <url-or-local-file>: capture a source into raw/ and seed article, entity, and concept pages\n"
            "- /wiki review: inspect the last ingest's touched files and suggested follow-ups"
            "\n- /wiki map: summarize the current graph, recent pages, and likely next maintenance actions"
            "\n- /wiki file-query <question> :: <answer>: file a durable answer into queries/, linked to the latest ingest when available"
            "\n- /wiki compare <title> :: <option A> => <notes> || <option B> => <notes>: file a tradeoff page into comparisons/"
            "\n- /wiki entity <title> :: <notes>: file or enrich a durable entity page in entities/"
            "\n- /wiki concept <title> :: <notes>: file or enrich a durable concept page in concepts/"
        )

    if normalized == "status":
        return format_wiki_status()

    if normalized == "init":
        result = json.loads(kb_tool(action="init", domain=argument or "General personal wiki"))
        return (
            "Wiki initialized\n"
            f"Path: {result['wiki_path']}\n"
            f"Layout: {result['layout']}\n"
            "Created:\n"
            + "\n".join(f"- {path}" for path in result["created"])
            + "\n\nNext steps:\n"
            + "- /wiki ingest <url-or-local-file>\n"
            + "- /wiki review\n"
            + "- /wiki map"
        )

    if normalized == "lint":
        result = json.loads(kb_tool(action="lint"))
        if not result.get("success"):
            return f"Wiki lint failed: {result.get('error', 'unknown error')}"
        lines = [
            "Wiki lint complete",
            f"Path: {result['wiki_path']}",
            f"Issue count: {result['issue_count']}",
        ]
        issues = result.get("issues", {})
        for key, values in issues.items():
            lines.append(f"- {key}: {len(values)}")
        return "\n".join(lines)

    if normalized == "review":
        return format_wiki_review()

    if normalized == "map":
        return format_wiki_map()

    if normalized == "file-query":
        parsed = _parse_file_query_argument(argument)
        if not parsed:
            return (
                "Usage: /wiki file-query <question> :: <answer>\n"
                "Example: /wiki file-query What is Hermes wiki for? :: It is the persistent markdown memory layer Hermes maintains inside or alongside Obsidian."
            )
        question, answer = parsed
        return _file_query_page(question, answer)

    if normalized == "compare":
        parsed = _parse_compare_argument(argument)
        if not parsed:
            return (
                "Usage: /wiki compare <title> :: <option A> => <notes> || <option B> => <notes>\n"
                "Example: /wiki compare Agents SDK vs MCP tools :: Agents SDK => Better for stateful loops. || MCP tools => Better for explicit external actions."
            )
        title, left_label, left_notes, right_label, right_notes = parsed
        return _file_comparison_page(title, left_label, left_notes, right_label, right_notes)

    if normalized == "entity":
        parsed = _parse_entity_argument(argument)
        if not parsed:
            return (
                "Usage: /wiki entity <title> :: <notes>\n"
                "Example: /wiki entity OpenAI :: Model provider and research lab relevant to the current topic."
            )
        title, notes = parsed
        return _file_entity_page(title, notes)

    if normalized == "concept":
        parsed = _parse_concept_argument(argument)
        if not parsed:
            return (
                "Usage: /wiki concept <title> :: <notes>\n"
                "Example: /wiki concept Sparse routing :: A routing pattern where only a subset of experts activates for each token."
            )
        title, notes = parsed
        return _file_concept_page(title, notes)

    if normalized == "ingest":
        try:
            return asyncio.run(run_wiki_command_async(normalized, argument))
        except RuntimeError:
            return (
                "Wiki ingest requires async execution and could not start from this context.\n"
                "Try again from the gateway or use a non-URL local file source."
            )

    return (
        f"Unknown /wiki subcommand: {normalized}\n"
        "Use: /wiki init [domain], /wiki status, /wiki lint, /wiki ingest <source>, /wiki review, /wiki map, /wiki file-query <question> :: <answer>, /wiki compare <title> :: <option A> => <notes> || <option B> => <notes>, /wiki entity <title> :: <notes>, or /wiki concept <title> :: <notes>"
    )
