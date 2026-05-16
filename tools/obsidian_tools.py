#!/usr/bin/env python3
"""Obsidian tools.

Structured task reads for Markdown task lists in an Obsidian vault.  This is
intentionally read-only: agents should use it instead of raw-reading Tasks.md
when they need a compact, line-addressable view of the user's task list.
"""

from __future__ import annotations

import json
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

from hermes_constants import get_default_hermes_root
from tools.registry import registry

_TASK_RE = re.compile(r"^(?P<indent>\s*)[-*+]\s+\[(?P<marker>.)\]\s*(?P<text>.*)$")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_ISO_DATE_RE = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
_DUE_MARKERS = ("📅", "due", "due:", "due::")

_MARKER_STATUS = {
    " ": "open",
    "": "open",
    "/": "active",
    ">": "active",
    "x": "done",
    "X": "done",
    "-": "cancelled",
    "~": "cancelled",
    "_": "cancelled",
}

_STATUSES = ("open", "active", "done", "cancelled")


def check_obsidian_requirements() -> bool:
    """The reader uses only the local filesystem; no external dependency."""
    return True


def _load_obsidian_config_path() -> str | None:
    """Best-effort config lookup without making the tool import fragile."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        obsidian_cfg = cfg.get("obsidian") or {}
        if isinstance(obsidian_cfg, dict):
            value = obsidian_cfg.get("vault_path") or obsidian_cfg.get("path")
            if value:
                return str(value)
    except Exception:
        return None
    return None


def _candidate_vault_paths() -> list[Path]:
    candidates: list[Path] = []

    env_path = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    cfg_path = _load_obsidian_config_path()
    if cfg_path:
        candidates.append(Path(cfg_path).expanduser())

    # In Hermes profile mode HOME may be profile-scoped
    # (~/.hermes/profiles/<name>/home). The shared Hermes root still lets us
    # recover the real OS home in standard installs: /home/user/.hermes ->
    # /home/user.
    try:
        root = get_default_hermes_root()
        if root.name == ".hermes":
            candidates.append(root.parent / "Documents" / "Obsidian Vault")
    except Exception:
        pass

    candidates.append(Path.home() / "Documents" / "Obsidian Vault")

    # Preserve order while dropping duplicates.
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def _resolve_vault() -> Path:
    candidates = _candidate_vault_paths()
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    # Return the highest-precedence candidate for a useful error message.
    if candidates:
        return candidates[0].resolve()
    return (Path.home() / "Documents" / "Obsidian Vault").resolve()


def _safe_note_path(vault: Path, path: str) -> Path:
    requested = (path or "Tasks.md").strip() or "Tasks.md"
    raw = Path(requested).expanduser()
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (vault / raw).resolve()

    try:
        candidate.relative_to(vault)
    except ValueError:
        raise ValueError(f"path must stay inside Obsidian vault: {requested}")
    return candidate


def _status_for_marker(marker: str) -> str:
    return _MARKER_STATUS.get(marker, "open")


def _extract_due(text: str) -> str | None:
    """Extract a likely due date from common Obsidian Tasks syntax."""
    match = _ISO_DATE_RE.search(text)
    if not match:
        return None
    # Prefer dates near a due marker, but fall back to the first ISO date so
    # historical task notes remain useful rather than returning nothing.
    lower = text.lower()
    if any(marker in text or marker in lower for marker in _DUE_MARKERS):
        return match.group(1)
    return match.group(1)


def _new_counts() -> dict[str, int]:
    return {status: 0 for status in _STATUSES}


def _parse_tasks(content: str, *, include_done: bool) -> tuple[list[dict[str, Any]], dict[str, int], OrderedDict[str, dict[str, int]], int]:
    tasks: list[dict[str, Any]] = []
    status_counts = _new_counts()
    section_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    current_section = "(top)"
    current_level = 0
    total_tasks = 0

    for line_no, line in enumerate(content.splitlines(), start=1):
        heading = _HEADING_RE.match(line)
        if heading:
            current_level = len(heading.group("hashes"))
            current_section = heading.group("title").strip()
            section_counts.setdefault(current_section, _new_counts())
            continue

        match = _TASK_RE.match(line)
        if not match:
            continue

        total_tasks += 1
        marker = match.group("marker")
        text = match.group("text").strip()
        status = _status_for_marker(marker)
        if status not in status_counts:
            status = "open"
        status_counts[status] += 1
        section_counts.setdefault(current_section, _new_counts())[status] += 1

        if not include_done and status in {"done", "cancelled"}:
            continue

        tasks.append(
            {
                "line": line_no,
                "section": current_section,
                "heading_level": current_level,
                "status": status,
                "marker": marker,
                "text": text,
                "due": _extract_due(text),
            }
        )

    return tasks, status_counts, section_counts, total_tasks


def obsidian_read_tasks_tool(path: str = "Tasks.md", include_done: bool = False, limit: int = 50) -> str:
    """Read Markdown tasks from an Obsidian note as structured JSON."""
    try:
        vault = _resolve_vault()
        note_path = _safe_note_path(vault, path)
        if not vault.exists():
            return json.dumps(
                {
                    "error": f"Obsidian vault not found: {vault}",
                    "path": path or "Tasks.md",
                    "tasks": [],
                },
                ensure_ascii=False,
            )
        if not note_path.exists() or not note_path.is_file():
            rel = str(note_path.relative_to(vault)) if note_path.is_relative_to(vault) else str(note_path)
            return json.dumps(
                {
                    "error": f"Obsidian note not found: {rel}",
                    "path": rel,
                    "tasks": [],
                },
                ensure_ascii=False,
            )

        content = note_path.read_text(encoding="utf-8")
        tasks, status_counts, section_counts, total_tasks = _parse_tasks(content, include_done=bool(include_done))

        try:
            max_items = int(limit)
        except (TypeError, ValueError):
            max_items = 50
        if max_items < 0:
            max_items = 0

        returned = tasks[:max_items]
        rel_path = str(note_path.relative_to(vault))
        active_tasks = status_counts["open"] + status_counts["active"]
        matched_tasks = len(tasks)
        result = {
            "path": rel_path,
            "include_done": bool(include_done),
            "limit": max_items,
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "matched_tasks": matched_tasks,
            "returned_tasks": len(returned),
            "truncated": matched_tasks > len(returned),
            "status_counts": status_counts,
            "section_counts": [
                {"section": section, **counts}
                for section, counts in section_counts.items()
                if any(counts.values())
            ],
            "summary": (
                f"{len(returned)} of {matched_tasks} matching tasks returned from {rel_path}; "
                f"{active_tasks} active/open tasks, {status_counts['done']} done, "
                f"{status_counts['cancelled']} cancelled."
            ),
            "tasks": returned,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc), "path": path or "Tasks.md", "tasks": []}, ensure_ascii=False)


OBSIDIAN_READ_TASKS_SCHEMA = {
    "name": "obsidian_read_tasks",
    "description": (
        "Read Markdown tasks from an Obsidian note as structured JSON. Use this "
        "instead of raw-reading Tasks.md when you need Charlie's task list. By "
        "default it returns only active/open tasks, grouped with section and line metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Vault-relative note path to parse. Defaults to Tasks.md.",
                "default": "Tasks.md",
            },
            "include_done": {
                "type": "boolean",
                "description": "Include done and cancelled tasks in the returned tasks array.",
                "default": False,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of matching tasks to return.",
                "default": 50,
                "minimum": 0,
            },
        },
        "required": [],
    },
}


registry.register(
    name="obsidian_read_tasks",
    toolset="obsidian",
    schema=OBSIDIAN_READ_TASKS_SCHEMA,
    handler=lambda args, **kw: obsidian_read_tasks_tool(
        path=args.get("path", "Tasks.md"),
        include_done=args.get("include_done", False),
        limit=args.get("limit", 50),
    ),
    check_fn=check_obsidian_requirements,
    emoji="📝",
)
