"""Brain — Multi-layer intelligent model routing for Hermes Agent.

Layers:
  Layer 0:   Preprocessing (multimodal detection, token estimation)
  Layer 0.5: Fingerprint Cache (SHA256 exact match)
  Layer 1:   Heuristic Classifier (regex rules)
  Affinity:  Session Affinity (lock model for ongoing tasks)
  Layer 2:   Lightweight Planner (cheap LLM classifier)
  Execution: Model resolution + fallback chain + circuit breaker

Integration:
  from agent.brain.pipeline import route_message

  decision = route_message(user_input, session, config)
  # decision.resolved_model, .resolved_provider, .resolved_base_url are set
"""

from agent.brain.types import (
    RouteDecision,
    SessionAffinityState,
    LayerTrace,
    EMPTY_DECISION,
    LOCKABLE_ROUTES,
)
from agent.brain.config import BrainConfig
from agent.brain.pipeline import route_message
from agent.brain.affinity import (
    establish_affinity,
    record_affinity_failure,
    record_affinity_success,
)
from agent.brain.circuit_breaker import CircuitBreaker
from agent.brain.logging import BrainTraceLogger
