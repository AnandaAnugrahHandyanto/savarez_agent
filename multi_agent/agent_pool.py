#!/usr/bin/env python3
"""
Agent Pool - SubAgent Lifecycle and Resource Management

Manages the pool of sub-agents spawned within a team, providing:
- SubAgent creation and lifecycle tracking
- Resource limits per team
- Health monitoring and recovery
- Integration with existing delegate_task infrastructure

Each SubAgent wraps an AIAgent instance with team-specific context.
"""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubAgentStatus(Enum):
    """Lifecycle states for a SubAgent."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class SubAgentConfig:
    """Configuration for a SubAgent."""
    timeout: int = 300          # Max seconds before timeout
    max_retries: int = 2        # Retry attempts on failure
    health_check_interval: int = 30  # Seconds between health checks
    toolsets: List[str] = field(default_factory=list)
    model: Optional[str] = None
    role: Optional[str] = None   # e.g., "researcher", "coder"


@dataclass 
class SubAgent:
    """
    A sub-agent instance running within a team.
    
    Wraps an AIAgent with team-specific context and lifecycle tracking.
    """
    agent_id: str = field(default_factory=lambda: f"subagent_{uuid.uuid4().hex[:8]}")
    task_id: str = ""            # The task this agent is handling
    role: Optional[str] = None   # Role specialization
    
    # AIAgent instance
    agent: Any = field(default=None, repr=False)
    
    # Configuration
    config: SubAgentConfig = field(default_factory=SubAgentConfig)
    
    # Lifecycle state
    status: SubAgentStatus = SubAgentStatus.INITIALIZING
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = field(default=None)
    completed_at: Optional[datetime] = field(default=None)
    
    # Result
    result: Any = None
    error: Optional[str] = None
    
    # Parent references
    parent_agent: Any = field(default=None, repr=False)
    team_id: str = ""
    
    # Callbacks
    _progress_callback: Optional[Callable] = field(default=None, repr=False)
    
    # Threading
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _cancel_event: Optional[threading.Event] = field(default=None, repr=False)
    
    def __post_init__(self):
        if self._cancel_event is None:
            self._cancel_event = threading.Event()
    
    @property
    def is_alive(self) -> bool:
        """Check if the agent thread is still running."""
        return self._thread is not None and self._thread.is_alive()
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time since agent started."""
        if not self.started_at:
            return 0
        return (datetime.now() - self.started_at).total_seconds()
    
    def cancel(self) -> None:
        """Signal the agent to cancel."""
        if self._cancel_event:
            self._cancel_event.set()
        if self.agent and hasattr(self.agent, 'interrupt'):
            self.agent.interrupt()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current agent progress."""
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "role": self.role,
            "status": self.status.value,
            "elapsed_seconds": self.elapsed_seconds,
            "is_alive": self.is_alive,
        }


class AgentPool:
    """
    Manages a pool of sub-agents for a team.
    
    Provides:
    - Resource limits (max concurrent agents)
    - SubAgent creation via delegate_task integration
    - Health monitoring
    - Graceful shutdown
    
    The pool integrates with the existing delegate_task infrastructure
    to leverage its proven sub-agent spawning mechanism.
    """
    
    def __init__(
        self,
        max_agents: int = 5,
        parent_agent: Any = None,
        default_timeout: int = 300,
    ):
        """
        Initialize the AgentPool.
        
        Args:
            max_agents: Maximum concurrent sub-agents allowed
            parent_agent: The parent AIAgent instance
            default_timeout: Default timeout for sub-agents in seconds
        """
        self.max_agents = max_agents
        self.parent_agent = parent_agent
        self.default_timeout = default_timeout
        
        # Active sub-agents
        self._agents: Dict[str, SubAgent] = {}
        self._agents_lock = threading.RLock()
        
        # Task to agent mapping
        self._task_to_agent: Dict[str, str] = {}
        
        # Event for waiting on pool to be empty
        self._all_complete_event = threading.Event()
        
        logger.info(f"AgentPool initialized with max_agents={max_agents}")
    
    @property
    def active_count(self) -> int:
        """Number of currently active (running) agents."""
        with self._agents_lock:
            return sum(
                1 for a in self._agents.values()
                if a.status == SubAgentStatus.RUNNING
            )
    
    @property
    def total_count(self) -> int:
        """Total number of agents in the pool."""
        with self._agents_lock:
            return len(self._agents)
    
    def can_spawn(self) -> bool:
        """Check if a new agent can be spawned."""
        with self._agents_lock:
            return self.active_count < self.max_agents
    
    def get_available_slots(self) -> int:
        """Get number of available agent slots."""
        with self._agents_lock:
            return max(0, self.max_agents - self.active_count)
    
    def spawn_agent(
        self,
        task_id: str,
        goal: str,
        context: Optional[str] = None,
        toolsets: Optional[List[str]] = None,
        config: Optional[SubAgentConfig] = None,
        role: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> SubAgent:
        """
        Spawn a new sub-agent to handle a task.
        
        Args:
            task_id: Unique identifier for the task
            goal: The task goal/objective
            context: Additional context for the agent
            toolsets: List of allowed toolsets
            config: SubAgentConfig for customization
            role: Role specialization
            progress_callback: Callback for progress updates
            
        Returns:
            The spawned SubAgent instance
            
        Raises:
            RuntimeError: If max agents reached or spawning fails
        """
        if not self.can_spawn():
            raise RuntimeError(
                f"Cannot spawn agent: pool full ({self.active_count}/{self.max_agents})"
            )
        
        if config is None:
            config = SubAgentConfig(
                timeout=self.default_timeout,
                toolsets=toolsets or [],
                role=role,
            )
        
        # Create sub-agent
        subagent = SubAgent(
            task_id=task_id,
            role=role or config.role,
            config=config,
            parent_agent=self.parent_agent,
            _progress_callback=progress_callback,
        )
        
        # Build the child agent using delegate_task infrastructure
        try:
            child = self._build_child_agent(
                goal=goal,
                context=context,
                toolsets=toolsets or config.toolsets,
                max_iterations=50,  # Could be made configurable
                parent_agent=self.parent_agent,
            )
            subagent.agent = child
        except Exception as e:
            logger.error(f"Failed to build child agent for task {task_id}: {e}")
            subagent.status = SubAgentStatus.FAILED
            subagent.error = str(e)
            raise
        
        # Register agent
        with self._agents_lock:
            self._agents[subagent.agent_id] = subagent
            self._task_to_agent[task_id] = subagent.agent_id
        
        # Start agent thread
        subagent.status = SubAgentStatus.RUNNING
        subagent.started_at = datetime.now()
        subagent._thread = threading.Thread(
            target=self._run_agent,
            args=(subagent,),
            daemon=True,
        )
        subagent._thread.start()
        
        logger.info(f"Spawned agent {subagent.agent_id} for task {task_id}")
        return subagent
    
    def _build_child_agent(self, goal, context, toolsets, max_iterations, parent_agent):
        """
        Build a child AIAgent using the delegate_task infrastructure.
        
        This reuses the proven _build_child_agent from delegate_tool.py
        to ensure consistent sub-agent behavior.
        """
        # Import delegate_tool components
        from tools.delegate_tool import _build_child_agent, _get_max_concurrent_children
        
        # Get the parent agent's effective configuration
        parent = parent_agent
        if parent is None:
            parent = self.parent_agent
        
        # Build child using delegate_task infrastructure
        child = _build_child_agent(
            task_index=0,
            goal=goal,
            context=context,
            toolsets=toolsets,
            model=None,  # Inherit from parent
            max_iterations=max_iterations,
            task_count=1,
            parent_agent=parent,
        )
        
        return child
    
    def _run_agent(self, subagent: SubAgent) -> None:
        """Run a sub-agent in a thread."""
        task_id = subagent.task_id
        cancel_event = subagent._cancel_event
        
        try:
            logger.info(f"Agent {subagent.agent_id} starting task {task_id}")
            
            # Run the conversation
            result = subagent.agent.run_conversation(user_message=subagent.agent._ephemeral_system_prompt or subagent.task_id)
            
            # Check if cancelled
            if cancel_event.is_set():
                subagent.status = SubAgentStatus.CANCELLED
                subagent.result = {"status": "cancelled", "task_id": task_id}
                return
            
            # Store result
            subagent.result = {
                "task_id": task_id,
                "status": "completed",
                "final_response": result.get("final_response", ""),
                "messages": result.get("messages", []),
            }
            subagent.status = SubAgentStatus.COMPLETED
            logger.info(f"Agent {subagent.agent_id} completed task {task_id}")
            
        except Exception as e:
            logger.exception(f"Agent {subagent.agent_id} failed task {task_id}")
            subagent.status = SubAgentStatus.FAILED
            subagent.error = str(e)
            subagent.result = {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }
        
        finally:
            subagent.completed_at = datetime.now()
            
            # Cleanup agent resources
            if subagent.agent and hasattr(subagent.agent, 'close'):
                try:
                    subagent.agent.close()
                except Exception as e:
                    logger.debug(f"Agent cleanup error: {e}")
            
            # Notify completion
            self._all_complete_event.set()
    
    def get_agent(self, agent_id: str) -> Optional[SubAgent]:
        """Get a sub-agent by ID."""
        with self._agents_lock:
            return self._agents.get(agent_id)
    
    def get_agent_by_task(self, task_id: str) -> Optional[SubAgent]:
        """Get a sub-agent handling a specific task."""
        with self._agents_lock:
            agent_id = self._task_to_agent.get(task_id)
            if agent_id:
                return self._agents.get(agent_id)
        return None
    
    def cancel_agent(self, agent_id: str) -> bool:
        """Cancel a specific agent."""
        with self._agents_lock:
            agent = self._agents.get(agent_id)
            if agent:
                agent.cancel()
                return True
        return False
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel an agent by task ID."""
        with self._agents_lock:
            agent_id = self._task_to_agent.get(task_id)
            if agent_id:
                agent = self._agents.get(agent_id)
                if agent:
                    agent.cancel()
                    return True
        return False
    
    async def pause_all(self) -> None:
        """Pause all running agents."""
        with self._agents_lock:
            for agent in self._agents.values():
                if agent.status == SubAgentStatus.RUNNING:
                    # Note: True pause requires agent support
                    agent.status = SubAgentStatus.PAUSED
        logger.info("All agents paused")
    
    async def resume_all(self) -> None:
        """Resume all paused agents."""
        with self._agents_lock:
            for agent in self._agents.values():
                if agent.status == SubAgentStatus.PAUSED:
                    agent.status = SubAgentStatus.RUNNING
        logger.info("All agents resumed")
    
    async def cancel_all(self) -> None:
        """Cancel all agents."""
        with self._agents_lock:
            for agent in self._agents.values():
                if agent.status in (SubAgentStatus.RUNNING, SubAgentStatus.PAUSED):
                    agent.cancel()
                    agent.status = SubAgentStatus.CANCELLED
        logger.info("All agents cancelled")
    
    async def wait_for_completion(self, timeout: Optional[float] = None) -> Dict[str, SubAgent]:
        """
        Wait for all agents to complete.
        
        Args:
            timeout: Maximum seconds to wait (None = wait forever)
            
        Returns:
            Dict of agent_id -> SubAgent with final states
        """
        start = time.time()
        while True:
            with self._agents_lock:
                active = [
                    a for a in self._agents.values()
                    if a.status in (SubAgentStatus.RUNNING, SubAgentStatus.INITIALIZING)
                ]
            
            if not active:
                return dict(self._agents)
            
            if timeout and (time.time() - start) >= timeout:
                logger.warning("Wait for completion timed out")
                return dict(self._agents)
            
            # Wait a bit before checking again
            time.sleep(0.5)
    
    async def shutdown(self) -> None:
        """Shutdown the agent pool."""
        logger.info("Shutting down AgentPool")
        
        # Cancel all agents
        await self.cancel_all()
        
        # Wait for agents to finish
        await self.wait_for_completion(timeout=10)
        
        with self._agents_lock:
            self._agents.clear()
            self._task_to_agent.clear()
        
        logger.info("AgentPool shutdown complete")
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status."""
        with self._agents_lock:
            status_counts = {}
            for s in SubAgentStatus:
                status_counts[s.value] = sum(
                    1 for a in self._agents.values() if a.status == s
                )
            
            return {
                "max_agents": self.max_agents,
                "active_count": self.active_count,
                "total_count": self.total_count,
                "available_slots": self.get_available_slots(),
                "status_counts": status_counts,
                "agents": [
                    {
                        "agent_id": a.agent_id,
                        "task_id": a.task_id,
                        "status": a.status.value,
                    }
                    for a in self._agents.values()
                ],
            }
