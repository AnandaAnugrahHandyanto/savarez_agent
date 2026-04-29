#!/usr/bin/env python3
"""
Multi-Agent Collaboration Module

Provides a framework for coordinating multiple AIAgent instances to work
collaboratively on complex tasks. Inspired by:
- JackChen-me/open-multi-agent: TypeScript multi-model team coordination
- HKUDS/OpenHarness: SubAgent generation, Team Registry, task lifecycle management
- agency-agents: Specialized agent role division

Key Components:
- Team: A managed group of agents working on shared objectives
- TaskDecomposer: Breaks complex tasks into parallelizable subtasks (DAG)
- AgentPool: Manages sub-agent lifecycle and resource limits
- MessageBus: Inter-agent communication (sync/async, with attachments)
- ResultAggregator: Collects and merges sub-agent results
- Registry: Tracks all active teams with snapshot/restore capability
"""

from .team import Team, TeamStatus
from .task_decomposer import TaskDecomposer, Task, TaskDependency, DependencyType
from .agent_pool import AgentPool, SubAgent, SubAgentStatus
from .message_bus import MessageBus, Message, MessageType, Attachment
from .result_aggregator import ResultAggregator, AggregationStrategy, AggregationResult
from .registry import TeamRegistry, TeamSnapshot

__all__ = [
    # Team
    "Team",
    "TeamStatus",
    # Task Decomposer
    "TaskDecomposer",
    "Task",
    "TaskDependency",
    "DependencyType",
    # Agent Pool
    "AgentPool",
    "SubAgent",
    "SubAgentStatus",
    # Message Bus
    "MessageBus",
    "Message",
    "MessageType",
    "Attachment",
    # Result Aggregator
    "ResultAggregator",
    "AggregationStrategy",
    "AggregationResult",
    # Registry
    "TeamRegistry",
    "TeamSnapshot",
]
