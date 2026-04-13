#!/usr/bin/env python3
"""
Unified Knowledge Manager — Orchestrates SQLite (SessionDB) and Obsidian (Markdown).

Implements the "Mirroring" protocol: every structured save (Note, Person,
Project, Decision) is mirrored to a Markdown file in the Obsidian vault
if configured. Handles bidirectional sync and frontmatter reconciliation.
Ported logic from Hermes Companion (Swift).
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent.obsidian_sync import compute_content_hash, ensure_managed_structure, extract_markdown_metadata, get_entity_dir

logger = logging.getLogger(__name__)

class KnowledgeManager:
    """Orchestrates structured knowledge between SQLite and Obsidian Markdown files."""

    def __init__(self, db, vault_path: Optional[str] = None, agent_prefix: str = "Hermes", graph_manager=None):
        """
        Args:
            db: SessionDB instance
            vault_path: Absolute path to the Obsidian vault
            agent_prefix: Root folder name within the vault for Hermes data
            graph_manager: Optional GraphManager for episode sync
        """
        self.db = db
        self.vault_path = Path(os.path.expanduser(vault_path)) if vault_path else None
        self.agent_prefix = agent_prefix
        self.graph_manager = graph_manager
        
        if self.vault_path:
            try:
                ensure_managed_structure(str(self.vault_path), self.agent_prefix)
            except Exception as e:
                logger.error("Failed to create vault structure in %s: %s", self.vault_path, e)
                self.vault_path = None

    def _get_entity_dir(self, entity_type: str) -> Optional[Path]:
        """Get the directory for an entity type within the vault."""
        if not self.vault_path:
            return None
        return get_entity_dir(str(self.vault_path), self.agent_prefix, entity_type)

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        safe = re.sub(r'[\\/*?:"<>|]', "-", name)
        return safe.strip()[:80]

    def _write_markdown(self, entity_type: str, name: str, body: str, frontmatter: Dict[str, Any]) -> Optional[str]:
        """Write a markdown file to the vault with frontmatter."""
        if not self.vault_path:
            return None
            
        dir_path = self._get_entity_dir(entity_type)
        if not dir_path:
            return None
            
        safe_name = self._sanitize_filename(name)
        file_path = dir_path / f"{safe_name}.md"
        
        # Standard frontmatter
        fm = {
            "created_by": "hermes-agent",
            "hermes_type": entity_type,
            "updated_at": datetime.now().isoformat(),
        }
        fm.update(frontmatter)
        
        fm_lines = ["---"]
        for k, v in fm.items():
            if v is None:
                continue
            if isinstance(v, list):
                if not v:
                    fm_lines.append(f"{k}: []")
                else:
                    items = [f'"{i}"' if " " in str(i) else str(i) for i in v]
                    fm_lines.append(f"{k}: [{', '.join(items)}]")
            elif isinstance(v, (int, float, bool)):
                fm_lines.append(f"{k}: {str(v).lower()}")
            else:
                # Basic escaping for strings
                val = str(v).replace('"', '\\"')
                fm_lines.append(f'{k}: "{val}"')
        fm_lines.append("---\n")
        
        content = "\n".join(fm_lines) + body
        
        try:
            file_path.write_text(content, encoding="utf-8")
            relative_path = str(file_path.relative_to(self.vault_path))
            if hasattr(self.db, "upsert_obsidian_managed_file"):
                metadata = extract_markdown_metadata(content)
                self.db.upsert_obsidian_managed_file(
                    vault_relative_path=relative_path,
                    managed_relative_path=str(file_path.relative_to(self.vault_path / self.agent_prefix)),
                    uuid=str(fm.get("uuid")) if fm.get("uuid") else None,
                    entity_type=entity_type,
                    wiki_page_type=None,
                    file_ext=file_path.suffix.lower(),
                    content_hash=compute_content_hash(content),
                    last_vault_mtime=file_path.stat().st_mtime,
                    last_vault_size=file_path.stat().st_size,
                    last_db_revision_id=None,
                    last_sync_direction="db_to_vault",
                    sync_status="synced",
                    conflict_state="none",
                    source_origin="managed",
                    tombstoned=False,
                    metadata=metadata,
                )
            if hasattr(self.db, "record_obsidian_sync_event"):
                self.db.record_obsidian_sync_event(
                    event_type="db_write",
                    path=relative_path,
                    direction="db_to_vault",
                    status="ok",
                    detail=f"Wrote {entity_type} markdown to Obsidian vault",
                    metadata={"entity_type": entity_type, "relative_path": relative_path},
                )
            return relative_path
        except Exception as e:
            logger.error("Failed to write markdown to %s: %s", file_path, e)
            return None

    # ------------------------------------------------------------------
    # Public API — Mirroring DB operations
    # ------------------------------------------------------------------

    def save_note(self, content: str, tags: List[str] = None, session_id: str = None) -> int:
        """Save a note to DB and mirror to Obsidian."""
        note_uuid = str(uuid.uuid4())
        title = content.split('\n')[0].strip('#').strip()[:40] or "Untitled Note"
        
        file_path = None
        if self.vault_path:
            file_path = self._write_markdown(
                entity_type="note",
                name=title,
                body=content,
                frontmatter={
                    "uuid": note_uuid,
                    "tags": tags or [],
                    "session_id": session_id
                }
            )
            
        return self.db.save_knowledge_note(
            content=content,
            tags=tags,
            session_id=session_id,
            uuid=note_uuid,
            file_path=file_path
        )

    def save_person(
        self, name: str, role: str = None, organization: str = None,
        details: str = None, tags: List[str] = None
    ) -> int:
        """Save a person to DB and mirror to Obsidian."""
        existing = self.db.search_knowledge(query=name, entity_type="person", limit=1)
        person_uuid = None
        if existing and existing[0]['name'].lower() == name.lower():
            person_uuid = existing[0].get('uuid')
            
        if not person_uuid:
            person_uuid = str(uuid.uuid4())
            
        file_path = None
        if self.vault_path:
            body = f"# {name}\n\n"
            if role:
                body += f"**Role:** {role}\n"
            if organization:
                body += f"**Organization:** {organization}\n"
            if details:
                body += f"\n## Details\n{details}\n"
                
            file_path = self._write_markdown(
                entity_type="person",
                name=name,
                body=body,
                frontmatter={
                    "uuid": person_uuid,
                    "name": name,
                    "role": role,
                    "organization": organization,
                    "tags": tags or []
                }
            )
            
        return self.db.save_knowledge_person(
            name=name,
            role=role,
            organization=organization,
            details=details,
            tags=tags,
            uuid=person_uuid,
            file_path=file_path
        )

    def save_project(
        self, name: str, description: str = None,
        status: str = "active", tags: List[str] = None
    ) -> int:
        """Save a project to DB and mirror to Obsidian."""
        existing = self.db.search_knowledge(query=name, entity_type="project", limit=1)
        project_uuid = None
        if existing and existing[0]['name'].lower() == name.lower():
            project_uuid = existing[0].get('uuid')
            
        if not project_uuid:
            project_uuid = str(uuid.uuid4())
            
        file_path = None
        if self.vault_path:
            body = f"# Project: {name}\n\n"
            body += f"**Status:** {status}\n\n"
            if description:
                body += f"## Description\n{description}\n"
                
            file_path = self._write_markdown(
                entity_type="project",
                name=name,
                body=body,
                frontmatter={
                    "uuid": project_uuid,
                    "name": name,
                    "status": status,
                    "tags": tags or []
                }
            )
            
        return self.db.save_knowledge_project(
            name=name,
            description=description,
            status=status,
            tags=tags,
            uuid=project_uuid,
            file_path=file_path
        )

    def save_decision(
        self, title: str, rationale: str = None,
        status: str = "active", tags: List[str] = None
    ) -> int:
        """Save a decision to DB and mirror to Obsidian."""
        decision_uuid = str(uuid.uuid4())
        
        file_path = None
        if self.vault_path:
            body = f"# Decision: {title}\n\n"
            body += f"**Status:** {status}\n\n"
            if rationale:
                body += f"## Rationale\n{rationale}\n"
                
            file_path = self._write_markdown(
                entity_type="decision",
                name=title,
                body=body,
                frontmatter={
                    "uuid": decision_uuid,
                    "title": title,
                    "status": status,
                    "tags": tags or []
                }
            )
            
        return self.db.save_knowledge_decision(
            title=title,
            rationale=rationale,
            status=status,
            tags=tags,
            uuid=decision_uuid,
            file_path=file_path
        )

    # ------------------------------------------------------------------
    # High-level Sync Operations (Ported from Swift)
    # ------------------------------------------------------------------

    async def sync_episodes(self, limit: int = 20) -> Tuple[int, int]:
        """
        Sync recent episodes from the context graph to Obsidian.
        """
        if not self.vault_path or not self.graph_manager:
            return 0, 0
            
        try:
            # GraphitiEpisodes are dictionaries
            episodes = await self.graph_manager.get_episodes(limit=limit)
        except Exception as e:
            logger.error("Failed to fetch episodes from graph: %s", e)
            return 0, 0
            
        created = 0
        skipped = 0
        
        for ep in episodes:
            uuid_str = ep.get("uuid")
            name = ep.get("name")
            content = ep.get("content")
            
            if not uuid_str or not name or not content:
                skipped += 1
                continue
                
            safe_name = self._sanitize_filename(name)
            rel_path = f"{self.agent_prefix}/Episodes/{safe_name}.md"
            
            if (self.vault_path / rel_path).exists():
                skipped += 1
                continue
                
            fm = {
                "uuid": uuid_str,
                "type": "episode",
                "source": ep.get("source", "unknown"),
                "created_by": "hermes-agent",
                "tags": ["hermes", "episode"],
                "synced_at": datetime.now().isoformat()
            }
            
            self._write_markdown(
                entity_type="episode",
                name=name,
                body=f"# {name}\n\n{content}",
                frontmatter=fm
            )
            created += 1
            
        logger.info("Obsidian sync: %d created, %d skipped", created, skipped)
        return created, skipped

    def write_decision_trace(
        self, name: str, goal: str, options: List[str], 
        decision: str, reasoning: str, related_entities: List[str] = None
    ) -> Optional[str]:
        """
        Render a decision trace as an Obsidian note.
        """
        if not self.vault_path:
            return None
            
        links_section = ""
        if related_entities:
            links = [f"[[{self.agent_prefix}/Entities/{e}]]" for e in related_entities]
            links_section = "\n## Related\n" + "\n".join(links) + "\n"
            
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        
        body = f"# Decision: {name}\n\n## Goal\n{goal}\n\n## Options\n{options_text}\n\n## Decision\n{decision}\n\n## Reasoning\n{reasoning}\n{links_section}"
        
        fm = {
            "type": "decision",
            "date": datetime.now().isoformat(),
            "tags": ["hermes", "decision"],
            "created_by": "hermes-agent"
        }
        
        return self._write_markdown(
            entity_type="decision",
            name=name,
            body=body,
            frontmatter=fm
        )
