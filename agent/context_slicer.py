"""Deterministic context-section slicing helpers.

This module is intentionally pure and side-effect free.  It scores already
materialized section metadata (skills, Kanban task blocks, project context
manifests, file-hint blocks, etc.) against task text, loaded-skill metadata,
and an optional active file path.  It does not read skill bodies, mutate the
system prompt, or create any parallel storage.

The integration entrypoint :func:`select_render_block_ids` adapts
``agent.instruction_surface.InstructionBlock`` sequences for the
disabled-by-default core prompt-assembly seam in ``agent.system_prompt``.
It is conservative by construction:

* Only an explicit allowlist of *optional* surfaces (``skill index`` and
  ``project/context`` files by default) may ever be dropped.  Every other
  block — identity, tool/Kanban guidance, tool-use enforcement, model
  operational guidance, environment/profile/platform hints, memory/user/
  external-memory/timestamp, caller system_message, active task context —
  is treated as a hard-contract always-include block.
* A block whose ``threat_status`` is ``"blocked"`` is always retained, so
  slicing can never silently erase blocked/injection-like evidence.
* When no task / skill / active-file signals are available, nothing is
  dropped (include-on-uncertainty).

The flag helpers (:func:`is_context_slicing_enabled`,
:func:`resolve_slice_budget`) mirror ``agent.uswarm_helpers`` so the feature
stays default-off and explicit-opt-in via config or the
``HERMES_CONTEXT_SLICING`` env var.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Mapping, Optional, Sequence

Surface = Literal["core", "kanban", "skill", "project", "file", "tool", "memory", "other"]
CachePolicy = Literal["stable", "session", "turn", "tool_result"]

TASK_KEYWORDS: Mapping[str, frozenset[str]] = {
    "kanban": frozenset({"kanban", "task", "handoff", "review-required", "blocked", "child", "card"}),
    "spike": frozenset({"spike", "prototype", "design", "feasibility", "proof"}),
    "skill": frozenset({"skill", "skills", "skill.md", "frontmatter", "index"}),
    "debugging": frozenset({"debug", "traceback", "failure", "rca", "regression"}),
    "review": frozenset({"review", "diff", "tests", "evidence", "quality"}),
    "github": frozenset({"github", "pr", "pull", "branch", "commit"}),
    "devops": frozenset({"deploy", "cron", "gateway", "service", "docker", "container"}),
}

EXTENSION_HINTS: Mapping[str, frozenset[str]] = {
    ".py": frozenset({"python", "pytest", "typing", "ruff", "tests"}),
    ".md": frozenset({"markdown", "docs", "provenance", "artifact"}),
    ".ts": frozenset({"typescript", "node", "frontend"}),
    ".tsx": frozenset({"typescript", "react", "frontend"}),
    ".js": frozenset({"javascript", "node", "frontend"}),
    ".jsx": frozenset({"javascript", "react", "frontend"}),
    ".json": frozenset({"json", "config", "schema"}),
    ".yaml": frozenset({"yaml", "config", "schema"}),
    ".yml": frozenset({"yaml", "config", "schema"}),
    ".toml": frozenset({"toml", "config"}),
    ".sh": frozenset({"shell", "bash", "scripts"}),
}

# Section ids that are always included by the pure scorer regardless of their
# ``always`` flag.  The integration adapter additionally forces every
# non-droppable block to ``always=True``; this set keeps the pure helper safe
# when used standalone with the spike fixtures.
ALWAYS_SECTION_IDS = frozenset({"core.safety", "kanban.task"})

# Optional, bulky, low-risk surfaces the first integration is allowed to drop.
# Everything else is hard-contract and always included.  Kept narrow on
# purpose: "if uncertain, include".
DEFAULT_DROPPABLE_BLOCK_IDS = frozenset(
    {
        "skill.index",
        "project.context_files",
        "project.AGENTS",
        "project.HERMES_MD",
        "project.CLAUDE",
        "project.CURSOR",
        "experimental.uswarm_context_pack",
    }
)
DEFAULT_DROPPABLE_SURFACES = frozenset({"skill_index", "project", "derived_context"})

_WORD_RE = re.compile(r"[A-Za-z0-9_.-]+")

_TRUTHY = {"1", "true", "yes", "on", "y"}
_FALSEY = {"0", "false", "no", "off", "n"}


@dataclass(frozen=True)
class ContextSection:
    """Compact metadata for one renderable context section."""

    id: str
    surface: Surface | str
    labels: frozenset[str] = field(default_factory=frozenset)
    authority: int = 0
    chars: int = 0
    always: bool = False
    cache_policy: CachePolicy | str = "session"
    source_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "labels", frozenset(_normalize_label(label) for label in self.labels if str(label).strip()))
        object.__setattr__(self, "authority", int(self.authority or 0))
        object.__setattr__(self, "chars", max(0, int(self.chars or 0)))

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "surface": self.surface,
            "labels": sorted(self.labels),
            "authority": self.authority,
            "chars": self.chars,
            "always": self.always,
            "cache_policy": self.cache_policy,
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class SkillContextMetadata:
    """Skill metadata sufficient for context-slicing signal extraction."""

    name: str
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)
    category: str | None = None
    source_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tags", frozenset(_normalize_label(tag) for tag in self.tags if str(tag).strip()))


@dataclass(frozen=True)
class SliceBudget:
    target_chars: int = 24_000
    max_sections: int = 8

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_chars", max(0, int(self.target_chars)))
        object.__setattr__(self, "max_sections", max(0, int(self.max_sections)))


@dataclass(frozen=True)
class SliceSignals:
    task: frozenset[str]
    skills: frozenset[str]
    active_file: frozenset[str]

    def is_empty(self) -> bool:
        return not (self.task or self.skills or self.active_file)

    def summary(self) -> dict[str, list[str]]:
        return {
            "task": sorted(self.task),
            "skills": sorted(self.skills),
            "active_file": sorted(self.active_file),
        }


@dataclass(frozen=True)
class ContextSliceDecision:
    selected: tuple[str, ...]
    dropped: tuple[str, ...]
    signals: SliceSignals
    scores: Mapping[str, float]
    total_chars: int
    reason: str = "scored"

    def summary(self) -> dict[str, object]:
        return {
            "selected": list(self.selected),
            "dropped": list(self.dropped),
            "signals": self.signals.summary(),
            "scores": dict(sorted(self.scores.items())),
            "total_chars": self.total_chars,
            "reason": self.reason,
        }


def words(text: str) -> frozenset[str]:
    """Return normalized word-ish tokens from free text."""

    return frozenset(_normalize_label(word) for word in _WORD_RE.findall(text or ""))


def derive_task_signals(title: str = "", body: str = "") -> frozenset[str]:
    haystack = words(f"{title}\n{body}")
    signals: set[str] = set()
    for task_type, keywords in TASK_KEYWORDS.items():
        overlap = haystack & keywords
        if overlap:
            signals.add(task_type)
            signals.update(overlap)
    return frozenset(sorted(signals))


def derive_skill_signals(skills: Iterable[SkillContextMetadata | Mapping[str, object]]) -> frozenset[str]:
    signals: set[str] = set()
    for skill in skills:
        meta = coerce_skill_metadata(skill)
        signals.update(words(meta.name))
        signals.update(words(meta.description))
        signals.update(meta.tags)
        if meta.category:
            signals.update(words(meta.category.replace("/", " ")))
    return frozenset(sorted(signals))


def derive_file_signals(active_file: str | Path | None) -> frozenset[str]:
    if not active_file:
        return frozenset()
    suffix = Path(str(active_file)).suffix.lower()
    return EXTENSION_HINTS.get(suffix, frozenset())


def derive_slice_signals(
    *,
    task_title: str = "",
    task_body: str = "",
    loaded_skills: Iterable[SkillContextMetadata | Mapping[str, object]] = (),
    active_file: str | Path | None = None,
) -> SliceSignals:
    return SliceSignals(
        task=derive_task_signals(task_title, task_body),
        skills=derive_skill_signals(loaded_skills),
        active_file=derive_file_signals(active_file),
    )


def score_section(section: ContextSection, signals: SliceSignals) -> float:
    labels = section.labels
    score = 100.0 if section.always or section.id in ALWAYS_SECTION_IDS else 0.0
    score += len(labels & signals.task) * 5
    score += len(labels & signals.skills) * 4
    score += len(labels & signals.active_file) * 3
    score += section.authority / 200
    if section.chars > 12_000 and not section.always:
        score -= 5
    return round(score, 2)


def slice_context_sections(
    sections: Iterable[ContextSection | Mapping[str, object]],
    *,
    task_title: str = "",
    task_body: str = "",
    loaded_skills: Iterable[SkillContextMetadata | Mapping[str, object]] = (),
    active_file: str | Path | None = None,
    budget: SliceBudget | Mapping[str, object] | None = None,
) -> ContextSliceDecision:
    """Rank and pack context sections into a deterministic decision manifest.

    Always sections are included even when they exceed the soft budget; optional
    sections must fit both remaining character and max-section limits.  Ties are
    resolved by section id for stable prompt-cache behavior.
    """

    normalized_sections = [coerce_section(section) for section in sections]
    normalized_budget = coerce_budget(budget)
    signals = derive_slice_signals(
        task_title=task_title,
        task_body=task_body,
        loaded_skills=loaded_skills,
        active_file=active_file,
    )
    return _pack(normalized_sections, signals, normalized_budget)


def _pack(
    sections: Sequence[ContextSection],
    signals: SliceSignals,
    budget: SliceBudget,
) -> ContextSliceDecision:
    scores = {section.id: score_section(section, signals) for section in sections}
    ordered = sorted(sections, key=lambda section: (-scores[section.id], section.id))

    selected: list[str] = []
    dropped: list[str] = []
    total_chars = 0
    for section in ordered:
        must_include = section.always or section.id in ALWAYS_SECTION_IDS
        fits_budget = (
            budget.max_sections > 0
            and len(selected) < budget.max_sections
            and total_chars + section.chars <= budget.target_chars
        )
        if must_include or fits_budget:
            selected.append(section.id)
            total_chars += section.chars
        else:
            dropped.append(section.id)

    return ContextSliceDecision(
        selected=tuple(selected),
        dropped=tuple(dropped),
        signals=signals,
        scores=scores,
        total_chars=total_chars,
    )


# ── Integration adapter (instruction-surface blocks) ───────────────────────


def _block_is_droppable(
    block: object,
    *,
    droppable_ids: frozenset[str],
    droppable_surfaces: frozenset[str],
) -> bool:
    """An optional block may be dropped only if it is on the allowlist AND not
    flagged as blocked/threat evidence.  Hard-contract surfaces never match."""

    if str(getattr(block, "threat_status", "")) == "blocked":
        return False
    block_id = str(getattr(block, "id", ""))
    surface = str(getattr(block, "surface", ""))
    return block_id in droppable_ids or surface in droppable_surfaces


def select_render_block_ids(
    blocks: Sequence[object],
    *,
    task_title: str = "",
    task_body: str = "",
    loaded_skills: Iterable[SkillContextMetadata | Mapping[str, object]] = (),
    active_file: str | Path | None = None,
    budget: SliceBudget | Mapping[str, object] | None = None,
    droppable_ids: Iterable[str] = DEFAULT_DROPPABLE_BLOCK_IDS,
    droppable_surfaces: Iterable[str] = DEFAULT_DROPPABLE_SURFACES,
) -> ContextSliceDecision:
    """Decide which ``InstructionBlock``-like blocks to render.

    Hard-contract blocks (everything not on the droppable allowlist) and any
    block whose ``threat_status`` is ``"blocked"`` are forced-include.  When no
    task/skill/active-file signal is present the decision keeps every block
    (include-on-uncertainty).  Render order is the caller's responsibility — the
    returned ``selected`` ids should be applied as a filter over the original
    block order so the prompt-cache prefix stays stable.
    """

    drop_ids = frozenset(droppable_ids)
    drop_surfaces = frozenset(droppable_surfaces)
    normalized_budget = coerce_budget(budget)
    signals = derive_slice_signals(
        task_title=task_title,
        task_body=task_body,
        loaded_skills=loaded_skills,
        active_file=active_file,
    )

    all_ids = tuple(str(getattr(block, "id", "")) for block in blocks)

    if signals.is_empty():
        return ContextSliceDecision(
            selected=all_ids,
            dropped=(),
            signals=signals,
            scores={block_id: 100.0 for block_id in all_ids},
            total_chars=sum(len(getattr(block, "content", "") or "") for block in blocks),
            reason="no_signal_include_all",
        )

    sections = [
        section_from_instruction_block(
            block,
            always=not _block_is_droppable(
                block, droppable_ids=drop_ids, droppable_surfaces=drop_surfaces
            ),
        )
        for block in blocks
    ]
    decision = _pack(sections, signals, normalized_budget)
    # Defensive: a malformed allowlist must never drop a hard-contract block.
    forced = {
        str(getattr(block, "id", ""))
        for block in blocks
        if not _block_is_droppable(block, droppable_ids=drop_ids, droppable_surfaces=drop_surfaces)
    }
    if forced - set(decision.selected):
        keep = [bid for bid in all_ids if bid in set(decision.selected) | forced]
        dropped = [bid for bid in decision.dropped if bid not in forced]
        decision = ContextSliceDecision(
            selected=tuple(keep),
            dropped=tuple(dropped),
            signals=decision.signals,
            scores=decision.scores,
            total_chars=decision.total_chars,
            reason="scored_forced_contract",
        )
    return decision


def coerce_section(section: ContextSection | Mapping[str, object]) -> ContextSection:
    if isinstance(section, ContextSection):
        return section
    labels = _string_values(section.get("labels", ()))
    return ContextSection(
        id=str(section.get("id", "")),
        surface=str(section.get("surface", "other")),
        labels=frozenset(labels),
        authority=_int_value(section.get("authority"), 0),
        chars=_int_value(section.get("chars"), 0),
        always=bool(section.get("always", False)),
        cache_policy=str(section.get("cache_policy", "session")),
        source_path=str(section["source_path"]) if section.get("source_path") else None,
    )


def coerce_skill_metadata(skill: SkillContextMetadata | Mapping[str, object]) -> SkillContextMetadata:
    if isinstance(skill, SkillContextMetadata):
        return skill
    tags = _string_values(skill.get("tags", ()))
    return SkillContextMetadata(
        name=str(skill.get("name", "")),
        description=str(skill.get("description", "")),
        tags=frozenset(tags),
        category=str(skill["category"]) if skill.get("category") else None,
        source_path=str(skill["source_path"]) if skill.get("source_path") else None,
    )


def coerce_budget(budget: SliceBudget | Mapping[str, object] | None) -> SliceBudget:
    if budget is None:
        return SliceBudget()
    if isinstance(budget, SliceBudget):
        return budget
    return SliceBudget(
        target_chars=_int_value(budget.get("target_chars"), 24_000),
        max_sections=_int_value(budget.get("max_sections"), 8),
    )


def section_from_instruction_block(block: object, *, always: bool | None = None) -> ContextSection:
    """Build section metadata from an ``agent.instruction_surface`` block.

    Kept duck-typed to avoid importing instruction-surface code and forming a
    prompt-builder dependency cycle.
    """

    content = getattr(block, "content", "") or ""
    block_id = str(getattr(block, "id", ""))
    labels = getattr(block, "labels", ()) or ()
    return ContextSection(
        id=block_id,
        surface=str(getattr(block, "surface", "other")),
        labels=frozenset(str(label) for label in labels),
        authority=int(getattr(block, "authority", 0) or 0),
        chars=len(content),
        always=(block_id in ALWAYS_SECTION_IDS) if always is None else always,
        cache_policy=str(getattr(block, "cache_policy", "session")),
        source_path=str(getattr(block, "path", "")) or None,
    )


def section_from_skill_metadata(skill: SkillContextMetadata | Mapping[str, object], *, chars: int = 0) -> ContextSection:
    meta = coerce_skill_metadata(skill)
    labels = set(words(meta.name)) | set(words(meta.description)) | set(meta.tags)
    if meta.category:
        labels.update(words(meta.category.replace("/", " ")))
    return ContextSection(
        id=f"skill.{meta.name}",
        surface="skill",
        labels=frozenset(labels),
        authority=800,
        chars=chars,
        cache_policy="session",
        source_path=meta.source_path,
    )


# ── Config / flag resolution (default-off, mirrors uswarm_helpers) ──────────


def _coerce_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUTHY:
            return True
        if lowered in _FALSEY:
            return False
    return default


def _nested(mapping: Optional[Mapping[str, object]], *keys: str) -> object:
    current: object = mapping or {}
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def is_context_slicing_enabled(config: Optional[Mapping[str, object]] = None) -> bool:
    """Return whether disabled-by-default context slicing is enabled.

    ``HERMES_CONTEXT_SLICING`` env var (if set) overrides config; otherwise the
    nested ``context_slicing.enabled`` config key is consulted.  Default off.
    """

    env_value = os.getenv("HERMES_CONTEXT_SLICING")
    if env_value is not None:
        return _coerce_bool(env_value, default=False)
    return _coerce_bool(_nested(config, "context_slicing", "enabled"), default=False)


def resolve_slice_budget(config: Optional[Mapping[str, object]] = None) -> SliceBudget:
    """Resolve the packing budget from config, falling back to defaults."""

    budget = _nested(config, "context_slicing", "budget")
    if isinstance(budget, Mapping):
        return coerce_budget(budget)
    return SliceBudget()


def _string_values(value: object) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return words(value)
    if isinstance(value, IterableABC):
        return frozenset(str(item) for item in value)
    return frozenset({str(value)})


def _int_value(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _normalize_label(value: object) -> str:
    return str(value).strip().lower().replace("_", "-")


__all__ = [
    "ContextSection",
    "ContextSliceDecision",
    "SkillContextMetadata",
    "SliceBudget",
    "SliceSignals",
    "DEFAULT_DROPPABLE_BLOCK_IDS",
    "DEFAULT_DROPPABLE_SURFACES",
    "derive_file_signals",
    "derive_skill_signals",
    "derive_slice_signals",
    "derive_task_signals",
    "is_context_slicing_enabled",
    "resolve_slice_budget",
    "score_section",
    "section_from_instruction_block",
    "section_from_skill_metadata",
    "select_render_block_ids",
    "slice_context_sections",
    "words",
]
