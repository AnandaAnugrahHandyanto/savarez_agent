"""Structured retrieval pack for memory providers.

Inspired by holaOS's 5-section retrieval pack (memory-retrieval-pack.ts):
``known_facts / high_signal / constraints / blockers / open_questions``.

A :class:`RetrievalPack` is a structured container that a memory
provider can return from :func:`MemoryProvider.retrieve_pack` instead of
free-form text from :func:`MemoryProvider.prefetch`.  The system prompt
builder renders the pack into a fixed five-section fenced block, so
downstream models see a stable, parseable structure that preserves
prompt caching while still letting providers contribute semantic
categories of recall (a fact, a blocker, an open question) that pure
free-text prefetch cannot represent.

The five sections, with their contract:

``known_facts``
    Authoritative, durable facts about the user, environment, or
    workspace.  Items here are stated as-is, never paraphrased.
    Preference and identity entries live here.

``high_signal``
    Recent, time-relevant items that may not be durable (recent
    integrations, recent events, recent decisions).  Subject to
    staleness over hours/days.

``constraints``
    Hard constraints the agent must respect (security policies,
    access boundaries, role-based restrictions).

``blockers``
    Active problems or open issues that prevent progress.  Surfaced
    so the agent does not re-investigate.

``open_questions``
    Unresolved threads the user previously raised.  Surfaced so the
    agent can follow up or carry context forward.

Providers that do not implement :func:`MemoryProvider.retrieve_pack`
fall back to :func:`MemoryProvider.prefetch`.  The pack is rendered
via :func:`render_retrieval_pack` which always emits the same five
headings in the same order, regardless of which provider sections
are populated, so the LLM sees a stable shape.

The design intent is to give providers a richer, more deterministic
language for "what is in this chunk of recalled context" without
breaking the existing string-based prefetch contract that all 7
external provider plugins (honcho, mem0, supermemory, ...) already
implement.  Adding ``retrieve_pack`` is opt-in; ``MemoryManager``
silently degrades to ``prefetch`` for providers that do not override.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


# Ordered, fixed list of section names.  The order is part of the
# contract — downstream prompts and tests rely on it.
PACK_SECTIONS: tuple = (
    "known_facts",
    "high_signal",
    "constraints",
    "blockers",
    "open_questions",
)


@dataclass
class RetrievalPack:
    """A structured 5-section recall result from a memory provider.

    Each section is a list of short text items.  Empty sections are
    permitted and render as "(none)" so the LLM can still see the
    section exists.  Items should be self-contained and short
    (typically 1-2 lines); the renderer caps each section to a
    configurable number of items to bound prompt size.
    """

    known_facts: List[str] = field(default_factory=list)
    high_signal: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True if every section is empty."""
        return not any(
            getattr(self, name) for name in PACK_SECTIONS
        )

    def section(self, name: str) -> List[str]:
        """Return the items in section ``name`` (case-sensitive).

        Raises ``KeyError`` for unknown section names so caller bugs
        surface immediately rather than silently dropping data.
        """
        if name not in PACK_SECTIONS:
            raise KeyError(
                f"unknown retrieval pack section: {name!r}; "
                f"valid sections are {PACK_SECTIONS}"
            )
        return getattr(self, name)

    def merge(self, other: "RetrievalPack") -> "RetrievalPack":
        """Return a new pack with items from ``other`` appended to each section.

        Used by :class:`MemoryManager` to combine packs from multiple
        providers without mutating either input.  Items are appended in
        order; downstream rerankers (see ``retrieval_intent``) are
        responsible for ordering by relevance.
        """
        return RetrievalPack(
            known_facts=list(self.known_facts) + list(other.known_facts),
            high_signal=list(self.high_signal) + list(other.high_signal),
            constraints=list(self.constraints) + list(other.constraints),
            blockers=list(self.blockers) + list(other.blockers),
            open_questions=list(self.open_questions) + list(other.open_questions),
        )

    @classmethod
    def from_iterables(
        cls,
        known_facts: Optional[Iterable[str]] = None,
        high_signal: Optional[Iterable[str]] = None,
        constraints: Optional[Iterable[str]] = None,
        blockers: Optional[Iterable[str]] = None,
        open_questions: Optional[Iterable[str]] = None,
    ) -> "RetrievalPack":
        """Build a pack from optional iterables; ``None`` sections become empty."""
        return cls(
            known_facts=list(known_facts or []),
            high_signal=list(high_signal or []),
            constraints=list(constraints or []),
            blockers=list(blockers or []),
            open_questions=list(open_questions or []),
        )

    @classmethod
    def from_freetext(cls, text: str) -> "RetrievalPack":
        """Best-effort fallback: put free-text into ``high_signal``.

        Used when a provider returns a string (legacy ``prefetch``)
        and we need a pack-shaped result for the new pipeline.  All
        non-empty lines are treated as time-relevant high-signal
        items, the cheapest and safest default category.
        """
        if not text or not text.strip():
            return cls()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return cls(high_signal=lines)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_retrieval_pack(
    pack: Optional["RetrievalPack"],
    *,
    max_items_per_section: int = 12,
    max_chars_per_item: int = 400,
) -> str:
    """Render a :class:`RetrievalPack` to a stable, fenced text block.

    The output always lists all five section headings in the canonical
    order, even when a section is empty (rendered as ``(none)``).
    This makes the block's shape predictable for the LLM, which
    preserves prompt caching across turns (the system prompt block is
    stable; only the items within each section rotate).

    Parameters
    ----------
    pack:
        The pack to render.  Empty packs return an empty string.
    max_items_per_section:
        Cap on items per section.  Excess items are dropped silently
        (callers that care should rerank beforehand).
    max_chars_per_item:
        Cap on the length of each item.  Items longer than this are
        truncated with an ellipsis.  This is character-based, not
        token-based, to stay model-agnostic.
    """
    if pack is None or pack.is_empty():
        return ""

    lines: List[str] = []
    for name in PACK_SECTIONS:
        items = pack.section(name)
        if items:
            lines.append(f"## {name}")
            for raw in items[:max_items_per_section]:
                item = (raw or "").strip()
                if not item:
                    continue
                if len(item) > max_chars_per_item:
                    item = item[: max_chars_per_item - 1].rstrip() + "…"
                lines.append(f"- {item}")
            lines.append("")
        else:
            lines.append(f"## {name}")
            lines.append("- (none)")
            lines.append("")

    # Strip trailing blank line for cleanliness.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


__all__ = [
    "PACK_SECTIONS",
    "RetrievalPack",
    "render_retrieval_pack",
]
