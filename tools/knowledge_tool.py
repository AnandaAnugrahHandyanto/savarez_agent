#!/usr/bin/env python3
"""
Knowledge Tool — Structured personal knowledge store.

Provides CRUD for four entity types (notes, people, projects, decisions) with
tag-based cross-linking.  Tags are the cross-table connector: a note tagged
['sarah', 'acme', 'partnership'] links to Sarah's person entry and any Acme
project, enabling queries like "everything about Sarah" across all tables.

Storage: knowledge_* tables in ~/.hermes/state.db (schema v9+).
Thread-safe via SessionDB._execute_write (BEGIN IMMEDIATE + jitter retry).

Design mirrors memory_tool.py: schema + handler + self-registration.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Content scanning — delegates to consolidated guardrails module
# ---------------------------------------------------------------------------

from agent.guardrails import scan_content as _scan_content


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

_VALID_ENTITY_TYPES = {"note", "person", "project", "decision"}


async def knowledge_tool(
    action: str,
    content: str = None,
    name: str = None,
    title: str = None,
    role: str = None,
    organization: str = None,
    details: str = None,
    description: str = None,
    rationale: str = None,
    status: str = None,
    tags: str = None,
    query: str = None,
    entity_type: str = None,
    tag: str = None,
    limit: int = 20,
    session_db=None,
    session_id: str = None,
    knowledge_manager=None,
) -> str:
    """Single entry point for the knowledge tool. Returns JSON string."""
    if session_db is None:
        return json.dumps({
            "success": False,
            "error": "Knowledge store not available (session database not initialized)."
        })

    # Cap limit to prevent unbounded result sets
    limit = min(int(limit), 100)

    # Parse tags from comma-separated string
    tag_list = []
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]

    if action == "save_note":
        if not content:
            return json.dumps({"success": False, "error": "content is required for save_note"})
        threat = _scan_content(content)
        if threat:
            return json.dumps({"success": False, "error": threat})
        
        if knowledge_manager:
            note_id = knowledge_manager.save_note(
                content=content, tags=tag_list, session_id=session_id
            )
        else:
            note_id = session_db.save_knowledge_note(
                content=content, tags=tag_list,
                source="conversation", session_id=session_id,
            )
            
        return json.dumps({
            "success": True, "action": "save_note",
            "id": note_id, "tags": tag_list,
            "message": f"Note saved (id={note_id}) with tags: {tag_list}" if tag_list else f"Note saved (id={note_id})"
        })

    elif action == "save_person":
        if not name:
            return json.dumps({"success": False, "error": "name is required for save_person"})
        for field in [name, role, organization, details]:
            if field:
                threat = _scan_content(field)
                if threat:
                    return json.dumps({"success": False, "error": threat})
        
        if knowledge_manager:
            person_id = knowledge_manager.save_person(
                name=name, role=role, organization=organization,
                details=details, tags=tag_list
            )
        else:
            person_id = session_db.save_knowledge_person(
                name=name, role=role, organization=organization,
                details=details, tags=tag_list,
            )
            
        return json.dumps({
            "success": True, "action": "save_person",
            "id": person_id, "name": name,
            "message": f"Person '{name}' saved (id={person_id})"
        })

    elif action == "save_project":
        if not name:
            return json.dumps({"success": False, "error": "name is required for save_project"})
        for field in [name, description]:
            if field:
                threat = _scan_content(field)
                if threat:
                    return json.dumps({"success": False, "error": threat})
        
        if knowledge_manager:
            project_id = knowledge_manager.save_project(
                name=name, description=description,
                status=status or "active", tags=tag_list
            )
        else:
            project_id = session_db.save_knowledge_project(
                name=name, description=description,
                status=status or "active", tags=tag_list,
            )
            
        return json.dumps({
            "success": True, "action": "save_project",
            "id": project_id, "name": name,
            "message": f"Project '{name}' saved (id={project_id})"
        })

    elif action == "save_decision":
        if not title:
            return json.dumps({"success": False, "error": "title is required for save_decision"})
        for field in [title, rationale]:
            if field:
                threat = _scan_content(field)
                if threat:
                    return json.dumps({"success": False, "error": threat})
        
        if knowledge_manager:
            decision_id = knowledge_manager.save_decision(
                title=title, rationale=rationale,
                status=status or "active", tags=tag_list
            )
        else:
            decision_id = session_db.save_knowledge_decision(
                title=title, rationale=rationale,
                status=status or "active", tags=tag_list,
            )
            
        return json.dumps({
            "success": True, "action": "save_decision",
            "id": decision_id, "title": title,
            "message": f"Decision '{title}' saved (id={decision_id})"
        })

    elif action == "search":
        if entity_type and entity_type not in _VALID_ENTITY_TYPES:
            return json.dumps({
                "success": False,
                "error": f"Invalid entity_type '{entity_type}'. Use: {', '.join(sorted(_VALID_ENTITY_TYPES))}"
            })
        results = session_db.search_knowledge(
            query=query, entity_type=entity_type,
            tag=tag, limit=limit,
        )
        return json.dumps({
            "success": True, "action": "search",
            "count": len(results), "results": results,
        })

    elif action == "list":
        if not entity_type:
            return json.dumps({"success": False, "error": "entity_type is required for list"})
        if entity_type not in _VALID_ENTITY_TYPES:
            return json.dumps({
                "success": False,
                "error": f"Invalid entity_type '{entity_type}'. Use: {', '.join(sorted(_VALID_ENTITY_TYPES))}"
            })
        results = session_db.list_knowledge(
            entity_type=entity_type, tag=tag, limit=limit,
        )
        return json.dumps({
            "success": True, "action": "list",
            "entity_type": entity_type, "count": len(results),
            "results": results,
        })

    elif action == "ingest":
        if not knowledge_manager:
            return json.dumps({"success": False, "error": "Obsidian vault not configured."})
        
        from cron.obsidian_ingest import ObsidianIngest
        ingestor = ObsidianIngest(
            db=session_db,
            vault_path=str(knowledge_manager.vault_path),
            agent_prefix=knowledge_manager.agent_prefix
        )
        ingestor.ingest_all()
        return json.dumps({
            "success": True, "action": "ingest",
            "message": "Obsidian vault scanned and ingested successfully."
        })

    elif action == "sync":
        if not knowledge_manager:
            return json.dumps({"success": False, "error": "Obsidian vault not configured."})
        
        created, skipped = await knowledge_manager.sync_episodes(limit=limit)
        return json.dumps({
            "success": True, "action": "sync",
            "created": created, "skipped": skipped,
            "message": f"Synced {created} episodes to Obsidian (skipped {skipped})."
        })

    else:
        return json.dumps({
            "success": False,
            "error": f"Unknown action '{action}'. Use: save_note, save_person, save_project, save_decision, search, list, ingest, sync"
        })


def check_knowledge_requirements() -> bool:
    """Knowledge tool requires session DB — always register, gate at runtime."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

KNOWLEDGE_SCHEMA = {
    "name": "knowledge",
    "description": (
        "Save and query structured personal knowledge. Mirrors all data to your "
        "Obsidian vault if configured, creating a compounding knowledge base.\n\n"
        "WHEN TO USE (proactively, don't wait to be asked):\n"
        "- User mentions a person: save_person with their name, role, org\n"
        "- User shares a meeting note or observation: save_note with tags\n"
        "- User starts or mentions a project: save_project\n"
        "- User makes or describes a decision: save_decision with rationale\n"
        "- User asks 'what do I know about X': search with query or tag\n\n"
        "ACTIONS:\n"
        "- save_note: Save a note (requires content, optional tags)\n"
        "- save_person: Save/update a person (requires name)\n"
        "- save_project: Save/update a project (requires name)\n"
        "- save_decision: Record a decision (requires title, rationale)\n"
        "- search: Cross-table search by query text and/or tag\n"
        "- list: List entities of a specific type\n"
        "- ingest: Manually trigger ingestion of your personal Obsidian notes into Hermes\n"
        "- sync: Export recent agent episodes/learnings to Obsidian\n\n"
        "This is DIFFERENT from the memory tool: memory is for agent instructions and "
        "user preferences. Knowledge is for facts about the user's world. This is also "
        "different from the 'kb' wiki tool: knowledge is the structured fact store, while "
        "the wiki is for compiled markdown synthesis and durable research pages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save_note", "save_person", "save_project", "save_decision", "search", "list", "ingest", "sync"],
                "description": "The action to perform."
            },
            "content": {
                "type": "string",
                "description": "Note content (for save_note)."
            },
            "name": {
                "type": "string",
                "description": "Person or project name (for save_person, save_project)."
            },
            "title": {
                "type": "string",
                "description": "Decision title (for save_decision)."
            },
            "role": {
                "type": "string",
                "description": "Person's role (for save_person)."
            },
            "organization": {
                "type": "string",
                "description": "Person's organization (for save_person)."
            },
            "details": {
                "type": "string",
                "description": "Additional details as JSON (for save_person)."
            },
            "description": {
                "type": "string",
                "description": "Project description (for save_project)."
            },
            "rationale": {
                "type": "string",
                "description": "Why this decision was made (for save_decision)."
            },
            "status": {
                "type": "string",
                "description": "Entity status: 'active', 'completed', 'paused', 'superseded', 'reversed'."
            },
            "tags": {
                "type": "string",
                "description": "Comma-separated tags for cross-linking (e.g. 'sarah,acme,partnership')."
            },
            "query": {
                "type": "string",
                "description": "Search text (for search action). Searches across names, content, titles."
            },
            "entity_type": {
                "type": "string",
                "enum": ["note", "person", "project", "decision"],
                "description": "Filter by entity type (for search/list)."
            },
            "tag": {
                "type": "string",
                "description": "Filter by a single tag (for search/list)."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 20, max 100).",
                "default": 20
            }
        },
        "required": ["action"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="knowledge",
    toolset="knowledge",
    schema=KNOWLEDGE_SCHEMA,
    is_async=True,
    handler=lambda args, **kw: knowledge_tool(
        action=args.get("action", ""),
        content=args.get("content"),
        name=args.get("name"),
        title=args.get("title"),
        role=args.get("role"),
        organization=args.get("organization"),
        details=args.get("details"),
        description=args.get("description"),
        rationale=args.get("rationale"),
        status=args.get("status"),
        tags=args.get("tags"),
        query=args.get("query"),
        entity_type=args.get("entity_type"),
        tag=args.get("tag"),
        limit=args.get("limit", 20),
        session_db=kw.get("session_db"),
        session_id=kw.get("session_id"),
        knowledge_manager=kw.get("knowledge_manager"),
    ),
    check_fn=check_knowledge_requirements,
    emoji="📚",
    mutates=True,
)
