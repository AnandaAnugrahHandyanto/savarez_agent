"""Parsed skill metadata for prompt rendering and skill discovery tools."""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent.skill_utils import (
    extract_skill_conditions,
    extract_skill_description,
    get_all_skills_dirs,
    get_disabled_skill_names,
    iter_skill_index_files,
    parse_frontmatter,
    skill_matches_platform,
)
from hermes_constants import get_hermes_home, get_skills_dir
from utils import atomic_json_write

logger = logging.getLogger(__name__)

SNAPSHOT_VERSION = 2
_INVENTORY_CACHE_MAX = 8
_INVENTORY_CACHE: OrderedDict[tuple, "Inventory"] = OrderedDict()
_INVENTORY_LOCK = threading.Lock()


@dataclass(frozen=True)
class SkillEntry:
    name: str
    skill_name: str
    category: str
    description: str
    priority: str = "normal"
    platforms: tuple[str, ...] = ()
    conditions: dict = field(default_factory=dict)
    source: str = "local"


@dataclass(frozen=True)
class Inventory:
    entries: tuple[SkillEntry, ...]
    category_descriptions: dict[str, str]


def normalize_priority(value: object) -> str:
    priority = str(value or "normal").strip().lower()
    return priority if priority in ("critical", "normal") else "normal"


def _snapshot_path() -> Path:
    return get_hermes_home() / ".skills_prompt_snapshot.json"


def _build_manifest(skills_dir: Path) -> dict[str, list[int]]:
    manifest: dict[str, list[int]] = {}
    for filename in ("SKILL.md", "DESCRIPTION.md"):
        for path in iter_skill_index_files(skills_dir, filename):
            try:
                st = path.stat()
            except OSError:
                continue
            manifest[str(path.relative_to(skills_dir))] = [st.st_mtime_ns, st.st_size]
    return manifest


def _load_snapshot(skills_dir: Path) -> Optional[dict]:
    path = _snapshot_path()
    if not path.exists():
        return None
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("version") != SNAPSHOT_VERSION:
        return None
    if snapshot.get("manifest") != _build_manifest(skills_dir):
        return None
    return snapshot


def _write_snapshot(
    skills_dir: Path,
    manifest: dict[str, list[int]],
    entries: list[SkillEntry],
    category_descriptions: dict[str, str],
) -> None:
    payload = {
        "version": SNAPSHOT_VERSION,
        "manifest": manifest,
        "skills": [
            {
                "name": entry.name,
                "skill_name": entry.skill_name,
                "category": entry.category,
                "description": entry.description,
                "priority": entry.priority,
                "platforms": list(entry.platforms),
                "conditions": entry.conditions,
                "source": entry.source,
            }
            for entry in entries
        ],
        "category_descriptions": category_descriptions,
    }
    try:
        atomic_json_write(_snapshot_path(), payload)
    except Exception as exc:
        logger.debug("Could not write skills snapshot: %s", exc)


def _entry_from_snapshot(raw: dict) -> Optional[SkillEntry]:
    try:
        name = str(raw.get("name") or raw.get("frontmatter_name") or raw.get("skill_name") or "")
        skill_name = str(raw.get("skill_name") or name)
        if not name:
            return None
        platforms = raw.get("platforms") or ()
        if isinstance(platforms, str):
            platforms = (platforms,)
        return SkillEntry(
            name=name,
            skill_name=skill_name,
            category=str(raw.get("category") or "general"),
            description=str(raw.get("description") or ""),
            priority=normalize_priority(raw.get("priority")),
            platforms=tuple(str(p).strip() for p in platforms if str(p).strip()),
            conditions=raw.get("conditions") or {},
            source=str(raw.get("source") or "local"),
        )
    except Exception:
        return None


def entry_from_skill_file(skill_file: Path, base_dir: Path, *, source: str) -> Optional[SkillEntry]:
    try:
        raw = skill_file.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter(raw)
    except Exception as exc:
        logger.warning("Failed to parse skill file %s: %s", skill_file, exc)
        frontmatter = {}

    try:
        rel = skill_file.relative_to(base_dir)
    except ValueError:
        rel = Path(skill_file.name)
    parts = rel.parts
    if len(parts) >= 2:
        skill_name = parts[-2]
        category = "/".join(parts[:-2]) if len(parts) > 2 else parts[0]
    else:
        category = "general"
        skill_name = skill_file.parent.name

    platforms = frontmatter.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]

    return SkillEntry(
        name=str(frontmatter.get("name", skill_name)),
        skill_name=skill_name,
        category=category,
        description=extract_skill_description(frontmatter),
        priority=normalize_priority(frontmatter.get("priority")),
        platforms=tuple(str(p).strip() for p in platforms if str(p).strip()),
        conditions=extract_skill_conditions(frontmatter),
        source=source,
    )


def _read_category_descriptions(base_dir: Path) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for desc_file in iter_skill_index_files(base_dir, "DESCRIPTION.md"):
        try:
            content = desc_file.read_text(encoding="utf-8")
            frontmatter, _ = parse_frontmatter(content)
            cat_desc = frontmatter.get("description")
            if not cat_desc:
                continue
            rel = desc_file.relative_to(base_dir)
            category = "/".join(rel.parts[:-1]) if len(rel.parts) > 1 else "general"
            descriptions[category] = str(cat_desc).strip().strip("'\"")
        except Exception as exc:
            logger.debug("Could not read skill description %s: %s", desc_file, exc)
    return descriptions


def _skill_should_show(
    conditions: dict,
    available_tools: set[str] | None,
    available_toolsets: set[str] | None,
) -> bool:
    if available_tools is None and available_toolsets is None:
        return True

    at = available_tools or set()
    ats = available_toolsets or set()
    for ts in conditions.get("fallback_for_toolsets", []):
        if ts in ats:
            return False
    for tool in conditions.get("fallback_for_tools", []):
        if tool in at:
            return False
    for ts in conditions.get("requires_toolsets", []):
        if ts not in ats:
            return False
    for tool in conditions.get("requires_tools", []):
        if tool not in at:
            return False
    return True


def _entry_allowed(
    entry: SkillEntry,
    disabled: set[str],
    available_tools: set[str] | None,
    available_toolsets: set[str] | None,
) -> bool:
    if not skill_matches_platform({"platforms": list(entry.platforms)}):
        return False
    if entry.name in disabled or entry.skill_name in disabled:
        return False
    return _skill_should_show(entry.conditions, available_tools, available_toolsets)


def load_inventory(
    available_tools: set[str] | None = None,
    available_toolsets: set[str] | None = None,
    disabled_names: set[str] | None = None,
) -> Inventory:
    """Return parsed, filtered skill metadata."""
    skills_dir = get_skills_dir()
    all_dirs = get_all_skills_dirs()
    external_dirs = all_dirs[1:] if len(all_dirs) > 1 else []

    if not skills_dir.exists() and not external_dirs:
        return Inventory(entries=(), category_descriptions={})

    from gateway.session_context import get_session_env

    platform_hint = (
        os.environ.get("HERMES_PLATFORM")
        or get_session_env("HERMES_SESSION_PLATFORM")
        or ""
    )
    disabled = disabled_names if disabled_names is not None else get_disabled_skill_names()
    cache_key = (
        str(skills_dir.resolve()),
        tuple(str(d) for d in external_dirs),
        tuple(sorted(str(t) for t in (available_tools or set()))),
        tuple(sorted(str(ts) for ts in (available_toolsets or set()))),
        platform_hint,
        tuple(sorted(disabled)),
    )
    with _INVENTORY_LOCK:
        cached = _INVENTORY_CACHE.get(cache_key)
        if cached is not None:
            _INVENTORY_CACHE.move_to_end(cache_key)
            return cached

    entries: list[SkillEntry] = []
    category_descriptions: dict[str, str] = {}

    snapshot = _load_snapshot(skills_dir) if skills_dir.exists() else None
    if snapshot is not None:
        for raw in snapshot.get("skills", []):
            if not isinstance(raw, dict):
                continue
            entry = _entry_from_snapshot(raw)
            if entry is not None:
                entries.append(entry)
        category_descriptions.update(
            {
                str(key): str(value)
                for key, value in (snapshot.get("category_descriptions") or {}).items()
            }
        )
    elif skills_dir.exists():
        for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
            entry = entry_from_skill_file(skill_file, skills_dir, source="local")
            if entry is not None:
                entries.append(entry)
        category_descriptions.update(_read_category_descriptions(skills_dir))
        _write_snapshot(
            skills_dir,
            _build_manifest(skills_dir),
            entries,
            category_descriptions,
        )

    seen_names = {entry.name for entry in entries}
    for ext_dir in external_dirs:
        if not ext_dir.exists():
            continue
        for skill_file in iter_skill_index_files(ext_dir, "SKILL.md"):
            entry = entry_from_skill_file(skill_file, ext_dir, source="external")
            if entry is None or entry.name in seen_names:
                continue
            entries.append(entry)
            seen_names.add(entry.name)
        for category, description in _read_category_descriptions(ext_dir).items():
            category_descriptions.setdefault(category, description)

    filtered = tuple(
        entry
        for entry in entries
        if _entry_allowed(entry, disabled, available_tools, available_toolsets)
    )
    inventory = Inventory(
        entries=filtered,
        category_descriptions=dict(category_descriptions),
    )

    with _INVENTORY_LOCK:
        _INVENTORY_CACHE[cache_key] = inventory
        _INVENTORY_CACHE.move_to_end(cache_key)
        while len(_INVENTORY_CACHE) > _INVENTORY_CACHE_MAX:
            _INVENTORY_CACHE.popitem(last=False)
    return inventory


def clear_inventory_cache(*, clear_snapshot: bool = False) -> None:
    with _INVENTORY_LOCK:
        _INVENTORY_CACHE.clear()
    if clear_snapshot:
        try:
            _snapshot_path().unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("Could not remove skills snapshot: %s", exc)
