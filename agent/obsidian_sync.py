#!/usr/bin/env python3
"""Shared Obsidian sync helpers for Hermes-managed vault content."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

MANAGED_FOLDERS = [
    "Wiki",
    "Notes",
    "People",
    "Projects",
    "Decisions",
    "Episodes",
    "Research",
    "Assets",
    "Canvas",
]

ENTITY_FOLDER_MAP = {
    "note": "Notes",
    "person": "People",
    "project": "Projects",
    "decision": "Decisions",
    "episode": "Episodes",
    "wiki": "Wiki",
    "research": "Research",
    "asset": "Assets",
    "canvas": "Canvas",
}


def expand_vault_path(vault_path: Optional[str]) -> Optional[Path]:
    if not vault_path:
        return None
    return Path(os.path.expanduser(vault_path))


def get_managed_root(vault_path: Optional[str], agent_prefix: str) -> Optional[Path]:
    expanded = expand_vault_path(vault_path)
    if not expanded:
        return None
    return expanded / agent_prefix


def ensure_managed_structure(vault_path: Optional[str], agent_prefix: str) -> Optional[Path]:
    managed_root = get_managed_root(vault_path, agent_prefix)
    if not managed_root:
        return None
    managed_root.mkdir(parents=True, exist_ok=True)
    for folder in MANAGED_FOLDERS:
        (managed_root / folder).mkdir(parents=True, exist_ok=True)
    return managed_root


def get_entity_dir(vault_path: Optional[str], agent_prefix: str, entity_type: str) -> Optional[Path]:
    managed_root = ensure_managed_structure(vault_path, agent_prefix)
    if not managed_root:
        return None
    folder = ENTITY_FOLDER_MAP.get(entity_type, "Notes")
    path = managed_root / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return {}, content
    fm_text = match.group(1)
    body = content[match.end():]
    try:
        return yaml.safe_load(fm_text) or {}, body
    except Exception:
        return {}, body


def extract_markdown_metadata(content: str) -> Dict[str, Any]:
    wiki_links = [match.group(1).strip() for match in re.finditer(r"\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", content)]
    embeds = [match.group(1).strip() for match in re.finditer(r"!\[\[([^\]]+)\]\]", content)]
    markdown_links = [match.group(1).strip() for match in re.finditer(r"!?\\[[^\\]]*\\]\\(([^)]+)\\)", content)]
    tags = [match.group(2) for match in re.finditer(r"(^|\s)#([A-Za-z0-9/_-]+)", content)]
    task_count = len(re.findall(r"^\s*[-*]\s+\[[ xX]\]", content, re.MULTILINE))
    callout_count = len(re.findall(r"^\s*>\s*\[[!][A-Z0-9_-]+\]", content, re.MULTILINE))
    dataview_fields = [match.group(1) for match in re.finditer(r"^\s*([A-Za-z0-9_-]+)::\s+(.+)$", content, re.MULTILINE)]
    return {
        "wiki_links": wiki_links,
        "embeds": embeds,
        "markdown_links": markdown_links,
        "tags": tags,
        "task_count": task_count,
        "callout_count": callout_count,
        "dataview_fields": dataview_fields,
    }


def extract_canvas_refs(content: str) -> List[Dict[str, Any]]:
    try:
        parsed = json.loads(content)
    except Exception:
        return []

    refs: List[Dict[str, Any]] = []
    for node in parsed.get("nodes", []):
        if not isinstance(node, dict):
            continue
        target_path = node.get("file") or node.get("path")
        refs.append({
            "node_id": node.get("id"),
            "node_type": node.get("type", "unknown"),
            "target_path": target_path if isinstance(target_path, str) else None,
            "metadata": node,
        })
    return refs
