"""VDGP (Verifiable Decision Gate Propagation) module for quality gate verdict handling."""
import json
import logging
import sqlite3
from typing import Dict, Any, Optional

class GateVerdictError(ValueError):
    """Exception for invalid gate verdicts."""

def validate_gate_verdict(metadata: Dict[str, Any]) -> None:
    """Validate gate_verdict structure according to G4 requirements.
    
    Args:
        metadata: Task metadata dictionary
    
    Raises:
        GateVerdictError: For any validation failure
    """
    if 'gate_verdict' not in metadata:
        raise GateVerdictError("Missing 'gate_verdict' in metadata")
    
    verdict_data = metadata['gate_verdict']
    if not isinstance(verdict_data, dict):
        raise GateVerdictError("'gate_verdict' must be a dictionary")
    
    verdict = verdict_data.get('verdict')
    if verdict not in ['GO', 'NO-GO']:
        raise GateVerdictError(f"Invalid verdict: {verdict}. Must be 'GO' or 'NO-GO'")
    
    if 'reviewed_task' not in verdict_data:
        raise GateVerdictError("Missing 'reviewed_task' in gate_verdict")
    
    if verdict == 'NO-GO' and (not verdict_data.get('reasons') or 
                               not isinstance(verdict_data['reasons'], list) or 
                               len(verdict_data['reasons']) == 0):
        raise GateVerdictError("NO-GO verdict must have at least one reason")

def propagate_gate_verdict(
    conn: sqlite3.Connection, 
    gate_task_id: str, 
    verdict_data: Dict[str, Any]
) -> bool:
    """Propagate gate verdict to the reviewed task (idempotent operation).
    
    Args:
        conn: SQLite database connection
        gate_task_id: ID of the gate task
        verdict_data: Gate verdict dictionary
    
    Returns:
        True if propagation was performed, False if skipped (idempotent)
    """
    verdict = verdict_data['verdict']
    reviewed_task = verdict_data['reviewed_task']
    reasons = verdict_data.get('reasons', [])
    
    # Check for existing verdict event (idempotency)
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM task_events 
        WHERE task_id = ? AND kind IN ('gate_go', 'gate_nogo')
    """, (gate_task_id,))
    if cur.fetchone():
        return False  # Already processed
    
    # Check current status of reviewed task
    cur.execute("SELECT status FROM tasks WHERE id = ?", (reviewed_task,))
    row = cur.fetchone()
    if not row or row[0] != 'blocked':
        return False  # Task not blocked or doesn't exist
    
    # Record verdict event
    event_kind = 'gate_go' if verdict == 'GO' else 'gate_nogo'
    payload = {"reviewed_task": reviewed_task}

    # Use internal helpers from kanban_db
    from hermes_cli.kanban_db import _append_event, unblock_task, add_comment
    _append_event(conn, gate_task_id, event_kind, payload)

    # Both GO and NO-GO unblock the reviewed task (G2/G3):
    #   GO → auto-unblock to ready (review passes)
    #   NO-GO → auto-unblock to ready with reasons as comment (worker reworks)
    unblock_task(conn, reviewed_task)

    if verdict == 'NO-GO':
        comment = "Quality gate NO-GO:\n" + "\n".join(f"- {reason}" for reason in reasons)
        add_comment(conn, reviewed_task, "gate-verdict", comment)
    
    return True

def propagate_all_gate_verdicts(conn: sqlite3.Connection) -> int:
    """Sweep for recently completed quality-gate tasks and propagate verdicts.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        Number of verdicts propagated in this sweep
    """
    count = 0
    cur = conn.cursor()
    
    # Find completed tasks with gate_verdict in their latest run's metadata
    # that haven't been processed yet. Metadata lives on task_runs, not
    # on the tasks table, so we join to the most recent completed run.
    cur.execute("""
        SELECT t.id, r.metadata
        FROM tasks t
        JOIN task_runs r ON r.task_id = t.id
            AND r.outcome = 'completed'
            AND r.ended_at = (
                SELECT MAX(r2.ended_at) FROM task_runs r2
                WHERE r2.task_id = t.id AND r2.outcome = 'completed'
            )
        WHERE t.status = 'done'
        AND json_extract(r.metadata, '$.gate_verdict') IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM task_events
            WHERE task_id = t.id AND kind IN ('gate_go', 'gate_nogo')
        )
    """)
    
    for task_id, metadata_json in cur.fetchall():
        try:
            metadata = json.loads(metadata_json)
            verdict_data = metadata['gate_verdict']
            
            # Validate before propagation
            validate_gate_verdict(metadata)
            
            if propagate_gate_verdict(conn, task_id, verdict_data):
                count += 1
        except (GateVerdictError, json.JSONDecodeError) as e:
            # Log error but continue processing others
            logging.warning("VDGP: error processing task %s: %s", task_id, e)
    
    return count

def kanban_complete(
    conn: sqlite3.Connection, 
    task_id: str, 
    **kwargs
) -> bool:
    """Thin facade around complete_task with gate_verdict validation."""
    from hermes_cli.kanban_db import complete_task
    
    metadata = kwargs.get('metadata')
    if metadata and 'gate_verdict' in metadata:
        validate_gate_verdict(metadata)
    
    # Pass through to original implementation
    return complete_task(conn, task_id, **kwargs)