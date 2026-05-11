"""Execution Layer — model resolution + fallback chain.

Resolves a RouteDecision to a concrete model/provider, applying:
  - Route→model mapping from config
  - Auto-upgrade guards (simple → complex on too-long context or many turns)
  - Circuit breaker awareness (skip broken targets)
  - Fallback chain selection
"""

import logging
from typing import Optional

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig, RouteTarget
from agent.brain.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


def resolve_model(
    decision: RouteDecision,
    config: BrainConfig,
    circuit_breaker: CircuitBreaker,
    estimated_tokens: int = 0,
    session_turns: int = 0,
) -> RouteDecision:
    """
    Resolve a RouteDecision to a concrete model/provider.

    Side effects: mutates decision with resolved_model, resolved_provider,
    resolved_base_url, and fallback chain in metadata.

    Returns the same decision object (mutated).
    """
    route = decision.route

    if route not in config.execution.routes:
        logger.warning("Unknown route '%s', falling back to complex", route)
        route = "complex"
        decision.route = "complex"

    target = config.execution.routes[route]

    # Auto-upgrade guards (simple → complex)
    if route == "simple" and _should_upgrade(target, estimated_tokens, session_turns):
        logger.debug(
            "Auto-upgrade: simple → complex (tokens=%d, turns=%d)",
            estimated_tokens, session_turns,
        )
        target = config.execution.routes.get("complex", target)
        decision.route = "complex"
        decision.metadata["auto_upgraded"] = True
        decision.metadata["upgrade_reason"] = _upgrade_reason(
            target, estimated_tokens, session_turns
        )

    # Select model from fallback chain, respecting circuit breaker
    chain = config.fallback.chains.get(
        decision.route,
        [target.model],
    )
    selected = _select_from_chain(chain, circuit_breaker, target.provider)

    decision.resolved_model = selected
    decision.resolved_provider = target.provider or ""
    decision.resolved_base_url = target.base_url or ""
    decision.metadata["fallback_chain"] = chain
    decision.metadata["timeout"] = get_route_timeout(decision.route, config)

    return decision


def _should_upgrade(
    target: RouteTarget,
    estimated_tokens: int,
    session_turns: int,
) -> bool:
    """Check if simple route should auto-upgrade to complex."""
    if target.auto_upgrade_max_tokens > 0 and estimated_tokens > target.auto_upgrade_max_tokens:
        return True
    if target.auto_upgrade_max_turns > 0 and session_turns > target.auto_upgrade_max_turns:
        return True
    return False


def _upgrade_reason(
    target: RouteTarget,
    estimated_tokens: int,
    session_turns: int,
) -> str:
    reasons = []
    if target.auto_upgrade_max_tokens > 0 and estimated_tokens > target.auto_upgrade_max_tokens:
        reasons.append(
            f"estimated_tokens ({estimated_tokens}) > max ({target.auto_upgrade_max_tokens})"
        )
    if target.auto_upgrade_max_turns > 0 and session_turns > target.auto_upgrade_max_turns:
        reasons.append(
            f"session_turns ({session_turns}) > max ({target.auto_upgrade_max_turns})"
        )
    return "; ".join(reasons)


def _select_from_chain(
    chain: list,
    cb: CircuitBreaker,
    provider: str = "",
) -> str:
    """Select first available model from fallback chain."""
    for model in chain:
        if not cb.is_open(provider, model):
            return model
    # All open — return last as ultimate fallback
    logger.warning("All models in fallback chain are circuit-broken: %s", chain)
    return chain[-1]


def resolve_fallback_chain(route: str, config: BrainConfig) -> list:
    """Return ordered fallback chain for a route."""
    return config.fallback.chains.get(route, ["deepseek-v4-pro"])


def get_route_timeout(route: str, config: BrainConfig) -> int:
    """Return API timeout in seconds for a given route."""
    return config.fallback.timeout.get(route, 30)
