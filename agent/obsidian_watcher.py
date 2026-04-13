#!/usr/bin/env python3
"""Polling-based Obsidian watcher for Hermes-managed vault content."""

from __future__ import annotations

import logging
import mimetypes
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agent.obsidian_sync import (
    compute_content_hash,
    ensure_managed_structure,
    extract_canvas_refs,
    extract_markdown_metadata,
    get_managed_root,
    parse_frontmatter,
)
from hermes_state import SessionDB

logger = logging.getLogger(__name__)


MANAGED_ENTITY_MAP = {
    "Wiki": "wiki",
    "Notes": "note",
    "People": "person",
    "Projects": "project",
    "Decisions": "decision",
    "Episodes": "episode",
    "Research": "research",
    "Assets": "asset",
    "Canvas": "canvas",
}


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("/")


def _walk_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    results: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".obsidian", ".git"} for part in path.parts):
            continue
        results.append(path)
    return results


def _resolve_reference(base_dir: Path, reference: str) -> Path:
    normalized = reference.replace("file://", "").split("#", 1)[0].strip()
    if not normalized:
        return base_dir
    ref_path = Path(normalized)
    if ref_path.is_absolute():
        return ref_path
    return (base_dir / ref_path).resolve()


def _extract_attachment_refs(file_path: Path, content: str, vault_path: Path) -> List[Dict[str, Any]]:
    metadata = extract_markdown_metadata(content)
    refs: List[Dict[str, Any]] = []
    for target in list(metadata.get("embeds", [])) + list(metadata.get("markdown_links", [])):
        if not isinstance(target, str):
            continue
        resolved = _resolve_reference(file_path.parent, target)
        exists = resolved.exists()
        try:
            target_path = _normalize_path(str(resolved.relative_to(vault_path)))
        except Exception:
            target_path = _normalize_path(target)
        refs.append({
            "target_path": target_path,
            "target_type": "embed" if target in metadata.get("embeds", []) else "markdown",
            "exists": exists,
            "mime_type": mimetypes.guess_type(target)[0],
        })
    return refs


def _map_managed_metadata(agent_prefix: str, managed_root: Path, file_path: Path) -> Tuple[str, str, Optional[str], Optional[str]]:
    managed_relative_path = _normalize_path(str(file_path.relative_to(managed_root)))
    vault_relative_path = _normalize_path(f"{agent_prefix}/{managed_relative_path}")
    segments = managed_relative_path.split("/")
    top = segments[0] if segments else ""
    entity_type = MANAGED_ENTITY_MAP.get(top)
    wiki_page_type = segments[1] if top == "Wiki" and len(segments) > 1 else None
    return managed_relative_path, vault_relative_path, entity_type, wiki_page_type


class ObsidianSyncWatcher:
    """Continuously reconcile Hermes-managed Obsidian content into state.db."""

    def __init__(
        self,
        db: SessionDB,
        vault_path: str,
        agent_prefix: str = "Hermes",
        poll_interval: float = 2.5,
    ):
        self.db = db
        self.vault_path = Path(os.path.expanduser(vault_path))
        self.agent_prefix = agent_prefix
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="obsidian-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        logger.info("Starting Obsidian watcher for %s", self.vault_path)
        self.db.upsert_obsidian_sync_checkpoint(
            "obsidian-watcher",
            last_started_at=time.time(),
            last_status="running",
            last_error=None,
            last_scan_count=0,
            last_change_count=0,
        )
        while not self._stop_event.wait(self.poll_interval):
            try:
                self.sync_once()
            except Exception as exc:
                logger.warning("Obsidian watcher sync failed: %s", exc)
                self.db.upsert_obsidian_sync_checkpoint(
                    "obsidian-watcher",
                    last_completed_at=time.time(),
                    last_status="error",
                    last_error=str(exc),
                )
                self.db.record_obsidian_sync_event(
                    event_type="watcher_sync",
                    direction="vault_watch",
                    status="error",
                    detail=str(exc),
                )
        self.db.upsert_obsidian_sync_checkpoint(
            "obsidian-watcher",
            last_completed_at=time.time(),
            last_status="stopped",
            last_error=None,
        )
        logger.info("Stopped Obsidian watcher")

    def sync_once(self) -> None:
        managed_root = ensure_managed_structure(str(self.vault_path), self.agent_prefix)
        if not managed_root:
            return

        existing_rows = {
            row["vault_relative_path"]: row
            for row in self.db.list_obsidian_managed_files(include_tombstoned=False)
        }
        seen: Set[str] = set()
        uuid_to_path: Dict[str, str] = {}
        scan_count = 0
        change_count = 0
        started_at = time.time()

        for file_path in _walk_files(managed_root):
            scan_count += 1
            managed_relative_path, vault_relative_path, entity_type, wiki_page_type = _map_managed_metadata(
                self.agent_prefix,
                managed_root,
                file_path,
            )
            seen.add(vault_relative_path)
            existing = existing_rows.get(vault_relative_path)
            ext = file_path.suffix.lower()
            is_text = ext in {".md", ".canvas", ".txt", ".json"}
            raw = file_path.read_text(encoding="utf-8") if is_text else None
            content_hash = compute_content_hash(raw if raw is not None else file_path.read_bytes().hex())
            stat = file_path.stat()

            uuid = None
            metadata: Dict[str, Any] = {}
            if raw is not None and ext == ".md":
                frontmatter, _body = parse_frontmatter(raw)
                uuid = frontmatter.get("uuid") if isinstance(frontmatter.get("uuid"), str) else None
                refs = _extract_attachment_refs(file_path, raw, self.vault_path)
                self.db.replace_obsidian_attachment_refs(vault_relative_path, refs)
                md_meta = extract_markdown_metadata(raw)
                metadata = {
                    "frontmatter": frontmatter,
                    "wiki_link_count": len(md_meta.get("wiki_links", [])),
                    "embed_count": len(md_meta.get("embeds", [])),
                    "markdown_link_count": len(md_meta.get("markdown_links", [])),
                    "tag_count": len(md_meta.get("tags", [])),
                    "task_count": md_meta.get("task_count", 0),
                    "callout_count": md_meta.get("callout_count", 0),
                    "dataview_fields": md_meta.get("dataview_fields", []),
                }
            elif raw is not None and ext == ".canvas":
                refs = []
                for ref in extract_canvas_refs(raw):
                    target_path = ref.get("target_path")
                    resolved = _resolve_reference(file_path.parent, target_path) if isinstance(target_path, str) else None
                    refs.append({
                        **ref,
                        "target_path": _normalize_path(target_path) if isinstance(target_path, str) else None,
                        "broken": bool(target_path and resolved and not resolved.exists()),
                    })
                self.db.replace_obsidian_canvas_refs(vault_relative_path, refs)
                metadata = {"node_count": len(refs)}

            if existing is None or existing.get("content_hash") != content_hash or existing.get("tombstoned"):
                change_count += 1
                revision_id = self.db.record_obsidian_file_revision(
                    vault_relative_path=vault_relative_path,
                    content_hash=content_hash,
                    content_text=raw if raw is not None else None,
                    source="vault_to_db",
                    actor="obsidian-watcher",
                    metadata={"path": vault_relative_path, "entity_type": entity_type, "file_ext": ext},
                )
                self.db.upsert_obsidian_managed_file(
                    vault_relative_path=vault_relative_path,
                    managed_relative_path=managed_relative_path,
                    uuid=uuid,
                    entity_type=entity_type,
                    wiki_page_type=wiki_page_type,
                    file_ext=ext,
                    content_hash=content_hash,
                    last_vault_mtime=stat.st_mtime,
                    last_vault_size=stat.st_size,
                    last_db_revision_id=revision_id,
                    last_sync_direction="vault_to_db",
                    sync_status="synced",
                    conflict_state="none",
                    source_origin="managed",
                    tombstoned=False,
                    metadata=metadata,
                )
                self.db.record_obsidian_sync_event(
                    event_type="watcher_sync_file",
                    path=vault_relative_path,
                    direction="vault_to_db",
                    status="ok",
                    detail=f"Reconciled {vault_relative_path}",
                    metadata={"entity_type": entity_type, "hash": content_hash},
                )

            if uuid:
                other_path = uuid_to_path.get(uuid)
                if other_path and other_path != vault_relative_path:
                    already_open = any(
                        conflict.get("conflict_type") == "duplicate_uuid"
                        for conflict in self.db.list_open_obsidian_conflicts(vault_relative_path)
                    )
                    if not already_open:
                        self.db.record_obsidian_conflict(
                            vault_relative_path=vault_relative_path,
                            conflict_type="duplicate_uuid",
                            summary=f"Duplicate Obsidian UUID {uuid} detected for {vault_relative_path} and {other_path}.",
                            uuid=uuid,
                            entity_type=entity_type,
                        )
                    self.db.upsert_obsidian_managed_file(
                        vault_relative_path=vault_relative_path,
                        managed_relative_path=managed_relative_path,
                        uuid=uuid,
                        entity_type=entity_type,
                        wiki_page_type=wiki_page_type,
                        file_ext=ext,
                        content_hash=content_hash,
                        last_vault_mtime=stat.st_mtime,
                        last_vault_size=stat.st_size,
                        last_db_revision_id=existing.get("last_db_revision_id") if existing else None,
                        last_sync_direction="vault_to_db",
                        sync_status="conflict",
                        conflict_state="open",
                        source_origin="managed",
                        tombstoned=False,
                        metadata=metadata,
                    )
                else:
                    uuid_to_path[uuid] = vault_relative_path

        for vault_relative_path, row in existing_rows.items():
            if vault_relative_path in seen:
                continue
            change_count += 1
            self.db.upsert_obsidian_managed_file(
                vault_relative_path=vault_relative_path,
                managed_relative_path=row.get("managed_relative_path") or row.get("managed_relative_path".replace("_", "")),
                uuid=row.get("uuid"),
                entity_type=row.get("entity_type"),
                wiki_page_type=row.get("wiki_page_type"),
                file_ext=row.get("file_ext"),
                content_hash=row.get("content_hash"),
                last_vault_mtime=row.get("last_vault_mtime"),
                last_vault_size=row.get("last_vault_size"),
                last_db_revision_id=row.get("last_db_revision_id"),
                last_sync_direction="vault_to_db",
                sync_status="deleted",
                conflict_state="none",
                source_origin=row.get("source_origin", "managed"),
                tombstoned=True,
                metadata=row.get("metadata", {}),
            )
            self.db.record_obsidian_sync_event(
                event_type="watcher_tombstone",
                path=vault_relative_path,
                direction="vault_to_db",
                status="ok",
                detail=f"Marked {vault_relative_path} as deleted",
            )

        managed_root_norm = _normalize_path(str(managed_root.resolve()))
        for path in _walk_files(self.vault_path):
            normalized_abs = _normalize_path(str(path.resolve()))
            if normalized_abs.startswith(managed_root_norm):
                continue
            if path.suffix.lower() not in {".md", ".canvas"}:
                continue
            content = path.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(content)
            rel = _normalize_path(str(path.relative_to(self.vault_path)))
            title = None
            if isinstance(frontmatter.get("title"), str) and frontmatter.get("title"):
                title = str(frontmatter["title"])
            if not title:
                title = next((line.lstrip("# ").strip() for line in body.splitlines() if line.strip()), path.stem)
            self.db.upsert_obsidian_import_candidate(
                vault_relative_path=rel,
                title=title,
                file_uuid=frontmatter.get("uuid") if isinstance(frontmatter.get("uuid"), str) else None,
                content_hash=compute_content_hash(content),
                last_vault_mtime=path.stat().st_mtime,
                imported=False,
                imported_managed_path=None,
                metadata={
                    "origin": "external",
                    "ext": path.suffix.lower(),
                    "tag_count": len(extract_markdown_metadata(content).get("tags", [])),
                },
            )

        self.db.upsert_obsidian_sync_checkpoint(
            "obsidian-watcher",
            last_started_at=started_at,
            last_completed_at=time.time(),
            last_status="ok",
            last_error=None,
            last_scan_count=scan_count,
            last_change_count=change_count,
        )
