#!/usr/bin/env python3
"""Layered sync: openclaw-sync base + clawdbot-main fork overlays into vendor/openclaw-mirror."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SourceRoots:
    openclaw_sync: Path
    clawdbot_main: Path
    claw_root: Path


@dataclass(frozen=True)
class LayerPlan:
    extension: str
    base_root: Path
    overlay_root: Path
    target: Path


def load_layers_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _should_skip(path: Path, skip_dirs: set[str], skip_globs: tuple[str, ...]) -> bool:
    if path.name in skip_dirs:
        return True
    if any(part in skip_dirs for part in path.parts):
        return True
    rel = path.as_posix()
    return any(fnmatch.fnmatch(rel, pattern) for pattern in skip_globs)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(
    root: Path,
    *,
    skip_dirs: set[str],
    skip_globs: tuple[str, ...],
) -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file() or _should_skip(path, skip_dirs, skip_globs):
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = _file_hash(path)
    return files


def _glob_to_regex(pattern: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**", index):
            parts.append("(?:.*/)?")
            index += 2
            if index < len(pattern) and pattern[index] == "/":
                index += 1
            continue
        if pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
            continue
        start = index
        while index < len(pattern) and pattern[index] != "*":
            index += 1
        parts.append(re.escape(pattern[start:index]))
    return "^" + "".join(parts) + "$"


def _match_any(rel: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        if re.match(_glob_to_regex(pattern), rel):
            return True
    return False


def overlay_relpaths(
    extension: str,
    base_files: dict[str, str],
    overlay_files: dict[str, str],
    *,
    overlay_paths: list[str],
    prefer_overlay_for_changed: list[str],
) -> list[str]:
    selected: set[str] = set()
    for rel in overlay_files:
        if rel not in base_files:
            if overlay_paths and not _match_any(rel, overlay_paths):
                continue
            selected.add(rel)
    for rel in set(base_files) & set(overlay_files):
        if base_files[rel] == overlay_files[rel]:
            continue
        if _match_any(rel, prefer_overlay_for_changed):
            selected.add(rel)
        elif overlay_paths and _match_any(rel, overlay_paths):
            selected.add(rel)
    for pattern in overlay_paths:
        for rel in overlay_files:
            if _match_any(rel, (pattern,)):
                selected.add(rel)
    return sorted(selected)


def build_layer_plans(
    sources: SourceRoots,
    vendor_root: Path,
    config: dict,
) -> list[LayerPlan]:
    plans: list[LayerPlan] = []
    for name, spec in config.get("extensions", {}).items():
        base_kind = spec.get("base", "openclaw-sync")
        overlay_kind = spec.get("overlay", "clawdbot-main")
        base_parent = sources.openclaw_sync if base_kind == "openclaw-sync" else sources.clawdbot_main
        overlay_parent = sources.clawdbot_main if overlay_kind == "clawdbot-main" else sources.openclaw_sync
        base_root = base_parent / "extensions" / name
        overlay_root = overlay_parent / "extensions" / name
        if not base_root.is_dir():
            continue
        plans.append(
            LayerPlan(
                extension=name,
                base_root=base_root,
                overlay_root=overlay_root,
                target=vendor_root / "extensions" / name,
            ),
        )
    return plans


def diff_layered_plan(
    plan: LayerPlan,
    *,
    skip_dirs: set[str],
    skip_globs: tuple[str, ...],
    overlay_paths: list[str],
    prefer_overlay_for_changed: list[str],
) -> dict[str, object]:
    base_files = collect_files(plan.base_root, skip_dirs=skip_dirs, skip_globs=skip_globs)
    overlay_files = (
        collect_files(plan.overlay_root, skip_dirs=skip_dirs, skip_globs=skip_globs)
        if plan.overlay_root.is_dir()
        else {}
    )
    target_files = (
        collect_files(plan.target, skip_dirs=skip_dirs, skip_globs=skip_globs)
        if plan.target.is_dir()
        else {}
    )
    overlay_rels = overlay_relpaths(
        plan.extension,
        base_files,
        overlay_files,
        overlay_paths=overlay_paths,
        prefer_overlay_for_changed=prefer_overlay_for_changed,
    )
    merged: dict[str, str] = dict(base_files)
    for rel in overlay_rels:
        if rel in overlay_files:
            merged[rel] = overlay_files[rel]
    added = sorted(set(merged) - set(target_files))
    removed = sorted(set(target_files) - set(merged))
    changed = sorted(rel for rel in set(merged) & set(target_files) if merged[rel] != target_files[rel])
    return {
        "extension": plan.extension,
        "base": str(plan.base_root),
        "overlay": str(plan.overlay_root),
        "target": str(plan.target),
        "base_file_count": len(base_files),
        "overlay_file_count": len(overlay_files),
        "overlay_applied_count": len(overlay_rels),
        "overlay_relpaths_sample": overlay_rels[:40],
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def apply_layered_plan(
    plan: LayerPlan,
    *,
    skip_dirs: set[str],
    skip_globs: tuple[str, ...],
    overlay_paths: list[str],
    prefer_overlay_for_changed: list[str],
) -> None:
    if plan.target.exists():
        shutil.rmtree(plan.target)
    shutil.copytree(
        plan.base_root,
        plan.target,
        ignore=shutil.ignore_patterns(*skip_dirs),
        dirs_exist_ok=False,
    )
    if not plan.overlay_root.is_dir():
        return
    base_files = collect_files(plan.base_root, skip_dirs=skip_dirs, skip_globs=skip_globs)
    overlay_files = collect_files(plan.overlay_root, skip_dirs=skip_dirs, skip_globs=skip_globs)
    for rel in overlay_relpaths(
        plan.extension,
        base_files,
        overlay_files,
        overlay_paths=overlay_paths,
        prefer_overlay_for_changed=prefer_overlay_for_changed,
    ):
        src = plan.overlay_root / rel
        if not src.is_file():
            continue
        dst = plan.target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
