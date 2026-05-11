"""Shared data types for the Brain routing system."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RouteDecision:
    """Output from any routing layer. Execution layer fills resolved_model/provider."""
    route: str                          # "simple" | "coding" | "complex" | "vision" | "doc_extract"
    confidence: float                   # 0.0 – 1.0
    source: str                         # "l0_image" | "l05_fingerprint" | "l1_greeting" | "l2_planner" | ...
    resolved_model: Optional[str] = None
    resolved_provider: Optional[str] = None
    resolved_base_url: Optional[str] = None
    resolved_api_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.90

    @property
    def is_terminal(self) -> bool:
        """Routes that should NOT be re-evaluated by later layers."""
        return self.route in ("vision", "doc_extract")


@dataclass
class LayerTrace:
    """One entry in the full routing trace for observability."""
    layer: str                          # "l0" | "l05" | "l1" | "affinity" | "l2" | "exec"
    decision: Optional[str] = None      # route or None if pass-through
    confidence: Optional[float] = None
    source: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionAffinityState:
    """Persistent session affinity — locked model for current session."""
    route: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    confidence: float = 0.0
    consecutive_failures: int = 0
    locked_at: float = 0.0


EMPTY_DECISION = RouteDecision("complex", 0.1, "none")
LOCKABLE_ROUTES = frozenset({"coding", "complex", "vision"})
