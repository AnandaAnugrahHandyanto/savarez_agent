#!/usr/bin/env python3
"""
Team - Multi-Agent Team Definition and Lifecycle Management

A Team represents a coordinated group of agents working together on a shared objective.
Each team has:
- A unique ID for tracking
- A parent agent that spawned the team
- A set of sub-agents managed by an AgentPool
- Shared state accessible to all team members
- A message bus for inter-agent communication
"""

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TeamStatus(Enum):
    """Lifecycle states for a Team."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TeamConfig:
    """Configuration for a Team."""
    max_subagents: int = 5
    default_timeout: int = 300  # seconds
    enable_message_bus: bool = True
    enable_result_aggregation: bool = True
    auto_cleanup_on_complete: bool = True


@dataclass
class Team:
    """
    A managed group of agents working collaboratively.
    
    The Team coordinates sub-agents through:
    - An AgentPool for lifecycle management
    - A MessageBus for inter-agent communication  
    - A ResultAggregator for collecting outputs
    
    The parent agent retains oversight and can:
    - Monitor team progress
    - Interrupt sub-agents
    - Retry failed tasks
    - Cancel the entire team
    """
    team_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "default"
    status: TeamStatus = TeamStatus.INITIALIZING
    config: TeamConfig = field(default_factory=TeamConfig)
    parent_agent: Any = field(default=None, repr=False)
    
    # Sub-components (initialized in __post_init__)
    _agent_pool: Any = field(default=None, repr=False)
    _message_bus: Any = field(default=None, repr=False)
    _result_aggregator: Any = field(default=None, repr=False)
    
    # Shared team state
    shared_state: Dict[str, Any] = field(default_factory=dict)
    _state_lock: threading.RLock = field(default_factory=threading.RLock)
    
    # Callbacks
    _progress_callback: Optional[Callable] = field(default=None)
    _completion_callback: Optional[Callable] = field(default=None)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = field(default=None)
    completed_at: Optional[datetime] = field(default=None)
    
    # Task tracking
    _tasks: Dict[str, "Task"] = field(default_factory=dict)
    _completed_tasks: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize sub-components after dataclass initialization."""
        # Import here to avoid circular dependencies
        from .agent_pool import AgentPool
        from .message_bus import MessageBus
        from .result_aggregator import ResultAggregator
        
        # Create sub-components unless they were provided
        if self._agent_pool is None:
            self._agent_pool = AgentPool(
                max_agents=self.config.max_subagents,
                parent_agent=self.parent_agent
            )
        
        if self._message_bus is None and self.config.enable_message_bus:
            self._message_bus = MessageBus(team_id=self.team_id)
        
        if self._result_aggregator is None and self.config.enable_result_aggregation:
            self._result_aggregator = ResultAggregator()
    
    @property
    def agent_pool(self) -> "AgentPool":
        """Access the agent pool."""
        return self._agent_pool
    
    @property
    def message_bus(self) -> Optional["MessageBus"]:
        """Access the message bus."""
        return self._message_bus
    
    @property
    def result_aggregator(self) -> "ResultAggregator":
        """Access the result aggregator."""
        return self._result_aggregator
    
    async def start(self) -> None:
        """Start the team and begin task execution."""
        if self.status != TeamStatus.INITIALIZING:
            raise RuntimeError(f"Cannot start team from status: {self.status}")
        
        self.status = TeamStatus.RUNNING
        self.started_at = datetime.now()
        logger.info(f"Team {self.team_id} started")
        
        # Start message bus if enabled
        if self._message_bus:
            await self._message_bus.start()
    
    async def pause(self) -> None:
        """Pause team execution (pause all sub-agents)."""
        if self.status != TeamStatus.RUNNING:
            raise RuntimeError(f"Cannot pause team from status: {self.status}")
        
        self.status = TeamStatus.PAUSED
        logger.info(f"Team {self.team_id} paused")
        
        # Pause all active sub-agents
        await self._agent_pool.pause_all()
    
    async def resume(self) -> None:
        """Resume paused team execution."""
        if self.status != TeamStatus.PAUSED:
            raise RuntimeError(f"Cannot resume team from status: {self.status}")
        
        self.status = TeamStatus.RUNNING
        logger.info(f"Team {self.team_id} resumed")
        
        # Resume all paused sub-agents
        await self._agent_pool.resume_all()
    
    async def cancel(self) -> None:
        """Cancel team execution and all sub-agents."""
        if self.status in (TeamStatus.COMPLETED, TeamStatus.CANCELLED):
            return
        
        self.status = TeamStatus.CANCELLED
        logger.info(f"Team {self.team_id} cancelled")
        
        # Cancel all sub-agents
        await self._agent_pool.cancel_all()
        
        if self._message_bus:
            await self._message_bus.stop()
    
    async def complete(self) -> Dict[str, Any]:
        """
        Mark team as completed and aggregate results.
        
        Returns:
            Dictionary containing aggregated results from all sub-agents
        """
        if self.status != TeamStatus.RUNNING:
            raise RuntimeError(f"Cannot complete team from status: {self.status}")
        
        self.status = TeamStatus.COMPLETING
        logger.info(f"Team {self.team_id} completing")
        
        # Aggregate results from all completed tasks
        aggregated = await self._aggregate_results()
        
        # Cleanup if configured
        if self.config.auto_cleanup_on_complete:
            await self._cleanup()
        
        self.status = TeamStatus.COMPLETED
        self.completed_at = datetime.now()
        
        if self._completion_callback:
            try:
                self._completion_callback(aggregated)
            except Exception as e:
                logger.warning(f"Completion callback failed: {e}")
        
        logger.info(f"Team {self.team_id} completed")
        return aggregated
    
    async def _aggregate_results(self) -> Dict[str, Any]:
        """Aggregate results from all completed tasks."""
        if not self._result_aggregator:
            return {"results": list(self._completed_tasks.values())}
        
        return await self._result_aggregator.aggregate(
            list(self._completed_tasks.values())
        )
    
    async def _cleanup(self) -> None:
        """Clean up team resources."""
        # Stop message bus
        if self._message_bus:
            await self._message_bus.stop()
        
        # Shutdown agent pool
        await self._agent_pool.shutdown()
    
    def add_task_result(self, task_id: str, result: Any) -> None:
        """Store a completed task result."""
        with self._state_lock:
            self._completed_tasks[task_id] = result
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Retrieve a task result by ID."""
        return self._completed_tasks.get(task_id)
    
    def set_shared_state(self, key: str, value: Any) -> None:
        """Set a shared state value accessible to all team members."""
        with self._state_lock:
            self.shared_state[key] = value
    
    def get_shared_state(self, key: str) -> Optional[Any]:
        """Get a shared state value."""
        with self._state_lock:
            return self._shared_state.get(key)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current team progress."""
        total = len(self._tasks)
        completed = len(self._completed_tasks)
        
        return {
            "team_id": self.team_id,
            "name": self.name,
            "status": self.status.value,
            "total_tasks": total,
            "completed_tasks": completed,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
            "active_agents": self._agent_pool.active_count if self._agent_pool else 0,
            "elapsed_seconds": (
                (datetime.now() - self.started_at).total_seconds()
                if self.started_at else 0
            ),
        }
    
    def to_snapshot(self) -> "TeamSnapshot":
        """Create a snapshot of the current team state."""
        from .registry import TeamSnapshot
        
        return TeamSnapshot(
            team_id=self.team_id,
            name=self.name,
            status=self.status,
            config=self.config,
            shared_state=dict(self.shared_state),
            completed_tasks=dict(self._completed_tasks),
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


@dataclass
class TeamContext:
    """
    Context passed to sub-agents when spawned within a team.
    
    Provides access to team-level resources like:
    - Shared state
    - Message bus for inter-agent communication
    - Team configuration
    """
    team_id: str
    team_name: str
    parent_agent: Any
    shared_state: Dict[str, Any]
    message_bus: Optional["MessageBus"] = None
    config: TeamConfig = field(default_factory=TeamConfig)
    
    @property
    def is_team_context(self) -> bool:
        return True


def create_team(
    name: str,
    parent_agent: Any,
    config: Optional[TeamConfig] = None,
    max_subagents: int = 5,
    default_timeout: int = 300,
) -> Team:
    """
    Factory function to create a new Team.
    
    Args:
        name: Human-readable team name
        parent_agent: The parent AIAgent instance that spawned this team
        config: Optional TeamConfig instance
        max_subagents: Maximum number of concurrent sub-agents
        default_timeout: Default timeout for sub-agent tasks in seconds
    
    Returns:
        A new Team instance in INITIALIZING state
    """
    if config is None:
        config = TeamConfig(
            max_subagents=max_subagents,
            default_timeout=default_timeout,
        )
    
    team = Team(
        name=name,
        parent_agent=parent_agent,
        config=config,
    )
    
    return team
