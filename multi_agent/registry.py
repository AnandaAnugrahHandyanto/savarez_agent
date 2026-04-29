#!/usr/bin/env python3
"""
Team Registry - Team and Agent Tracking with Snapshot/Restore

Provides:
- Registration of all active teams and their agents
- Team snapshot and restore capability
- Integration with Hermes session system
- Persistence of team state across sessions

Inspired by OpenHarness's Team Registry design.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentSnapshot:
    """Snapshot of a sub-agent at a point in time."""
    agent_id: str
    task_id: str
    role: Optional[str]
    status: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    result_summary: Optional[str] = None


@dataclass
class TeamSnapshot:
    """
    A point-in-time snapshot of a team's state.
    
    Can be serialized to JSON for persistence and later restored.
    """
    team_id: str
    name: str
    status: str
    config: Any  # TeamConfig
    shared_state: Dict[str, Any]
    completed_tasks: Dict[str, Any]
    
    # Timing
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Agent snapshots
    agents: List[AgentSnapshot] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "team_id": self.team_id,
            "name": self.name,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "config": {
                "max_subagents": self.config.max_subagents if hasattr(self.config, 'max_subagents') else self.config.get("max_subagents", 5),
                "default_timeout": self.config.default_timeout if hasattr(self.config, 'default_timeout') else self.config.get("default_timeout", 300),
            },
            "shared_state": self.shared_state,
            "completed_tasks": self.completed_tasks,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "task_id": a.task_id,
                    "role": a.role,
                    "status": a.status,
                    "created_at": a.created_at,
                    "started_at": a.started_at,
                    "completed_at": a.completed_at,
                    "result_summary": a.result_summary,
                }
                for a in self.agents
            ],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamSnapshot":
        """Create TeamSnapshot from dictionary."""
        from .team import TeamStatus
        
        config_data = data.get("config", {})
        
        return cls(
            team_id=data["team_id"],
            name=data["name"],
            status=data["status"],
            config=config_data,
            shared_state=data.get("shared_state", {}),
            completed_tasks=data.get("completed_tasks", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            agents=[
                AgentSnapshot(
                    agent_id=a["agent_id"],
                    task_id=a["task_id"],
                    role=a.get("role"),
                    status=a["status"],
                    created_at=a["created_at"],
                    started_at=a.get("started_at"),
                    completed_at=a.get("completed_at"),
                    result_summary=a.get("result_summary"),
                )
                for a in data.get("agents", [])
            ],
        )


class TeamRegistry:
    """
    Central registry for all active teams.
    
    Tracks:
    - All active teams and their metadata
    - Team snapshots for persistence
    - Session integration
    
    The registry is a singleton per Hermes instance.
    """
    
    _instance: Optional["TeamRegistry"] = None
    _instance_lock = threading.Lock()
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize the TeamRegistry.
        
        Args:
            registry_path: Path to store team snapshots (default: ~/.hermes/multi_agent_teams/)
        """
        self._teams: Dict[str, Any] = {}  # team_id -> Team
        self._snapshots: Dict[str, TeamSnapshot] = {}  # team_id -> TeamSnapshot
        self._lock = threading.RLock()
        
        # Set registry path
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            # Default to ~/.hermes/multi_agent_teams/
            home = os.path.expanduser("~")
            self.registry_path = Path(home) / ".hermes" / "multi_agent_teams"
        
        # Ensure directory exists
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        # Load any existing snapshots
        self._load_snapshots()
        
        logger.info(f"TeamRegistry initialized at {self.registry_path}")
    
    @classmethod
    def get_instance(cls, registry_path: Optional[str] = None) -> "TeamRegistry":
        """Get singleton instance of TeamRegistry."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(registry_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance._teams.clear()
                cls._instance._snapshots.clear()
            cls._instance = None
    
    def register_team(self, team: Any) -> None:
        """
        Register a new team.
        
        Args:
            team: The Team instance to register
        """
        with self._lock:
            self._teams[team.team_id] = team
            logger.info(f"Registered team {team.team_id} ({team.name})")
    
    def unregister_team(self, team_id: str) -> None:
        """
        Unregister a team.
        
        Args:
            team_id: The team ID to unregister
        """
        with self._lock:
            if team_id in self._teams:
                del self._teams[team_id]
                logger.info(f"Unregistered team {team_id}")
    
    def get_team(self, team_id: str) -> Optional[Any]:
        """
        Get a registered team by ID.
        
        Args:
            team_id: The team ID
            
        Returns:
            The Team instance or None if not found
        """
        with self._lock:
            return self._teams.get(team_id)
    
    def list_teams(
        self,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all registered teams.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of team info dictionaries
        """
        with self._lock:
            teams = []
            for team in self._teams.values():
                info = {
                    "team_id": team.team_id,
                    "name": team.name,
                    "status": team.status.value if hasattr(team.status, 'value') else str(team.status),
                    "created_at": team.created_at.isoformat() if isinstance(team.created_at, datetime) else str(team.created_at),
                    "started_at": team.started_at.isoformat() if team.started_at else None,
                    "completed_at": team.completed_at.isoformat() if team.completed_at else None,
                }
                
                if status_filter is None or info["status"] == status_filter:
                    teams.append(info)
            
            return teams
    
    def create_snapshot(self, team_id: str) -> Optional[TeamSnapshot]:
        """
        Create a snapshot of a team's current state.
        
        Args:
            team_id: The team ID
            
        Returns:
            TeamSnapshot or None if team not found
        """
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return None
            
            snapshot = team.to_snapshot()
            self._snapshots[team_id] = snapshot
            
            # Persist to disk
            self._save_snapshot(snapshot)
            
            return snapshot
    
    def restore_snapshot(self, team_id: str) -> Optional[TeamSnapshot]:
        """
        Restore a team from a snapshot.
        
        Args:
            team_id: The team ID to restore
            
        Returns:
            TeamSnapshot or None if no snapshot exists
        """
        with self._lock:
            return self._snapshots.get(team_id)
    
    def _save_snapshot(self, snapshot: TeamSnapshot) -> None:
        """Persist snapshot to disk."""
        try:
            filepath = self.registry_path / f"{snapshot.team_id}.json"
            with open(filepath, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
            logger.debug(f"Saved snapshot for team {snapshot.team_id}")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
    
    def _load_snapshots(self) -> None:
        """Load any existing snapshots from disk."""
        try:
            for filepath in self.registry_path.glob("*.json"):
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    snapshot = TeamSnapshot.from_dict(data)
                    self._snapshots[snapshot.team_id] = snapshot
                except Exception as e:
                    logger.warning(f"Failed to load snapshot {filepath}: {e}")
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
    
    def delete_snapshot(self, team_id: str) -> bool:
        """
        Delete a team snapshot.
        
        Args:
            team_id: The team ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            # Remove from memory
            if team_id in self._snapshots:
                del self._snapshots[team_id]
            
            # Remove from disk
            filepath = self.registry_path / f"{team_id}.json"
            if filepath.exists():
                filepath.unlink()
                logger.info(f"Deleted snapshot for team {team_id}")
                return True
            
            return False
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List all available snapshots.
        
        Returns:
            List of snapshot info dictionaries
        """
        with self._lock:
            return [
                {
                    "team_id": s.team_id,
                    "name": s.name,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if isinstance(s.created_at, datetime) else s.created_at,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in self._snapshots.values()
            ]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            team_statuses = {}
            for team in self._teams.values():
                status = team.status.value if hasattr(team.status, 'value') else str(team.status)
                team_statuses[status] = team_statuses.get(status, 0) + 1
            
            return {
                "total_teams": len(self._teams),
                "total_snapshots": len(self._snapshots),
                "team_statuses": team_statuses,
                "registry_path": str(self.registry_path),
            }
    
    def cleanup_completed(self, older_than_hours: float = 24) -> int:
        """
        Clean up completed team snapshots older than specified hours.
        
        Args:
            older_than_hours: Only delete snapshots older than this
            
        Returns:
            Number of snapshots deleted
        """
        cutoff = datetime.now().timestamp() - (older_than_hours * 3600)
        deleted = 0
        
        with self._lock:
            to_delete = []
            
            for team_id, snapshot in self._snapshots.items():
                if snapshot.completed_at:
                    if isinstance(snapshot.completed_at, datetime):
                        ts = snapshot.completed_at.timestamp()
                    else:
                        continue
                    
                    if ts < cutoff:
                        to_delete.append(team_id)
            
            for team_id in to_delete:
                if self.delete_snapshot(team_id):
                    deleted += 1
        
        return deleted


def get_registry(registry_path: Optional[str] = None) -> TeamRegistry:
    """
    Get the TeamRegistry singleton.
    
    Args:
        registry_path: Optional custom registry path
        
    Returns:
        TeamRegistry instance
    """
    return TeamRegistry.get_instance(registry_path)
