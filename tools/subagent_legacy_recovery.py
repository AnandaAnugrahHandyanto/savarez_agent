"""
Fix for subagent_legacy_recovery (Issue #594)
=============================================
Problem: Sub-session death amnesia - after subagent completes, artifacts are lost and cannot be recovered

Root Cause Analysis:
- In delegate_tool.py, subagent results are returned to parent but NOT persisted
- When parent dies, subagent artifacts (files created, terminal state, etc.) become orphaned
- No checkpoint mechanism exists for subagent working state
- The _active_subagents registry only tracks live agents, not completed ones

Fix Implementation:
1. Add persistent storage for subagent results under ~/.hermes/subagents/
2. Store subagent metadata, artifacts path, and final results
3. Add recovery mechanism to resume or inherit subagent artifacts
4. Implement subagent checkpoint before each significant operation
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

# New constants to add to delegate_tool.py
SUBAGENTS_LEGACY_DIR = "~/.hermes/subagents"
SUBAGENT_RESULT_TTL_HOURS = 24 * 7  # Keep results for 7 days

# Thread-safe registry for subagent legacy data
_legacy_registry_lock = threading.Lock()
_legacy_registry: Dict[str, Dict[str, Any]] = {}


def _get_legacy_dir() -> Path:
    """Get the subagent legacy storage directory."""
    import os as _os
    path = Path(os.path.expanduser(SUBAGENTS_LEGACY_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _subagent_legacy_save(
    subagent_id: str,
    parent_id: Optional[str],
    goal: str,
    artifacts_dir: Optional[str] = None,
    final_result: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Persist subagent result to disk for legacy recovery.
    
    This allows parent agent to recover subagent artifacts if parent dies
    mid-execution or when resuming a session.
    
    Args:
        subagent_id: Unique identifier for the subagent
        parent_id: Parent's subagent_id (if any)
        goal: The task goal string
        artifacts_dir: Working directory used by subagent
        final_result: The complete result dict from _run_single_child
        metadata: Additional metadata (model, toolsets, duration, etc.)
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        legacy_dir = _get_legacy_dir()
        entry = {
            "subagent_id": subagent_id,
            "parent_id": parent_id,
            "goal": goal,
            "artifacts_dir": artifacts_dir,
            "final_result": final_result,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": final_result.get("status", "unknown") if final_result else "unknown",
        }
        
        # Write to disk atomically
        entry_path = legacy_dir / f"{subagent_id}.json"
        tmp_path = legacy_dir / f".{subagent_id}.tmp"
        
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        
        os.replace(tmp_path, entry_path)
        
        # Update in-memory registry
        with _legacy_registry_lock:
            _legacy_registry[subagent_id] = entry
        
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Failed to save subagent legacy: {e}")
        return False


def _subagent_legacy_load(subagent_id: str) -> Optional[Dict[str, Any]]:
    """
    Load persisted subagent result by ID.
    
    Returns the full entry dict or None if not found/expired.
    """
    # Check memory first
    with _legacy_registry_lock:
        if subagent_id in _legacy_registry:
            return _legacy_registry[subagent_id]
    
    # Load from disk
    try:
        entry_path = _get_legacy_dir() / f"{subagent_id}.json"
        if not entry_path.exists():
            return None
        
        with open(entry_path, 'r', encoding='utf-8') as f:
            entry = json.load(f)
        
        # Check TTL
        created_at = datetime.fromisoformat(entry.get("created_at", ""))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        if age_hours > SUBAGENT_RESULT_TTL_HOURS:
            # Expired - clean up
            try:
                entry_path.unlink()
            except OSError:
                pass
            return None
        
        # Update registry
        with _legacy_registry_lock:
            _legacy_registry[subagent_id] = entry
        
        return entry
    except Exception:
        return None


def _subagent_legacy_list(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all persisted subagent results.
    
    Optionally filter by parent_id.
    """
    legacy_dir = _get_legacy_dir()
    results = []
    
    for entry_path in legacy_dir.glob("*.json"):
        try:
            with open(entry_path, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            
            # Check TTL
            created_at = datetime.fromisoformat(entry.get("created_at", ""))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
            if age_hours > SUBAGENT_RESULT_TTL_HOURS:
                try:
                    entry_path.unlink()
                except OSError:
                    pass
                continue
            
            if parent_id is None or entry.get("parent_id") == parent_id:
                results.append(entry)
        except Exception:
            continue
    
    return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)


def _subagent_legacy_recover(
    subagent_id: str,
    inherit_artifacts: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Recover subagent artifacts and result after parent death.
    
    This allows a new parent session to inherit the working state
    of a previously completed subagent.
    
    Args:
        subagent_id: ID of the subagent to recover
        inherit_artifacts: If True, move artifacts to new session location
    
    Returns:
        Recovery manifest dict with artifacts info, or None if not found
    """
    entry = _subagent_legacy_load(subagent_id)
    if not entry:
        return None
    
    recovery = {
        "subagent_id": subagent_id,
        "goal": entry.get("goal"),
        "status": entry.get("status"),
        "artifacts_dir": entry.get("artifacts_dir"),
        "final_result": entry.get("final_result"),
        "metadata": entry.get("metadata", {}),
        "completed_at": entry.get("completed_at"),
    }
    
    if inherit_artifacts and entry.get("artifacts_dir"):
        # In production, would move/copy artifacts to new session location
        # For now, just verify the path exists
        artifacts_path = Path(os.path.expanduser(entry["artifacts_dir"]))
        recovery["artifacts_available"] = artifacts_path.exists()
        recovery["artifacts_path"] = str(artifacts_path)
    
    return recovery


def _subagent_legacy_cleanup(subagent_ids: Optional[List[str]] = None) -> int:
    """
    Clean up expired or specified subagent legacy entries.
    
    Args:
        subagent_ids: Specific IDs to clean, or None for TTL-based cleanup
    
    Returns:
        Number of entries cleaned
    """
    legacy_dir = _get_legacy_dir()
    cleaned = 0
    
    if subagent_ids:
        for sid in subagent_ids:
            try:
                entry_path = legacy_dir / f"{sid}.json"
                if entry_path.exists():
                    entry_path.unlink()
                    with _legacy_registry_lock:
                        _legacy_registry.pop(sid, None)
                    cleaned += 1
            except OSError:
                pass
    else:
        # TTL-based cleanup
        now = datetime.now(timezone.utc)
        for entry_path in legacy_dir.glob("*.json"):
            try:
                with open(entry_path, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                
                created_at = datetime.fromisoformat(entry.get("created_at", ""))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                age_hours = (now - created_at).total_seconds() / 3600
                if age_hours > SUBAGENT_RESULT_TTL_HOURS:
                    entry_path.unlink()
                    with _legacy_registry_lock:
                        _legacy_registry.pop(entry.get("subagent_id"), None)
                    cleaned += 1
            except Exception:
                continue
    
    return cleaned


# ============================================================================
# INTEGRATION PATCHES for delegate_tool.py
# ============================================================================
"""
To integrate these fixes, add the following patches to delegate_tool.py:

1. In _run_single_child() around line 1850, add:
   
   # LEGACY RECOVERY FIX: Persist subagent result before cleanup
   _subagent_legacy_save(
       subagent_id=_subagent_id,
       parent_id=parent_subagent_id,
       goal=goal,
       artifacts_dir=getattr(child, '_working_dir', None),
       final_result=entry,
       metadata={
           'model': getattr(child, '_model_name', None),
           'duration_seconds': duration,
           'tool_count': entry.get('tool_calls', 0) if isinstance(entry, dict) else 0,
       }
   )

2. Add a new tool function 'subagent_recover' that calls _subagent_legacy_recover()

3. Add periodic cleanup in the main loop calling _subagent_legacy_cleanup()

4. Modify delegate_task signature to accept 'recover_from_subagent' parameter
   that allows resuming from a previous subagent's artifacts
"""
