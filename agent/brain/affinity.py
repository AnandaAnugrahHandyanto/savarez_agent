"""Session Affinity — lock model for ongoing task types.

Establish on first high-confidence non-simple route after Layer 2.
Release on: L1 conflict (high-confidence different route), idle timeout,
or 2+ consecutive failures on the locked model.
"""

import logging
import time
from typing import Optional

from agent.brain.types import RouteDecision, SessionAffinityState
from agent.brain.config import AffinityConfig

logger = logging.getLogger(__name__)


def check_affinity(
    affinity_state: Optional[SessionAffinityState],
    l1_decision: Optional[RouteDecision],
    config: AffinityConfig,
) -> Optional[RouteDecision]:
    """
    Check if session affinity should override routing.

    Called between Layer 1 and Layer 2.

    Returns:
        RouteDecision with resolution info (skip Layer 2), or
        None to continue to Layer 2, or
        None when affinity should be released (caller clears state).
    """
    if not config.enabled:
        return None
    if affinity_state is None or not affinity_state.route:
        return None

    # Check: idle timeout release (disabled in sticky mode)
    if config.mode != "sticky":
        idle = time.time() - affinity_state.locked_at
        if config.idle_timeout > 0 and idle > config.idle_timeout:
            logger.debug(
                "Affinity released: idle timeout (%.0fs > %ds)",
                idle, config.idle_timeout,
            )
            return None  # Signal to caller: clear affinity

    # Check: L1 conflict with high confidence (disabled in sticky mode)
    if config.mode != "sticky" and l1_decision and l1_decision.confidence >= 0.95:
        if l1_decision.route != affinity_state.route:
            logger.debug(
                "Affinity released: L1 conflict (%s ≠ %s, conf=%.2f)",
                l1_decision.route, affinity_state.route, l1_decision.confidence,
            )
            return None  # Signal to caller: clear affinity and reroute

    # Apply: reuse affinity model for same route type
    return RouteDecision(
        route=affinity_state.route,
        confidence=affinity_state.confidence,
        source="affinity_reuse",
        resolved_model=affinity_state.model,
        resolved_provider=affinity_state.provider,
        resolved_base_url=affinity_state.base_url,
        resolved_api_key=affinity_state.api_key,
    )


def establish_affinity(
    state: Optional[SessionAffinityState],
    decision: RouteDecision,
    config: AffinityConfig,
) -> Optional[SessionAffinityState]:
    """
    Attempt to establish session affinity after Layer 2 decision.

    Called after Layer 2 produces a decision.  Only locks on coding,
    complex, or vision routes with confidence ≥ min_confidence.

    Returns:
        New SessionAffinityState if locked, existing state if already
        locked to same route, or None if not lockable.
    """
    if not config.enabled:
        return None

    if decision.route not in config.lockable_routes:
        return None

    if decision.confidence < config.min_confidence:
        return None

    # Don't re-lock if already locked to same route
    if state and state.route == decision.route:
        return state

    return SessionAffinityState(
        route=decision.route,
        model=decision.resolved_model or "",
        provider=decision.resolved_provider or "",
        base_url=decision.resolved_base_url or "",
        api_key=decision.resolved_api_key or "",
        confidence=decision.confidence,
        locked_at=time.time(),
    )


def record_affinity_failure(
    state: Optional[SessionAffinityState],
) -> bool:
    """
    Record a failure on the affinity-locked model.

    Returns:
        True if affinity should be released (2+ consecutive failures).
        False otherwise.
    """
    if state is None or not state.route:
        return False
    state.consecutive_failures += 1
    if state.consecutive_failures >= 2:
        logger.warning(
            "Affinity released: %d consecutive failures on %s",
            state.consecutive_failures, state.model,
        )
        return True
    return False


def record_affinity_success(state: Optional[SessionAffinityState]):
    """Reset failure counter on successful model call."""
    if state:
        state.consecutive_failures = 0
