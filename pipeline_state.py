#!/usr/bin/env python3"""
Pipeline State Management for Hermes Agent.

Provides state tracking for work items moving through the trusted change pipeline.
Each work item has:
- Current stage in the pipeline
- Required artifacts collected
- Packet history (blocker, environment, completion)
- Links to GitHub issue/PR/branch

This is self-orchestration state - Hermes routes itself through stages,
checking required artifacts before advancing.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ── Pipeline Stages ──

PIPELINE_STAGES = [
    # Intake / Verification Lane
    "scout",              # Intake, optional
    "research-verify",    # First hard gate
    "plan-review",        # Plan sanity check
    
    # Repo-fit Lane (parallel reviews, synthesized by Repo Steward)
    "scope-steward",      # Domain fit
    "architecture-verify",# Technical architecture
    "integration-steward",# Integration surfaces
    "repo-steward",       # Synthesis
    
    # Execution Approval
    "issue-approve",      # Go/no-go
    "branch-create",       # Execution surface
    
    # Delivery Lane
    "delivery-manager",   # Orchestration node
    "spec-design",        # Specification
    "spec-verify",        # Spec verification
    "pr-create",          # Early draft PR
    "red-test",           # Failing tests
    "code-build",         # Implementation
    "cleanup",            # Local cleanup
    "green-test",         # Passing tests
    "tdd-refactor",       # Post-proof refactoring
    "review-improve",     # Review hardening
    "pr-maintain",        # PR packaging
    "wisdom",             # Learning capture
    "merge",              # Integration
    "complete",           # Done
]

# Stage transitions with required artifacts
STAGE_TRANSITIONS = {
    "scout": {
        "next": "research-verify",
        "required_artifacts": [],  # Optional stage
        "can_skip": True,
    },
    "research-verify": {
        "next": "plan-review",
        "required_artifacts": ["verification_packet"],
        "uncertainty_removed": "false premises",
    },
    "plan-review": {
        "next": "scope-steward",  # Or skip directly to repo-steward
        "required_artifacts": ["review_packet"],
        "uncertainty_removed": "bad plans",
    },
    "scope-steward": {
        "next": "architecture-verify",  # Parallel track
        "required_artifacts": ["scope_packet"],
        "uncertainty_removed": "domain misfit",
        "parallel_group": "repo-fit",
    },
    "architecture-verify": {
        "next": "integration-steward",  # Parallel track
        "required_artifacts": ["architecture_packet"],
        "uncertainty_removed": "architecture misfit",
        "parallel_group": "repo-fit",
    },
    "integration-steward": {
        "next": "repo-steward",  # Parallel track
        "required_artifacts": ["integration_packet"],
        "uncertainty_removed": "integration misfit",
        "parallel_group": "repo-fit",
    },
    "repo-steward": {
        "next": "issue-approve",
        "required_artifacts": ["fit_packet"],
        "uncertainty_removed": "architectural incoherence",
        "synthesizes": ["scope-steward", "architecture-verify", "integration-steward"],
    },
    "issue-approve": {
        "next": "branch-create",
        "required_artifacts": ["github_issue_url"],
        "uncertainty_removed": "premature execution",
    },
    "branch-create": {
        "next": "delivery-manager",
        "required_artifacts": ["branch_name", "head_sha"],
        "uncertainty_removed": "execution ambiguity",
    },
    "delivery-manager": {
        "next": "spec-design",
        "required_artifacts": [],  # Orchestration node
        "uncertainty_removed": "execution coherence",
    },
    "spec-design": {
        "next": "spec-verify",
        "required_artifacts": ["spec_md"],
        "uncertainty_removed": "vague targets",
    },
    "spec-verify": {
        "next": "pr-create",
        "required_artifacts": ["verified_spec"],
        "uncertainty_removed": "undefined correctness",
    },
    "pr-create": {
        "next": "red-test",
        "required_artifacts": ["pr_url"],
        "uncertainty_removed": "untracked work",
    },
    "red-test": {
        "next": "code-build",
        "required_artifacts": ["failing_tests"],
        "uncertainty_removed": "no proof target",
    },
    "code-build": {
        "next": "cleanup",
        "required_artifacts": ["implementation_files"],
        "uncertainty_removed": "the defect/gap",
    },
    "cleanup": {
        "next": "green-test",
        "required_artifacts": ["clean_diff"],
        "uncertainty_removed": "incidental mess",
    },
    "green-test": {
        "next": "tdd-refactor",
        "required_artifacts": ["green_tests"],
        "uncertainty_removed": "correctness doubt",
    },
    "tdd-refactor": {
        "next": "review-improve",
        "required_artifacts": ["refactor_summary"],
        "uncertainty_removed": "structural clumsiness",
    },
    "review-improve": {
        "next": "pr-maintain",
        "required_artifacts": ["review_fixes"],
        "uncertainty_removed": "review debt",
    },
    "pr-maintain": {
        "next": "wisdom",
        "required_artifacts": ["pr_packet"],
        "uncertainty_removed": "legibility debt",
    },
    "wisdom": {
        "next": "merge",
        "required_artifacts": ["wisdom_packet"],
        "uncertainty_removed": "repeated rediscovery",
    },
    "merge": {
        "next": "complete",
        "required_artifacts": ["merge_sha"],
        "uncertainty_removed": "unjustified integration",
    },
    "complete": {
        "next": None,  # Terminal
        "required_artifacts": [],"uncertainty_removed": None,
    },
}

SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY,-- UUID
    github_issue_url TEXT,           -- GitHub issue URL (required after issue-approve)
    github_issue_number INTEGER,     -- Issue number for quick lookup
    title TEXT,-- Work item title
    description TEXT, -- Full description
    current_stage TEXT NOT NULL,      -- Current pipeline stage
    stage_entered_at REAL, -- Timestamp when entered current stage
    created_at REAL NOT NULL,
    updated_at REAL NOT
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id TEXT NOT NULL REFERENCES work_items(id),
    artifact_type TEXT NOT NULL,      -- verification_packet, branch_name, etc.
    artifact_data TEXT NOT NULL,      -- JSON payload
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id TEXT NOT NULL REFERENCES work_items(id),
    packet_type TEXT NOT NULL,        -- blocker, environment, escalation, completion
    packet_data TEXT NOT NULL,        -- JSON payload
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id TEXT NOT NULL REFERENCES work_items(id),
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    transitioned_at REAL NOT NULL,
    artifact_produced TEXT,           -- Artifact type that enabled transition
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_work_items_stage ON work_items(current_stage);
CREATE INDEX IF NOT EXISTS idx_work_items_issue ON work_items(github_issue_url);
CREATE INDEX IF NOT EXISTS idx_artifacts_work_item ON artifacts(work_item_id);
CREATE INDEX IF NOT EXISTS idx_packets_work_item ON packets(work_item_id);
CREATE INDEX IF NOT EXISTS idx_stage_history_work_item ON stage_history(work_item_id);
"""


class PipelineStateDB:
    """
    SQLite-backed pipeline state for work items.
    
    Tracks:
    - Work items and their current stage
    - Artifacts collected at each stage
    - Packets emitted (blocker, environment, escalation, completion)
    - Stage transition history
    
    Thread-safe with WAL mode for concurrent access.
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or (get_hermes_home() / "pipeline_state.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=5.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        
        self._init_schema()
    
    def _init_schema(self):
        """Create tables if they don't exist."""
        cursor = self._conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        
        # Check schema version
        cursor.execute("SELECT version FROM pipeline_schema_version LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO pipeline_schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
        
        self._conn.commit()
    
    # =========================================================================
    # Work Item Lifecycle
    # =========================================================================
    
    def create_work_item(
        self,
        title: str,
        description: str = None,
        github_issue_url: str = None,
        github_issue_number: int = None,
        start_stage: str = "scout",
    ) -> str:
        """Create a new work item. Returns the work item ID."""
        work_item_id = str(uuid.uuid4())
        now = time.time()
        
        def _do(conn):
            conn.execute(
                """INSERT INTO work_items (
                    id, title, description, github_issue_url, github_issue_number,
                    current_stage, stage_entered_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    work_item_id,
                    title,
                    description,
                    github_issue_url,
                    github_issue_number,
                    start_stage,
                    now,
                    now,
                    now,
                )
            )
        
        self._execute_write(_do)
        return work_item_id
    
    def get_work_item(self, work_item_id: str) -> Optional[Dict[str, Any]]:
        """Get work item by ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM work_items WHERE id = ?",
            (work_item_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    
    def get_work_item_by_issue(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get work item by GitHub issue number."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM work_items WHERE github_issue_number = ?",
            (issue_number,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    
    def update_stage(self, work_item_id: str, new_stage: str, notes: str = None) -> bool:
        """Transition work item to a new stage."""
        # Validate stage
        if new_stage not in PIPELINE_STAGES:
            logger.error(f"Invalid stage: {new_stage}")
            return False
        
        work_item = self.get_work_item(work_item_id)
        if work_item is None:
            logger.error(f"Work item not found: {work_item_id}")
            return False
        
        old_stage = work_item["current_stage"]
        now = time.time()
        
        def _do(conn):
            # Update work item
            conn.execute(
                """UPDATE work_items 
                   SET current_stage = ?, stage_entered_at = ?, updated_at = ?
                   WHERE id = ?""",
                (new_stage, now, now, work_item_id)
            )
            
            # Record transition
            conn.execute(
                """INSERT INTO stage_history (
                    work_item_id, from_stage, to_stage, transitioned_at, notes
                ) VALUES (?, ?, ?, ?, ?)""",
                (work_item_id, old_stage, new_stage, now, notes)
            )
        
        self._execute_write(_do)
        return True
    
    def link_github_issue(
        self,
        work_item_id: str,
        issue_url: str,
        issue_number: int
    ) -> bool:
        """Link work item to GitHub issue."""
        def _do(conn):
            conn.execute(
                """UPDATE work_items 
                   SET github_issue_url = ?, github_issue_number = ?, updated_at = ?
                   WHERE id = ?""",
                (issue_url, issue_number, time.time(), work_item_id)
            )
        self._execute_write(_do)
        return True
    
    # =========================================================================
    # Artifacts
    # =========================================================================
    
    def store_artifact(
        self,
        work_item_id: str,
        artifact_type: str,
        artifact_data: Dict[str, Any]
    ) -> int:
        """Store an artifact for a work item."""
        now = time.time()
        artifact_id = None
        
        def _do(conn):
            cursor = conn.execute(
                """INSERT INTO artifacts (
                    work_item_id, artifact_type, artifact_data, created_at
                ) VALUES (?, ?, ?, ?)""",
                (work_item_id, artifact_type, json.dumps(artifact_data), now)
            )
            artifact_id = cursor.lastrowid
        
        self._execute_write(_do)
        return artifact_id
    
    def get_artifact(
        self,
        work_item_id: str,
        artifact_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent artifact of a given type for a work item."""
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT artifact_data FROM artifacts 
               WHERE work_item_id = ? AND artifact_type = ?
               ORDER BY created_at DESC LIMIT 1""",
            (work_item_id, artifact_type)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["artifact_data"])
    
    def get_all_artifacts(self, work_item_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all artifacts for a work item, keyed by type (most recent per type)."""
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT artifact_type, artifact_data, MAX(created_at) as latest
               FROM artifacts
               WHERE work_item_id = ?
               GROUP BY artifact_type""",
            (work_item_id,)
        )
        rows = cursor.fetchall()
        return {
            row["artifact_type"]: json.loads(row["artifact_data"])
            for row in rows
        }
    
    def has_artifacts(self, work_item_id: str, artifact_types: List[str]) -> Tuple[bool, List[str]]:
        """Check if work item has all required artifact types.
        
        Returns:
            (has_all, missing_types)
        """
        artifacts = self.get_all_artifacts(work_item_id)
        missing = [t for t in artifact_types if t not in artifacts]
        return len(missing) == 0, missing
    
    # =========================================================================
    # Packets
    # =========================================================================
    
    def emit_packet(
        self,
        work_item_id: str,
        packet_type: str,
        packet_data: Dict[str, Any]
    ) -> int:
        """Emit a packet (blocker, environment, escalation, completion)."""
        now = time.time()
        packet_id = None
        
        def _do(conn):
            cursor = conn.execute(
                """INSERT INTO packets (
                    work_item_id, packet_type, packet_data, created_at
                ) VALUES (?, ?, ?, ?)""",
                (work_item_id, packet_type, json.dumps(packet_data), now)
            )
            packet_id = cursor.lastrowid
        
        self._execute_write(_do)
        return packet_id
    
    def get_latest_packet(
        self,
        work_item_id: str,
        packet_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent packet of a given type."""
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT packet_data FROM packets 
               WHERE work_item_id = ? AND packet_type = ?
               ORDER BY created_at DESC LIMIT 1""",
            (work_item_id, packet_type)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["packet_data"])
    
    def get_packet_history(
        self,
        work_item_id: str,
        packet_type: str = None
    ) -> List[Dict[str, Any]]:
        """Get all packets for a work item, optionally filtered by type."""
        cursor = self._conn.cursor()
        if packet_type:
            cursor.execute(
                """SELECT packet_type, packet_data, created_at FROM packets 
                   WHERE work_item_id = ? AND packet_type = ?
                   ORDER BY created_at DESC""",
                (work_item_id, packet_type)
            )
        else:
            cursor.execute(
                """SELECT packet_type, packet_data, created_at FROM packets 
                   WHERE work_item_id = ?
                   ORDER BY created_at DESC""",
                (work_item_id,)
            )
        rows = cursor.fetchall()
        return [
            {
                "packet_type": row["packet_type"],
                "packet_data": json.loads(row["packet_data"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    
    # =========================================================================
    # Stage History
    # =========================================================================
    
    def get_stage_history(self, work_item_id: str) -> List[Dict[str, Any]]:
        """Get the stage transition history for a work item."""
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT from_stage, to_stage, transitioned_at, artifact_produced, notes
               FROM stage_history
               WHERE work_item_id = ?
               ORDER BY transitioned_at ASC""",
            (work_item_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    # =========================================================================
    # Transition Validation
    # =========================================================================
    
    def can_advance(
        self,
        work_item_id: str,
        target_stage: str = None
    ) -> Tuple[bool, str, List[str]]:
        """Check if work item can advance to the next stage.
        
        Returns:
            (can_advance, reason, missing_artifacts)
        """
        work_item = self.get_work_item(work_item_id)
        if work_item is None:
            return False, "Work item not found", []
        
        current_stage = work_item["current_stage"]
        
        # Get transition definition
        transition = STAGE_TRANSITIONS.get(current_stage)
        if transition is None:
            return False, f"Unknown stage: {current_stage}", []
        
        next_stage = target_stage or transition["next"]
        if next_stage is None:
            return False, "No next stage (terminal)", []
        
        # Check required artifacts
        required = transition.get("required_artifacts", [])
        if required:
            has_all, missing = self.has_artifacts(work_item_id, required)
            if not has_all:
                return False, f"Missing artifacts: {missing}", missing
        
        return True, "Can advance", []
    
    def advance(
        self,
        work_item_id: str,
        target_stage: str = None,
        notes: str = None
    ) -> Tuple[bool, str]:
        """Attempt to advance work item to the next stage.
        
        Returns:
            (success, message)
        """
        can_advance, reason, missing = self.can_advance(work_item_id, target_stage)
        if not can_advance:
            return False, f"Cannot advance: {reason}"
        
        work_item = self.get_work_item(work_item_id)
        current_stage = work_item["current_stage"]
        transition = STAGE_TRANSITIONS.get(current_stage)
        next_stage = target_stage or transition["next"]
        
        if next_stage is None:
            return False, "No next stage (terminal)"
        
        success = self.update_stage(work_item_id, next_stage, notes)
        if success:
            return True, f"Advanced from {current_stage} to {next_stage}"
        else:
            return False, "Failed to update stage"
    
    # =========================================================================
    # Write Helper
    # =========================================================================
    
    def _execute_write(self, fn):
        """Execute a write transaction with retry logic."""
        last_err = None
        for attempt in range(10):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.commit()
                        return result
                    except BaseException:
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        raise
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if "locked" in err_msg or "busy" in err_msg:
                    last_err = exc
                    time.sleep(0.05 * (attempt + 1))
                    continue
                raise
        raise last_err or sqlite3.OperationalError("database is locked")
    
    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                except Exception:
                    pass
                self._conn.close()
                self._conn = None


# ── Packet Factories ──

def create_blocker_packet(
    agent_id: str,
    stage: str,
    error_class: str,
    exact_command: str,
    env_snapshot: Dict[str, Any],
    resolution_hint: str,
    related_issues: List[str] = None,
    context: str = None,
) -> Dict[str, Any]:
    """Create a blocker packet."""
    return {
        "blocker_id": f"blk-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "agent_id": agent_id,
        "stage": stage,
        "error_class": error_class,
        "exact_command": exact_command,
        "env_snapshot": env_snapshot,
        "resolution_hint": resolution_hint,
        "related_issues": related_issues or [],
        "context": context,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active",
    }


def create_environment_packet(
    agent_id: str,
    stage: str,
    repo_root: str,
    branch: str,
    toolchain: Dict[str, str],
    secrets_status: Dict[str, str],
    constraints: Dict[str, str],
) -> Dict[str, Any]:
    """Create an environment packet."""
    return {
        "environment_id": f"env-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "agent_id": agent_id,
        "stage": stage,
        "repo": {
            "root": repo_root,
            "branch": branch,
        },
        "toolchain": toolchain,
        "secrets_status": secrets_status,
        "constraints": constraints,
        "created_at": datetime.utcnow().isoformat(),
    }


def create_escalation_packet(
    agent_id: str,
    stage: str,
    context: str,
    blocker_type: str,
    exact_block: str,
    attempted_solutions: List[str],
    recommended_path: str,
    steven_requested: bool = False,
) -> Dict[str, Any]:
    """Create an escalation packet.

    Escalation is RARE. Use only when:
    - Steven explicitly asked to be involved
    - Literally cannot proceed (external authorization, permission, access)
    - Something genuinely broken (service down, credential invalid)

    For everything else - implementation approach, cross-repo coherence,
    technical tradeoffs, product-level tradeoffs - reason through it yourself.
    """
    return {
        "escalation_id": f"esc-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "agent_id": agent_id,
        "stage": stage,
        "context": context,
        "blocker_type": blocker_type,# "external_auth", "permission", "service_down", "credential_invalid", "steven_requested"
        "exact_block": exact_block,# The specific error/state that blocks progress
        "attempted_solutions": attempted_solutions,# What I already tried
        "recommended_path": recommended_path, # What Steven should do
        "steven_requested": steven_requested,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }


def create_completion_packet(
    agent_id: str,
    stage: str,
    issue_url: str = None,
    branch: str = None,
    summary: str = None,
    evidence_bundle: Dict[str, Any] = None,
    lessons_learned: List[str] = None,
    next_stage: str = None,
) -> Dict[str, Any]:
    """Create a completion packet."""
    return {
        "completion_id": f"comp-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
        "agent_id": agent_id,
        "stage": stage,
        "issue_url": issue_url,
        "branch": branch,
        "summary": summary,
        "evidence_bundle": evidence_bundle or {},
        "lessons_learned": lessons_learned or [],
        "next_stage": next_stage,
        "status": "completed",
        "created_at": datetime.utcnow().isoformat(),
    }