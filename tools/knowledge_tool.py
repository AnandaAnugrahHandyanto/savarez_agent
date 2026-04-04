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
# Content scanning — reuse patterns from memory_tool for injection protection
# ---------------------------------------------------------------------------

_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
]

_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_content(content: str) -> Optional[str]:
    """Scan content for injection/exfiltration patterns."""
    if not content:
        return None
    for char in _INVISIBLE_CHARS:
        if char in content:
            return f"Blocked: invisible unicode U+{ord(char):04X}"
    lower = content.lower()
    for pattern, threat_type in _THREAT_PATTERNS:
        if re.search(pattern, lower):
            return f"Blocked: {threat_type}"
    return None


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

_VALID_ENTITY_TYPES = {"note", "person", "project", "decision"}


def knowledge_tool(
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

    else:
        return json.dumps({
            "success": False,
            "error": f"Unknown action '{action}'. Use: save_note, save_person, save_project, save_decision, search, list"
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
        "Save and query structured personal knowledge that persists across sessions. "
        "Stores four entity types — notes, people, projects, decisions — linked by tags.\n\n"
        "WHEN TO USE (proactively, don't wait to be asked):\n"
        "- User mentions a person: save_person with their name, role, org\n"
        "- User shares a meeting note or observation: save_note with tags for people/projects mentioned\n"
        "- User starts or mentions a project: save_project\n"
        "- User makes or describes a decision: save_decision with rationale\n"
        "- User asks 'what do I know about X': search with query or tag\n\n"
        "TAGS are the key concept: they cross-link entities. A note tagged 'sarah,acme' "
        "will appear when searching for tag='sarah' or tag='acme'. Always tag notes with "
        "the names of people and projects mentioned.\n\n"
        "ACTIONS:\n"
        "- save_note: Save a note (requires content, optional tags)\n"
        "- save_person: Save/update a person (requires name, optional role/organization/details/tags)\n"
        "- save_project: Save/update a project (requires name, optional description/status/tags)\n"
        "- save_decision: Record a decision (requires title, optional rationale/status/tags)\n"
        "- search: Cross-table search by query text and/or tag\n"
        "- list: List entities of a specific type\n\n"
        "This is DIFFERENT from the memory tool: memory stores your agent observations and user "
        "preferences. Knowledge stores facts about the user's world — people they know, projects "
        "they work on, decisions they've made, meeting notes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save_note", "save_person", "save_project", "save_decision", "search", "list"],
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
    ),
    check_fn=check_knowledge_requirements,
    emoji="📚",
)
