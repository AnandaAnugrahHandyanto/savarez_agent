"""
Hermes Agent Belief Pipeline
============================

Implements the anti-hallucination architecture from:
/root/.hermes/docs/system-design-brief-memory-belief-anti-hallucination.md

Primary components:
1. BeliefStore (SQLite WAL with FTS5)
2. Grounding pipeline (Path A: auto, Path B: voluntary)
3. Verification pipeline (input-triggered pre-generation check)
4. Retrieval pipeline (system prompt injection)
"""

import os
import sqlite3
import json
import time
import hashlib
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Constants
BELIEF_DB_DIR = os.path.expanduser("~/.hermes/profiles/default/beliefs")
os.makedirs(BELIEF_DB_DIR, exist_ok=True)

# High-risk input categories for triggering check_claim
HIGH_RISK_CATEGORIES = {
    "job_status": [
        "interview", "offer", "rejected", "accepted", "recruiter", 
        "job application", "hiring", "employment"
    ],
    "server_state": [
        "running", "stopped", "up", "down", "crashed", "status",
        "disk.*%", "memory.*%", "process", "service"
    ],
    "configuration": [
        "config", "setting", "cron", "schedule", "environment",
        "variable", "parameter", "option"
    ],
    "specific_numbers": [
        r"\b\d+\b",  # Simple numbers
        r"\d{4}-\d{2}-\d{2}",  # Dates
        r"\d{1,2}:\d{2}",  # Times
    ],
    "user_preferences": [
        "prefer", "like", "dislike", "want", "need", "require"
    ]
}

def get_user_belief_db_path(user_id: str) -> str:
    """Get the path to the user's belief database."""
    return os.path.join(BELIEF_DB_DIR, f"{user_id}.db")

def initialize_belief_store(user_id: str) -> sqlite3.Connection:
    """Initialize the belief store for a user, creating tables if needed."""
    db_path = get_user_belief_db_path(user_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    
    # Create beliefs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS beliefs (
            id              INTEGER PRIMARY KEY,
            user_id         TEXT NOT NULL,
            claim           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'INFERRED'
                                         CHECK (status IN ('VERIFIED', 'INFERRED', 'UNVERIFIED')),
            source_type     TEXT NOT NULL CHECK (source_type IN ('memory', 'tool', 'email', 'web', 'user_statement')),
            source_ref      TEXT,
            provenance      TEXT NOT NULL,
            content_summary TEXT,
            supersedes_id   INTEGER,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL,
            expires_at      REAL,
            metadata        TEXT,
            FOREIGN KEY (supersedes_id) REFERENCES beliefs(id) ON DELETE SET NULL
        )
    """)
    
    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_user ON beliefs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_beliefs_status ON beliefs(user_id, status)")
    
    # Create FTS5 virtual table for claim search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS beliefs_fts USING fts5(
            user_id, claim,
            content=beliefs,
            content_rowid=id
        )
    """)
    
    # Create triggers to keep beliefs_fts in sync with beliefs
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS beliefs_fts_insert AFTER INSERT ON beliefs BEGIN
            INSERT INTO beliefs_fts(rowid, user_id, claim)
            VALUES (new.id, new.user_id, new.claim);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS beliefs_fts_delete AFTER DELETE ON beliefs BEGIN
            INSERT INTO beliefs_fts(beliefs_fts, rowid, user_id, claim)
            VALUES ('delete', old.id, old.user_id, old.claim);
        END
    """)
    
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS beliefs_fts_update AFTER UPDATE ON beliefs BEGIN
            INSERT INTO beliefs_fts(beliefs_fts, rowid, user_id, claim)
            VALUES ('delete', old.id, old.user_id, old.claim);
            INSERT INTO beliefs_fts(rowid, user_id, claim)
            VALUES (new.id, new.user_id, new.claim);
        END
    """)
    
    conn.commit()
    return conn

def detect_high_risk_input(user_message: str) -> Optional[str]:
    """Detect if a user message contains high-risk input that should trigger check_claim.
    
    Returns the category name if high-risk, None otherwise.
    """
    message_lower = user_message.lower()
    
    for category, keywords in HIGH_RISK_CATEGORIES.items():
        # For regex patterns
        if category == "specific_numbers":
            for pattern in keywords:
                if re.search(pattern, message_lower):
                    return category
        else:
            # For keyword lists
            for keyword in keywords:
                if keyword in message_lower:
                    return category
    
    return None

def ground_claim(
    claim: str, 
    user_id: str, 
    source_type: str, 
    source_ref: str = None,
    status: str = "INFERRED",
    provenance: str = None
) -> Dict:
    """Ground a claim in the belief store.
    
    Path A (automatic): source_type='tool' with VERIFIED status
    Path B (voluntary): source_type='user_statement' with VERIFIED/INFERRED status
    
    Returns the belief record.
    """
    conn = initialize_belief_store(user_id)
    
    # Generate provenance if not provided
    if not provenance:
        provenance = f"{source_type}:{source_ref}" if source_ref else source_type
    
    # Check for conflicting beliefs via FTS5
    cursor = conn.execute("""
        SELECT b.id, b.claim, b.status
        FROM beliefs_fts
        JOIN beliefs b ON beliefs_fts.rowid = b.rowid
        WHERE beliefs_fts MATCH ?
          AND b.user_id = ?
        ORDER BY bm25(beliefs_fts)
        LIMIT 5
    """, (claim, user_id))
    
    conflicting_beliefs = cursor.fetchall()
    
    # Simple token overlap scoring (simplified version)
    def token_overlap(claim1: str, claim2: str) -> float:
        tokens1 = set(claim1.lower().split())
        tokens2 = set(claim2.lower().split())
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        return len(tokens1 & tokens2) / len(tokens1 | tokens2)
    
    supersedes_id = None
    for belief in conflicting_beliefs:
        overlap = token_overlap(claim, belief["claim"])
        if overlap >= 0.7:  # High overlap threshold
            # Conflict detected, determine resolution based on status
            if status == "VERIFIED" and belief["status"] == "INFERRED":
                # New VERIFIED supersedes old INFERRED
                supersedes_id = belief["id"]
                break
            elif status == "VERIFIED" and belief["status"] == "VERIFIED":
                # Both VERIFIED - don't auto-supersede, flag for review
                # In a full implementation, we might return a special status
                pass
            elif status == "INFERRED" and belief["status"] == "INFERRED":
                # New INFERRED supersedes old INFERRED
                supersedes_id = belief["id"]
                break
    
    # Insert the new belief
    current_time = time.time()
    cursor = conn.execute("""
        INSERT INTO beliefs (
            user_id, claim, status, source_type, source_ref, 
            provenance, supersedes_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, claim, status, source_type, source_ref,
        provenance, supersedes_id, current_time, current_time
    ))
    
    belief_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "belief_id": belief_id,
        "user_id": user_id,
        "claim": claim,
        "status": status,
        "source_type": source_type,
        "source_ref": source_ref,
        "provenance": provenance,
        "supersedes_id": supersedes_id,
        "created_at": current_time,
        "updated_at": current_time
    }

def check_claim(claim: str, user_id: str, category: str = None) -> Dict:
    """Check if a claim exists in the belief store.
    
    Returns status and source information.
    """
    try:
        conn = initialize_belief_store(user_id)
    except Exception as e:
        # If we can't access the belief store, treat as unverified
        return {
            "status": "UNVERIFIED",
            "source_type": None,
            "source_ref": None,
            "expires_at": None,
            "belief_id": None,
            "error": str(e)
        }
    
    # Search using FTS5 for best match
    cursor = conn.execute("""
        SELECT b.id, b.claim, b.status, b.source_type, b.source_ref, 
               b.expires_at, bm25(beliefs_fts) as rank
        FROM beliefs_fts
        JOIN beliefs b ON beliefs_fts.rowid = b.id
        WHERE beliefs_fts MATCH ?
          AND b.user_id = ?
          AND (b.expires_at IS NULL OR b.expires_at > ?)
        ORDER BY rank
        LIMIT 1
    """, (claim, user_id, time.time()))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "status": result["status"],
            "source_type": result["source_type"],
            "source_ref": result["source_ref"],
            "expires_at": result["expires_at"],
            "belief_id": result["id"],
            "matched_claim": result["claim"],
            "confidence": "high" if result["rank"] < -2 else "medium"  # Simplified confidence
        }
    else:
        # No matching belief found
        return {
            "status": "UNVERIFIED",
            "source_type": None,
            "source_ref": None,
            "expires_at": None,
            "belief_id": None
        }

def get_relevant_beliefs(user_id: str, status_filter: str = None, limit: int = 20) -> List[Dict]:
    """Get relevant beliefs for a user to inject into the system prompt.
    
    Returns up to 'limit' beliefs, prioritized by status and recency.
    """
    try:
        conn = initialize_belief_store(user_id)
    except Exception as e:
        return []
    
    # Build query based on status filter
    if status_filter:
        query = """
            SELECT id, claim, status, source_type, source_ref, updated_at
            FROM beliefs
            WHERE user_id = ?
              AND status = ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params = (user_id, status_filter, time.time(), limit)
    else:
        query = """
            SELECT id, claim, status, source_type, source_ref, updated_at
            FROM beliefs
            WHERE user_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY
              CASE status WHEN 'VERIFIED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END,
              updated_at DESC
            LIMIT ?
        """
        params = (user_id, time.time(), limit)
    
    cursor = conn.execute(query, params)
    beliefs = cursor.fetchall()
    conn.close()
    
    return [dict(belief) for belief in beliefs]

def audit_response(response_text: str) -> List[Dict]:
    """Weak post-generation audit for high-risk claims that slipped through.
    
    Returns a list of detected claims with their categories.
    """
    detected_claims = []
    
    # Job status patterns
    job_patterns = r"rejected|offer|accepted|interview.*result|recruiter"
    if re.search(job_patterns, response_text, re.IGNORECASE):
        detected_claims.append({
            "type": "job_status",
            "matched_text": re.search(job_patterns, response_text, re.IGNORECASE).group(),
            "confidence": "high"
        })
    
    # Server state patterns
    server_patterns = r"running|stopped|up|down|crashed|disk.*%|memory.*%"
    if re.search(server_patterns, response_text, re.IGNORECASE):
        detected_claims.append({
            "type": "server_state",
            "matched_text": re.search(server_patterns, response_text, re.IGNORECASE).group(),
            "confidence": "high"
        })
    
    # Date/number patterns (simplified)
    date_number_patterns = r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b|\b\d+\b"
    date_matches = re.findall(date_number_patterns, response_text)
    if date_matches:
        detected_claims.append({
            "type": "specific_numbers",
            "matched_text": ", ".join(date_matches[:3]),  # Limit to first 3
            "confidence": "medium"
        })
    
    return detected_claims

def categorize_input(user_message: str, high_risk_categories: Dict) -> Dict:
    """Categorize user input for A/B path routing.
    
    Returns category information including whether grounding is required.
    """
    message_lower = user_message.lower()
    
    for category, keywords in high_risk_categories.items():
        # For regex patterns
        if category == "specific_numbers":
            for pattern in keywords:
                if re.search(pattern, message_lower):
                    return {
                        "category": category,
                        "requires_grounding": True,
                        "matched_pattern": pattern
                    }
        else:
            # For keyword lists
            for keyword in keywords:
                if keyword in message_lower:
                    # Determine if this category requires grounding
                    # Generally, we want to ground job status, server state, and configuration claims
                    requires_grounding = category in ["job_status", "server_state", "configuration"]
                    return {
                        "category": category,
                        "requires_grounding": requires_grounding,
                        "matched_keyword": keyword
                    }
    
    # Default to general category with no grounding required
    return {
        "category": "general",
        "requires_grounding": False
    }

def format_belief_context_for_system_prompt(user_id: str = "default") -> str:
    """Format belief context for injection into system prompt."""
    beliefs = get_relevant_beliefs(user_id, limit=10)
    return format_belief_context(beliefs)

def auto_ground_claim(user_message: str, user_id: str = "default") -> Dict:
    """Automatically ground a claim from user input if it's high-risk.
    
    Returns grounding result with explanation.
    """
    category = detect_high_risk_input(user_message)
    if category:
        # In a full implementation, we would actually verify the claim here
        # For now, we'll just indicate that grounding is needed
        return {"is_supported": False, "explanation": f"Input contains {category} content that requires verification"}
    return {"is_supported": True, "explanation": "No high-risk claims detected"}

def format_belief_context(beliefs: List[Dict]) -> str:
    """Format beliefs for injection into system prompt."""
    if not beliefs:
        return ""
    
    context_lines = ["<belief_context>"]
    for belief in beliefs:
        line = f"  [{belief['status']}] {belief['claim']} (source: {belief['source_type']}"
        if belief['source_ref']:
            line += f", ref: {belief['source_ref']}"
        line += ")"
        context_lines.append(line)
    context_lines.append("</belief_context>")
    
    return "\n".join(context_lines)