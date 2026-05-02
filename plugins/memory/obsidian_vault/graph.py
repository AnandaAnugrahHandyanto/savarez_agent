"""Obsidian graph helpers for vault-local note expansion.

The graph layer is deliberately file-based and vault-bounded. QMD finds the
semantic seed notes; this module expands from those seeds through Obsidian's
native graph signals without spraying the whole vault into context.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from .paths import resolve_relative_path

WIKILINK_RE = re.compile(r"!?(?<!`)\[\[([^\]\n]+)\]\]")
MARKDOWN_MD_LINK_RE = re.compile(r"\[[^\]\n]+\]\(([^)\n]+?\.md(?:#[^)\n]*)?)\)")
INLINE_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][A-Za-z0-9_/-]*)")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class GraphNote:
    """A note plus the graph signals discovered for it."""

    path: str
    title: str
    links: set[str] = field(default_factory=set)
    backlinks: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)


@dataclass
class ExpandedNote:
    """A seed or graph-expanded note returned to the caller."""

    path: str
    title: str
    score: float
    reasons: set[str] = field(default_factory=set)
    snippet: str = ""
    depth: int = 0


def slugify_path(value: str | Path) -> str:
    """Return the slug style used by QMD qmd:// file URIs."""

    text = str(value).replace("\\", "/").lower()
    suffix = ""
    if text.endswith(".md"):
        text = text[:-3]
        suffix = ".md"
    text = re.sub(r"[^a-z0-9/]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = re.sub(r"/+", "/", text).strip("-/")
    parts = [part.strip("-") for part in text.split("/") if part.strip("-")]
    return "/".join(parts) + suffix


def note_title(path: Path) -> str:
    return path.stem


def relpath(vault_root: Path, path: Path) -> str:
    return path.resolve().relative_to(vault_root.resolve()).as_posix()


def iter_markdown_notes(vault_root: str | Path) -> list[Path]:
    root = Path(vault_root).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def build_note_lookup(vault_root: str | Path) -> dict[str, str]:
    """Map common note identifiers and QMD slugs to vault-relative paths.

    Full vault-relative paths win over ambiguous basenames. Without that, a
    root `README.md` can be shadowed by `60 Sources/Meetings/README.md`, which
    is exactly the sort of tiny graph bug that later wears a fake moustache.
    """

    root = Path(vault_root).expanduser().resolve()
    lookup: dict[str, str] = {}
    basename_keys: list[tuple[str, str]] = []
    for path in iter_markdown_notes(root):
        rel = relpath(root, path)
        rel_lower = rel.lower()
        full_keys = {
            rel,
            rel_lower,
            rel[:-3] if rel.lower().endswith(".md") else rel,
            rel_lower[:-3] if rel_lower.endswith(".md") else rel_lower,
            slugify_path(rel),
            slugify_path(rel[:-3] if rel.lower().endswith(".md") else rel),
        }
        for key in full_keys:
            lookup[key] = rel
        basename_keys.append((path.name.lower(), rel))
        basename_keys.append((path.stem.lower(), rel))

    for key, rel in basename_keys:
        lookup.setdefault(key, rel)
    return lookup


def _clean_wikilink_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    return target


def _normalise_candidate(target: str) -> str:
    target = target.strip().replace("\\", "/")
    if target.lower().endswith(".md"):
        return target
    return f"{target}.md" if "/" in target else target


def resolve_note_reference(
    vault_root: str | Path,
    source_rel: str | Path | None,
    target: str,
    lookup: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve a wikilink/markdown note reference to a vault-relative path."""

    if not target:
        return None
    root = Path(vault_root).expanduser().resolve()
    lookup = lookup or build_note_lookup(root)
    raw = _clean_wikilink_target(target)
    if not raw or raw.startswith(("http://", "https://", "mailto:")):
        return None

    candidates: list[str] = []
    normalised = _normalise_candidate(raw)
    candidates.extend([raw, raw.lower(), normalised, normalised.lower(), slugify_path(normalised)])

    if source_rel and not raw.startswith("/"):
        source_dir = Path(str(source_rel)).parent
        if str(source_dir) != ".":
            joined = (source_dir / normalised).as_posix()
            candidates.extend([joined, joined.lower(), slugify_path(joined)])

    for candidate in candidates:
        match = lookup.get(candidate)
        if match:
            return match

    # Last resort: direct path resolution, still bounded by the vault root.
    try:
        candidate_path = resolve_relative_path(root, normalised)
    except ValueError:
        return None
    if candidate_path.exists() and candidate_path.is_file() and candidate_path.suffix.lower() == ".md":
        return relpath(root, candidate_path)
    return None


def extract_wikilinks(text: str) -> set[str]:
    return {_clean_wikilink_target(match.group(1)) for match in WIKILINK_RE.finditer(text) if _clean_wikilink_target(match.group(1))}


def extract_markdown_note_links(text: str) -> set[str]:
    return {match.group(1).split("#", 1)[0].strip() for match in MARKDOWN_MD_LINK_RE.finditer(text)}


def extract_tags(text: str) -> set[str]:
    tags = {match.group(1).strip("/").lower() for match in INLINE_TAG_RE.finditer(text)}
    frontmatter = FRONTMATTER_RE.match(text)
    if frontmatter:
        body = frontmatter.group(1)
        in_tags_block = False
        for line in body.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("tags:"):
                in_tags_block = True
                rest = stripped.split(":", 1)[1].strip()
                if rest.startswith("[") and rest.endswith("]"):
                    for item in rest.strip("[]").split(","):
                        clean = item.strip().strip("'\"").lstrip("#").lower()
                        if clean:
                            tags.add(clean)
                elif rest and not rest.startswith("|"):
                    clean = rest.strip().strip("'\"").lstrip("#").lower()
                    if clean:
                        tags.add(clean)
                continue
            if in_tags_block and stripped.startswith("-"):
                clean = stripped[1:].strip().strip("'\"").lstrip("#").lower()
                if clean:
                    tags.add(clean)
                continue
            if in_tags_block and stripped and not line.startswith((" ", "\t")):
                in_tags_block = False
    return {tag for tag in tags if tag}


def build_graph(vault_root: str | Path) -> dict[str, GraphNote]:
    """Build a lightweight Obsidian graph for all Markdown notes in the vault."""

    root = Path(vault_root).expanduser().resolve()
    lookup = build_note_lookup(root)
    graph: dict[str, GraphNote] = {}

    for path in iter_markdown_notes(root):
        note_rel = relpath(root, path)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        links: set[str] = set()
        for target in extract_wikilinks(text) | extract_markdown_note_links(text):
            resolved = resolve_note_reference(root, note_rel, target, lookup)
            if resolved and resolved != note_rel:
                links.add(resolved)
        graph[note_rel] = GraphNote(
            path=note_rel,
            title=note_title(path),
            links=links,
            tags=extract_tags(text),
        )

    for source, note in graph.items():
        for target in note.links:
            if target in graph:
                graph[target].backlinks.add(source)
    return graph


def excerpt_for_note(vault_root: str | Path, rel: str, max_chars: int = 700) -> str:
    root = Path(vault_root).expanduser().resolve()
    try:
        path = resolve_relative_path(root, rel)
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    text = FRONTMATTER_RE.sub("", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def expand_graph(
    vault_root: str | Path,
    seed_scores: Mapping[str, float],
    *,
    depth: int = 1,
    max_neighbors: int = 12,
    include_wikilinks: bool = True,
    include_backlinks: bool = True,
    include_tag_neighbors: bool = False,
    max_excerpt_chars: int = 700,
) -> list[ExpandedNote]:
    """Expand semantic seed notes through graph neighbors and return ranked notes."""

    root = Path(vault_root).expanduser().resolve()
    graph = build_graph(root)
    results: dict[str, ExpandedNote] = {}
    queue: deque[tuple[str, int]] = deque()

    for seed, score in seed_scores.items():
        if seed not in graph:
            continue
        results[seed] = ExpandedNote(
            path=seed,
            title=graph[seed].title,
            score=float(score),
            reasons={"semantic_seed"},
            snippet=excerpt_for_note(root, seed, max_excerpt_chars),
            depth=0,
        )
        queue.append((seed, 0))

    tag_index: dict[str, set[str]] = {}
    if include_tag_neighbors:
        for path, note in graph.items():
            for tag in note.tags:
                tag_index.setdefault(tag, set()).add(path)

    added_neighbors = 0
    seen_depth: dict[str, int] = {path: 0 for path in results}
    while queue and added_neighbors < max_neighbors:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        note = graph.get(current)
        if not note:
            continue

        candidates: list[tuple[str, str]] = []
        if include_wikilinks:
            candidates.extend((target, "wikilink") for target in sorted(note.links))
        if include_backlinks:
            candidates.extend((source, "backlink") for source in sorted(note.backlinks))
        if include_tag_neighbors:
            tag_neighbors = set()
            for tag in note.tags:
                tag_neighbors.update(tag_index.get(tag, set()))
            candidates.extend((target, "tag") for target in sorted(tag_neighbors) if target != current)

        for target, reason in candidates:
            if target not in graph:
                continue
            next_depth = current_depth + 1
            existing = results.get(target)
            if existing:
                existing.reasons.add(reason)
                existing.depth = min(existing.depth, next_depth)
                continue
            if added_neighbors >= max_neighbors:
                break
            base_score = results[current].score if current in results else 0.1
            score = max(0.01, base_score * (0.55 ** next_depth))
            results[target] = ExpandedNote(
                path=target,
                title=graph[target].title,
                score=score,
                reasons={reason},
                snippet=excerpt_for_note(root, target, max_excerpt_chars),
                depth=next_depth,
            )
            seen_depth[target] = next_depth
            queue.append((target, next_depth))
            added_neighbors += 1

    return sorted(
        results.values(),
        key=lambda note: (0 if "semantic_seed" in note.reasons else 1, note.depth, -note.score, note.path.lower()),
    )
