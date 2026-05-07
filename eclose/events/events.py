from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class EventType(Enum):
    PERCEPTION = "perception"
    GAP = "gap"
    PROPOSAL = "proposal"
    EXECUTION = "execution"


class PerceptionSource(Enum):
    PROJECT = "project"
    WORLD = "world"
    SELF = "self"
    TASK = "task"


class GapType(Enum):
    SKILL = "skill"
    TOOL = "tool"
    KNOWLEDGE = "knowledge"
    CAPABILITY = "capability"


class Severity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class PerceptionEvent:
    type: EventType = EventType.PERCEPTION
    source: PerceptionSource = None
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class GapEvent:
    type: EventType = EventType.GAP
    gap_type: GapType = None
    severity: Severity = Severity.MINOR
    description: str = ""
    evidence: list[dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProposalEvent:
    type: EventType = EventType.PROPOSAL
    proposal_id: str = ""
    gap: GapEvent = None
    solution: dict = field(default_factory=dict)
    estimated_impact: dict = field(default_factory=dict)
    risks: list[dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    requires_approval: bool = True


@dataclass
class ExecutionEvent:
    type: EventType = EventType.EXECUTION
    proposal_id: str = ""
    status: str = "pending"  # success, partial, failed
    results: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
