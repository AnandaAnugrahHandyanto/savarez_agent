#!/usr/bin/env python3
"""
Entity Extraction + Session Graph System for Hermes.

Provides:
1. Entity Extraction - Parse session data to extract entities (projects, files, skills, tools, preferences, decisions)
2. Graph Schema - SQLite tables for entities, session-entity links, and entity relationships
3. Entity Linking - Connect new entities to related entities from past sessions
4. Query API - Find related sessions via entity intersection, get project timelines

Entity Types:
- project: Named projects or work areas
- file: File paths or names mentioned
- skill: Skills or capabilities mentioned
- tool: Tools (code, CLI, etc.) used or referenced
- preference: User preferences expressed
- decision: Decisions made during session
"""

import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from hermes_constants import get_hermes_home
from hermes_state import SessionDB

logger = logging.getLogger(__name__)

# Entity type constants
ENTITY_PROJECT = "project"
ENTITY_FILE = "file"
ENTITY_SKILL = "skill"
ENTITY_TOOL = "tool"
ENTITY_PREFERENCE = "preference"
ENTITY_DECISION = "decision"

ENTITY_TYPES = [ENTITY_PROJECT, ENTITY_FILE, ENTITY_SKILL, ENTITY_TOOL, ENTITY_PREFERENCE, ENTITY_DECISION]

# Relationship types
REL_RELATES_TO = "relates_to"
REL_PART_OF = "part_of"
REL_USES = "uses"
REL_DEPENDS_ON = "depends_on"

RELATIONSHIP_TYPES = [REL_RELATES_TO, REL_PART_OF, REL_USES, REL_DEPENDS_ON]

# Keyword patterns for entity extraction
KEYWORD_PATTERNS = {
    ENTITY_PROJECT: [
        re.compile(r'\b(project|workspace|repo|repository|codebase)\s+([a-zA-Z0-9_-]+)', re.I),
        re.compile(r'(?:working on|working in|project name:?)\s*([a-zA-Z0-9_-]+)', re.I),
        re.compile(r'/([^/\s]+)/(?:src|lib|app|main|tests?)/', re.I),
    ],
    ENTITY_FILE: [
        re.compile(r'(?:file|path|modifying|editing|creating)\s+([a-zA-Z0-9_./\\-]+\.(?:py|js|ts|md|json|yaml|yml|toml|sh|sql|html|css))', re.I),
        re.compile(r'(?:importing|exporting|reading|writing)\s+([a-zA-Z0-9_./\\-]+\.\w+)', re.I),
        re.compile(r'([a-zA-Z0-9_./\\-]+\.(?:py|js|ts|md|json|yaml|yml|toml|sh|sql))', re.I),
    ],
    ENTITY_SKILL: [
        re.compile(r'(?:skill|expert|proficient|experience)\s+(?:in|with)?\s*([a-zA-Z0-9\s]+)', re.I),
        re.compile(r'(?:using|working with|knowledge of)\s+([a-zA-Z0-9\s]+)', re.I),
        re.compile(r'(?:know|understand|can use)\s+([a-zA-Z0-9\s]+)', re.I),
        # Technical keywords
        re.compile(r'\b(python|javascript|typescript|rust|go|java|c\+\+|sql|html|css|docker|kubernetes|aws|gcp|azure|linux|git)\b', re.I),
    ],
    ENTITY_TOOL: [
        re.compile(r'(?:using|with|via|through)\s+(?:tool|command)\s+([a-zA-Z0-9_-]+)', re.I),
        re.compile(r'(?:running|executing|calling)\s+([a-zA-Z0-9_-]+)', re.I),
        re.compile(r'(?:tool|cli|command).*?(git|pip|npm|yarn|docker|kubectl|terraform|ansible|make|pytest|node|npm)', re.I),
    ],
    ENTITY_PREFERENCE: [
        re.compile(r'(?:prefer|like|love|hate|dislike|want|need|require)\s+(?:to|that|when)?\s*(.+)', re.I),
        re.compile(r'(?:my|I)\s+(?:preference|like|want|need)\s+(?:is|to)\s*(.+)', re.I),
        re.compile(r'(?:always|never|usually|often)\s+(.+)', re.I),
    ],
    ENTITY_DECISION: [
        re.compile(r'(?:decided|chose|selected|went with|picked)\s+(.+)', re.I),
        re.compile(r'(?:conclusion|decision|resolved|settled on)\s+(?:that|on)?\s*(.+)', re.I),
        re.compile(r'(?:will|going to)\s+(?:use|implement|build|create)\s+(.+)', re.I),
    ],
}

# Path prefixes to ignore
IGNORE_PATH_PREFIXES = [
    '/usr/', '/bin/', '/lib/', '/opt/', '/etc/', '/var/', 
    '~/.hermes/', 'node_modules/', '__pycache__/', '.git/',
    '/tmp/', '/dev/', '/sys/', '/proc/',
]


class EntityGraph:
    """
    Session relationship graph system.
    
    Manages entity extraction, storage, and querying for Hermes sessions.
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or (get_hermes_home() / "entity_graph.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
    
    def _init_schema(self):
        """Create entity graph tables if they don't exist."""
        cursor = self._conn.cursor()
        
        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                occurrence_count INTEGER DEFAULT 1,
                metadata TEXT,
                UNIQUE(type, normalized_name)
            )
        """)
        
        # Session-Entity links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                first_linked REAL NOT NULL,
                last_linked REAL NOT NULL,
                context_snippet TEXT,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                UNIQUE(session_id, entity_id)
            )
        """)
        
        # Entity relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_a INTEGER NOT NULL,
                entity_b INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                first_connected REAL NOT NULL,
                last_connected REAL NOT NULL,
                weight INTEGER DEFAULT 1,
                FOREIGN KEY (entity_a) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_b) REFERENCES entities(id) ON DELETE CASCADE,
                UNIQUE(entity_a, entity_b, relationship_type)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(normalized_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_entities_session ON session_entities(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_entities_entity ON session_entities(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_relationships_a ON entity_relationships(entity_a)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_relationships_b ON entity_relationships(entity_b)")
        
        self._conn.commit()
    
    def _normalize(self, name: str) -> str:
        """Normalize entity name for comparison."""
        return name.lower().strip()
    
    def _should_ignore_path(self, path: str) -> bool:
        """Check if path should be ignored."""
        for prefix in IGNORE_PATH_PREFIXES:
            if path.startswith(prefix) or path.startswith('~' + prefix):
                return True
        return False
    
    def extract_entities_from_text(self, text: str) -> Dict[str, Set[str]]:
        """
        Extract entities from text using keyword patterns.
        
        Returns dict mapping entity type to set of entity names.
        """
        entities = defaultdict(set)
        
        if not text:
            return entities
        
        # Extract by type using patterns
        for entity_type, patterns in KEYWORD_PATTERNS.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                for match in matches:
                    # Handle both single group and multiple groups
                    if isinstance(match, tuple):
                        name = match[0] if match else ""
                    else:
                        name = match
                    
                    if name and len(name) >= 2:
                        # Filter out common false positives
                        name = name.strip()
                        if entity_type == ENTITY_FILE and self._should_ignore_path(name):
                            continue
                        if len(name) >= 2:
                            entities[entity_type].add(name)
        
        # Additional heuristics for common patterns
        
        # Project names from common path structures
        project_pattern = re.compile(r'(?:^|/)([a-zA-Z0-9_-]+)(?:/src|/lib|/app|/main)?(?:/|$)')
        for match in project_pattern.findall(text):
            if match and len(match) >= 3:
                entities[ENTITY_PROJECT].add(match)
        
        return dict(entities)
    
    def _extract_entities_llm_fallback(self, session_data: dict, extracted: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        """
        LLM fallback for entity extraction when keyword patterns aren't sufficient.
        
        This is a placeholder - in production, you'd call an LLM to extract more nuanced entities.
        For now, we enhance the keyword-based extraction with additional heuristics.
        """
        # For now, just return the keyword-extracted entities
        # In production, this would call an LLM API
        return extracted
    
    def extract_entities_from_session(
        self,
        session_id: str,
        messages: List[dict],
        title: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract all entities from a session's messages.
        
        Args:
            session_id: The session ID
            messages: List of message dicts with 'role' and 'content'
            title: Optional session title
            
        Returns:
            List of entity dicts with 'type', 'name', 'context'
        """
        all_text = ""
        
        # Build text from messages
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            
            all_text += f"{role}: {content}\n"
            
            # Also include tool call info
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    fname = func.get("name", "")
                    fargs = func.get("arguments", "")
                    all_text += f"tool: {fname} {fargs}\n"
        
        # Add title if present
        if title:
            all_text += f"session: {title}\n"
        
        # Extract using patterns
        extracted = self.extract_entities_from_text(all_text)
        
        # Enhance with LLM if needed
        session_data = {"session_id": session_id, "messages": messages, "title": title}
        extracted = self._extract_entities_llm_fallback(session_data, extracted)
        
        # Build result list with context
        entities = []
        for entity_type, names in extracted.items():
            for name in names:
                entities.append({
                    "type": entity_type,
                    "name": name,
                    "normalized": self._normalize(name),
                })
        
        return entities
    
    def upsert_entity(
        self,
        entity_type: str,
        name: str,
        session_id: str = None,
        context_snippet: str = None,
    ) -> int:
        """
        Insert or update an entity, linking to a session.
        
        Returns the entity ID.
        """
        normalized = self._normalize(name)
        now = time.time()
        
        cursor = self._conn.cursor()
        
        # Check if entity exists
        cursor.execute(
            "SELECT id FROM entities WHERE type = ? AND normalized_name = ?",
            (entity_type, normalized)
        )
        row = cursor.fetchone()
        
        if row:
            entity_id = row["id"]
            # Update entity
            cursor.execute("""
                UPDATE entities SET 
                    last_seen = ?,
                    occurrence_count = occurrence_count + 1
                WHERE id = ?
            """, (now, entity_id))
        else:
            # Insert new entity
            cursor.execute("""
                INSERT INTO entities (type, name, normalized_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
            """, (entity_type, name, normalized, now, now))
            entity_id = cursor.lastrowid
        
        # Link to session if provided
        if session_id:
            cursor.execute("""
                INSERT OR REPLACE INTO session_entities 
                (session_id, entity_id, first_linked, last_linked, context_snippet)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, entity_id, now, now, context_snippet[:500] if context_snippet else None))
        
        self._conn.commit()
        return entity_id
    
    def link_entities(
        self,
        session_id: str,
        entities: List[Dict[str, Any]],
    ) -> None:
        """
        Link extracted entities to a session and build relationships.
        """
        now = time.time()
        entity_ids = []
        
        cursor = self._conn.cursor()
        
        for entity in entities:
            entity_id = self.upsert_entity(
                entity_type=entity["type"],
                name=entity["name"],
                session_id=session_id,
                context_snippet=entity.get("context"),
            )
            entity_ids.append(entity_id)
        
        # Build relationships between entities in this session
        # Entities that appear together in a session are related
        for i, eid_a in enumerate(entity_ids):
            for eid_b in entity_ids[i+1:]:
                # Determine relationship type based on entity types
                rel_type = self._infer_relationship(eid_a, eid_b)
                
                # Check if relationship exists and get current weight
                cursor.execute("""
                    SELECT weight FROM entity_relationships 
                    WHERE entity_a = ? AND entity_b = ? AND relationship_type = ?
                """, (eid_a, eid_b, REL_RELATES_TO))
                row = cursor.fetchone()
                new_weight = (row["weight"] + 1) if row else 1
                
                cursor.execute("""
                    INSERT OR REPLACE INTO entity_relationships
                    (entity_a, entity_b, relationship_type, first_connected, last_connected, weight)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (eid_a, eid_b, REL_RELATES_TO, now, now, new_weight))
        
        self._conn.commit()
    
    def _infer_relationship(self, entity_a_id: int, entity_b_id: int) -> str:
        """
        Infer relationship type between two entities based on their types.
        """
        # For now, default to relates_to
        # In production, could analyze co-occurrence patterns
        return REL_RELATES_TO
    
    def find_related_sessions(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find sessions related to a given session via entity intersection.
        
        Returns sessions that share entities with the given session.
        """
        cursor = self._conn.cursor()
        
        # Get entities for this session
        cursor.execute("""
            SELECT entity_id FROM session_entities WHERE session_id = ?
        """, (session_id,))
        session_entities = [row["entity_id"] for row in cursor.fetchall()]
        
        if not session_entities:
            return []
        
        # Try to join with sessions table for more info, fallback to just session_entities
        try:
            cursor.execute("""
                SELECT 
                    se.session_id,
                    COUNT(se.entity_id) as shared_count,
                    MAX(se.last_linked) as last_activity
                FROM session_entities se
                LEFT JOIN sessions s ON se.session_id = s.id
                WHERE se.entity_id IN ({})
                  AND se.session_id != ?
                GROUP BY se.session_id
                ORDER BY shared_count DESC, last_activity DESC
                LIMIT ?
            """.format(",".join("?" * len(session_entities))), 
            (*session_entities, session_id, limit))
        except sqlite3.OperationalError:
            # No sessions table - use just session_entities
            cursor.execute("""
                SELECT 
                    se.session_id,
                    COUNT(se.entity_id) as shared_count,
                    MAX(se.last_linked) as last_activity
                FROM session_entities se
                WHERE se.entity_id IN ({})
                  AND se.session_id != ?
                GROUP BY se.session_id
                ORDER BY shared_count DESC, last_activity DESC
                LIMIT ?
            """.format(",".join("?" * len(session_entities))), 
            (*session_entities, session_id, limit))
        
        results = []
        for row in cursor.fetchall():
            # Get the shared entities
            cursor.execute("""
                SELECT e.type, e.name
                FROM session_entities se
                JOIN entities e ON se.entity_id = e.id
                WHERE se.session_id = ? AND se.entity_id IN ({})
            """.format(",".join("?" * len(session_entities))),
            (row["session_id"], *session_entities))
            
            shared_entities = [{"type": r["type"], "name": r["name"]} for r in cursor.fetchall()]
            
            results.append({
                "session_id": row["session_id"],
                "shared_entities": shared_entities,
                "shared_count": row["shared_count"],
                "last_activity": row["last_activity"],
            })
        
        return results
    
    def get_entity_timeline(
        self,
        entity_name: str,
        entity_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of sessions involving an entity.
        
        Returns sessions where the entity appeared, ordered by time.
        """
        cursor = self._conn.cursor()
        
        normalized = self._normalize(entity_name)
        
        # Try sessions table first, fallback to just session_entities
        try:
            if entity_type:
                cursor.execute("""
                    SELECT 
                        s.id,
                        s.title,
                        s.started_at,
                        s.ended_at,
                        se.context_snippet
                    FROM sessions s
                    JOIN session_entities se ON s.id = se.session_id
                    JOIN entities e ON se.entity_id = e.id
                    WHERE e.normalized_name = ? AND e.type = ?
                    ORDER BY se.last_linked DESC
                """, (normalized, entity_type))
            else:
                cursor.execute("""
                    SELECT 
                        s.id,
                        s.title,
                        s.started_at,
                        s.ended_at,
                        se.context_snippet
                    FROM sessions s
                    JOIN session_entities se ON s.id = se.session_id
                    JOIN entities e ON se.entity_id = e.id
                    WHERE e.normalized_name = ?
                    ORDER BY se.last_linked DESC
                """, (normalized,))
        except sqlite3.OperationalError:
            # No sessions table - use session_entities directly
            if entity_type:
                cursor.execute("""
                    SELECT 
                        se.session_id as id,
                        se.context_snippet,
                        se.last_linked as started_at
                    FROM session_entities se
                    JOIN entities e ON se.entity_id = e.id
                    WHERE e.normalized_name = ? AND e.type = ?
                    ORDER BY se.last_linked DESC
                """, (normalized, entity_type))
            else:
                cursor.execute("""
                    SELECT 
                        se.session_id as id,
                        se.context_snippet,
                        se.last_linked as started_at
                    FROM session_entities se
                    JOIN entities e ON se.entity_id = e.id
                    WHERE e.normalized_name = ?
                    ORDER BY se.last_linked DESC
                """, (normalized,))
        
        # Handle different column sets from try/except
        rows = cursor.fetchall()
        results = []
        for row in rows:
            if "title" in row.keys():
                results.append({
                    "session_id": row["id"],
                    "title": row["title"],
                    "started_at": row["started_at"],
                    "ended_at": row["ended_at"],
                    "context": row["context_snippet"],
                })
            else:
                results.append({
                    "session_id": row["id"],
                    "title": None,
                    "started_at": row["started_at"],
                    "ended_at": None,
                    "context": row["context_snippet"],
                })
        
        return results
    
    def get_project_timeline(self, project_name: str) -> List[Dict[str, Any]]:
        """Get timeline for a project (shortcut for entity type project)."""
        return self.get_entity_timeline(project_name, ENTITY_PROJECT)
    
    def get_related_entities(
        self,
        entity_name: str,
        entity_type: str = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get entities related to a given entity.
        
        Returns other entities that frequently appear together.
        """
        cursor = self._conn.cursor()
        
        normalized = self._normalize(entity_name)
        
        if entity_type:
            cursor.execute("""
                SELECT e.id FROM entities WHERE normalized_name = ? AND type = ?
            """, (normalized, entity_type))
        else:
            cursor.execute("""
                SELECT id FROM entities WHERE normalized_name = ?
            """, (normalized,))
        
        row = cursor.fetchone()
        if not row:
            return []
        
        entity_id = row["id"]
        
        # Find related entities via relationships
        cursor.execute("""
            SELECT 
                e.type,
                e.name,
                er.weight,
                er.relationship_type
            FROM entity_relationships er
            JOIN entities e ON 
                (er.entity_a = ? AND e.id = er.entity_b) OR
                (er.entity_b = ? AND e.id = er.entity_a)
            WHERE er.entity_a = ? OR er.entity_b = ?
            ORDER BY er.weight DESC
            LIMIT ?
        """, (entity_id, entity_id, entity_id, entity_id, limit))
        
        return [
            {
                "type": row["type"],
                "name": row["name"],
                "weight": row["weight"],
                "relationship": row["relationship_type"],
            }
            for row in cursor.fetchall()
        ]
    
    def get_entity_stats(self) -> Dict[str, Any]:
        """Get statistics about the entity graph."""
        cursor = self._conn.cursor()
        
        # Count by type
        cursor.execute("""
            SELECT type, COUNT(*) as count FROM entities GROUP BY type
        """)
        by_type = {row["type"]: row["count"] for row in cursor.fetchall()}
        
        # Total counts
        cursor.execute("SELECT COUNT(*) as total FROM entities")
        total_entities = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as total FROM session_entities")
        total_links = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as total FROM entity_relationships")
        total_relationships = cursor.fetchone()["total"]
        
        return {
            "total_entities": total_entities,
            "total_links": total_links,
            "total_relationships": total_relationships,
            "by_type": by_type,
        }
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


def process_session_end(session_id: str) -> None:
    """
    Process session end: extract entities and build relationships.
    
    Called from session capture/close handlers.
    """
    from hermes_state import SessionDB
    
    # Get session data
    db = SessionDB()
    
    # Get messages
    cursor = db._conn.cursor()
    cursor.execute("""
        SELECT role, content, tool_calls FROM messages 
        WHERE session_id = ? ORDER BY timestamp
    """, (session_id,))
    
    messages = []
    for row in cursor.fetchall():
        msg = {"role": row["role"], "content": row["content"] or ""}
        if row["tool_calls"]:
            try:
                msg["tool_calls"] = json.loads(row["tool_calls"])
            except:
                msg["tool_calls"] = []
        messages.append(msg)
    
    # Get title
    cursor.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    title = row["title"] if row else None
    
    # Extract entities
    graph = EntityGraph()
    entities = graph.extract_entities_from_session(session_id, messages, title)
    
    # Link entities to session and build relationships
    graph.link_entities(session_id, entities)
    
    graph.close()
    db.close()
    
    logger.info(f"Entity extraction complete: {len(entities)} entities from session {session_id}")


# Integration helper for cli.py
def integrate_with_auto_distill(session_id: str) -> None:
    """
    Integrate entity extraction with the auto_distill system.
    
    Call this after session capture to extract and link entities.
    """
    try:
        process_session_end(session_id)
    except Exception as e:
        logger.warning(f"Entity extraction failed: {e}")


if __name__ == "__main__":
    # Test/demo
    import sys
    
    # Create graph
    graph = EntityGraph()
    
    print("Entity Graph System")
    print("=" * 50)
    print(f"Database: {graph.db_path}")
    print()
    
    # Show stats
    stats = graph.get_entity_stats()
    print(f"Total entities: {stats['total_entities']}")
    print(f"Total links: {stats['total_links']}")
    print(f"Total relationships: {stats['total_relationships']}")
    print()
    
    if stats['by_type']:
        print("By type:")
        for etype, count in stats['by_type'].items():
            print(f"  {etype}: {count}")
    
    graph.close()