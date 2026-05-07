"""
Eclose - Self-Evolving AI Agent System

A self-evolving AI agent that perceives environment, identifies gaps,
generates evolution proposals, and improves itself over time.
"""

# Events
from eclose.events import (
    EventType,
    PerceptionEvent,
    GapEvent,
    ProposalEvent,
    ExecutionEvent,
    PerceptionSource,
    GapType,
    Severity,
    EventBus,
    get_event_bus,
)

# Perception Agents
from eclose.perception import (
    BasePerceptionAgent,
    ProjectPerceptionAgent,
    WorldPerceptionAgent,
    SelfPerceptionAgent,
    TaskPerceptionAgent,
)

# Evolution System
from eclose.evolution import (
    GapAnalysisEngine,
    ProposalGenerator,
    EvolutionProposal,
    ApprovalWorkflow,
    ApprovalDecision,
    ExecutionEngine,
    ExecutionResult,
    VerificationLayer,
    VerificationResult,
)

# Constitution
from eclose.constitution import ConstitutionalConstraints

__all__ = [
    # Events
    "EventType",
    "PerceptionEvent",
    "GapEvent",
    "ProposalEvent",
    "ExecutionEvent",
    "PerceptionSource",
    "GapType",
    "Severity",
    "EventBus",
    "get_event_bus",
    # Perception
    "BasePerceptionAgent",
    "ProjectPerceptionAgent",
    "WorldPerceptionAgent",
    "SelfPerceptionAgent",
    "TaskPerceptionAgent",
    # Evolution
    "GapAnalysisEngine",
    "ProposalGenerator",
    "EvolutionProposal",
    "ApprovalWorkflow",
    "ApprovalDecision",
    "ExecutionEngine",
    "ExecutionResult",
    "VerificationLayer",
    "VerificationResult",
    # Constitution
    "ConstitutionalConstraints",
]

__version__ = "0.1.0"
