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
        r"I (?:got|received|was|am|was offered) a job(?: offer)?",
        "interview", "offer", "rejected", "accepted", "recruiter", 
        "job application", "hiring", "employment"
    ],
    "server_state": [
        "running", "stopped", "up", "down", "crashed", "status",
        "disk.*%", "memory.*%", "process", "service"
    ] + [
        r"(?:server|system|service) (?:is|was|has been) (?:down|up|running|stopped|crashed)",
        r"(?:disk|memory) (?:usage|utilization) is (?:at|over|under) \d+%"
    ],
    "configuration": [
        "config", "setting", "cron", "schedule", "environment",
        "variable", "parameter", "option"
    ] + [
        r"(?:config|configuration|setting|parameter) (?:is|was|has been) set to [^,.;]*",
        r"(?:port|cron|schedule|environment) (?:is|was) \d+"
    ],
    "specific_numbers": [
        r"\b\d{4}-\d{2}-\d{2}\b",  # Dates
        r"\b\d{1,2}:\d{2}\b",      # Times
        r"\b\d+(?:\.\d+)?\b"       # Numbers (including decimals)
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
    provenance: str = None,
    expiration_hours: int = 24
) -> Dict:
    """Ground a claim in the belief store.
    
    Path A (automatic): source_type='tool' with VERIFIED status
    Path B (voluntary): source_type='user_statement' with VERIFIED/INFERRED status
    
    Returns the belief record.
    """
    conn = initialize_belief_store(user_id)
    
    # Set expiration time based on status and parameters
    if status == "VERIFIED":
        # Verified claims don't expire by default
        expiration_time = None
    else:
        # Inferred claims expire based on parameter (default 24 hours)
        expiration_time = time.time() + (expiration_hours * 60 * 60)
    
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
            provenance, supersedes_id, created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, claim, status, source_type, source_ref,
        provenance, supersedes_id, current_time, current_time, expiration_time
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
        "updated_at": current_time,
        "expires_at": expiration_time
    }

def update_belief_expiration(belief_id: int, new_expiration_time: float, user_id: str) -> bool:
    """Update the expiration time for a specific belief."""
    try:
        conn = initialize_belief_store(user_id)
        cursor = conn.execute("""
            UPDATE beliefs 
            SET expires_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
        """, (new_expiration_time, time.time(), belief_id, user_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"Error updating belief expiration: {e}")
        return False

def get_expired_beliefs(user_id: str) -> List[Dict]:
    """Get all expired beliefs for a user."""
    try:
        conn = initialize_belief_store(user_id)
        current_time = time.time()
        cursor = conn.execute("""
            SELECT id, claim, status, source_type, source_ref, created_at, expires_at
            FROM beliefs
            WHERE user_id = ? AND expires_at IS NOT NULL AND expires_at < ?
        """, (user_id, current_time))
        
        expired_beliefs = cursor.fetchall()
        conn.close()
        return [dict(belief) for belief in expired_beliefs]
    except Exception as e:
        print(f"Error retrieving expired beliefs: {e}")
        return []

def extend_belief_expiration(belief_id: int, extension_hours: int, user_id: str) -> bool:
    """Extend the expiration time for a specific belief."""
    try:
        conn = initialize_belief_store(user_id)
        # First get the current expiration time
        cursor = conn.execute("""
            SELECT expires_at FROM beliefs 
            WHERE id = ? AND user_id = ?
        """, (belief_id, user_id))
        
        result = cursor.fetchone()
        if not result or result["expires_at"] is None:
            return False
            
        new_expiration_time = result["expires_at"] + (extension_hours * 60 * 60)
        return update_belief_expiration(belief_id, new_expiration_time, user_id)
    except Exception as e:
        print(f"Error extending belief expiration: {e}")
        return False

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
    
    current_time = time.time()
    
    # Escape the claim for FTS5 - wrap in double quotes to treat as phrase
    # Also escape any double quotes in the claim
    escaped_claim = '"' + claim.replace('"', '""') + '"'
    
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
    """, (escaped_claim, user_id, current_time))
    
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
        for pattern in keywords:
            # Check if pattern is a regex (contains special regex characters)
            if isinstance(pattern, str) and any(c in pattern for c in r'.*+?^${}()|[]\\'):
                # It's a regex pattern
                if re.search(pattern, user_message, re.IGNORECASE):
                    # Determine if this category requires grounding
                    # All high-risk categories should require grounding
                    requires_grounding = True
                    return {
                        "category": category,
                        "requires_grounding": requires_grounding,
                        "matched_pattern": pattern
                    }
            else:
                # It's a simple keyword
                if pattern in message_lower:
                    # Determine if this category requires grounding
                    # All high-risk categories should require grounding
                    requires_grounding = True
                    return {
                        "category": category,
                        "requires_grounding": requires_grounding,
                        "matched_keyword": pattern
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
        # Extract potential claims based on category
        claims = extract_claims_from_input(user_message, category)
        
        # Verify each claim
        verification_results = []
        for claim in claims:
            verification = verify_claim(claim, user_id, category)
            verification_results.append(verification)
        
        # Determine overall result
        unsupported_claims = [v for v in verification_results if not v["is_supported"]]
        if unsupported_claims:
            explanations = [v["explanation"] for v in unsupported_claims]
            return {
                "is_supported": False, 
                "explanation": "Input contains unverified claims: " + "; ".join(explanations),
                "claims": verification_results
            }
        else:
            return {
                "is_supported": True, 
                "explanation": "All claims in input have been verified",
                "claims": verification_results
            }
    return {"is_supported": True, "explanation": "No high-risk claims detected"}

def extract_claims_from_input(user_message: str, category: str) -> List[str]:
    """Extract specific claims from user input based on category."""
    claims = []
    
    if category == "job_status":
        # Look for job-related claims
        job_patterns = [
            r"I (?:got|received|was|am|was offered) a job(?: offer)?",
            r"I was (?:rejected|accepted|hired|fired)",
            r"I have an interview",
            r"I (?:applied for|am applying for) a job",
            r"(?:Recruiter|HR|Company) (?:contacted|called|emailed|replied)"
        ]
        
        for pattern in job_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            claims.extend(matches)
            
    elif category == "server_state":
        # Look for server-related claims
        server_patterns = [
            r"(?:server|system|service) (?:is|was|has been) (?:down|up|running|stopped|crashed)",
            r"(?:disk|memory) (?:usage|utilization) is (?:at|over|under) \d+%",
            r"(?:process|service) (?:is|was) (?:running|stopped|crashed)"
        ]
        
        for pattern in server_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            claims.extend(matches)
            
    elif category == "configuration":
        # Look for configuration claims
        config_patterns = [
            r"(?:config|configuration|setting|parameter) (?:is|was|has been) set to [^,.;]*",
            r"(?:port|cron|schedule|environment) (?:is|was) \d+",
            r"(?:variable|option) (?:is|was) [^,.;]*"
        ]
        
        for pattern in config_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            claims.extend(matches)
            
    elif category == "specific_numbers":
        # Extract specific numbers and dates
        number_patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",  # Dates
            r"\b\d{1,2}:\d{2}\b",      # Times
            r"\b\d+(?:\.\d+)?\b"       # Numbers (including decimals)
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, user_message)
            claims.extend(matches)
    
    # If no specific claims found, use the whole message
    if not claims:
        claims = [user_message]
        
    return claims

def verify_claim(claim: str, user_id: str, category: str) -> Dict:
    """Verify a specific claim against the belief store."""
    result = check_claim(claim, user_id)
    if result["status"] in ["VERIFIED", "INFERRED"]:
        # Additional context checks based on category
        if category == "job_status":
            # For job status claims, check if they align with recent user statements
            return {
                "is_supported": True, 
                "explanation": f"Claim consistent with {result['status']} belief", 
                "belief_check": result,
                "confidence": "high" if result["status"] == "VERIFIED" else "medium"
            }
        elif category == "server_state":
            # For server state, check if the state is recent
            current_time = time.time()
            if result["expires_at"] and result["expires_at"] < current_time:
                return {
                    "is_supported": False,
                    "explanation": "Claim found but belief is expired",
                    "belief_check": result,
                    "confidence": "low"
                }
            return {
                "is_supported": True,
                "explanation": f"Claim consistent with {result['status']} belief",
                "belief_check": result,
                "confidence": "high" if result["status"] == "VERIFIED" else "medium"
            }
    else:
        return {
            "is_supported": False, 
            "explanation": "Claim not found in belief store and requires verification", 
            "belief_check": result,
            "confidence": "none"
        }

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