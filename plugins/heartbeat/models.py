"""Data models for the Hermes Heartbeat plugin."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SourceObservation:
    source: str
    collected_at: str
    summary: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeartbeatContextPack:
    heartbeat_id: str
    generated_at: str
    timezone: str
    instructions: str
    observations: List[SourceObservation]
    recent_notifications: List[Dict[str, Any]]
    policy_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["observations"] = [item.to_dict() for item in self.observations]
        return data


@dataclass(frozen=True)
class FindingProposal:
    fingerprint: str
    priority: str
    summary: str
    recommended_action: str
    ttl_hours: int


@dataclass(frozen=True)
class ReviewDecision:
    action: str
    reason: str
    findings: List[FindingProposal]
