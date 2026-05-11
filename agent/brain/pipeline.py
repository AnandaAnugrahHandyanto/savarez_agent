"""Brain Pipeline — orchestrates all routing layers.

The `route_message()` function is the single public entry point.
It chains Layer 0 → 0.5 → 1 → Affinity check → 2 → Affinity establish
→ Execution, with fail-safe wrappers around every layer.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from agent.brain.types import (
    RouteDecision, LayerTrace, SessionAffinityState, EMPTY_DECISION,
)
from agent.brain.config import BrainConfig
from agent.brain.layer0 import layer0_preprocess, token_estimate
from agent.brain.layer0_5 import FingerprintCache
from agent.brain.layer1 import layer1_heuristic
from agent.brain.layer2 import layer2_planner
from agent.brain.affinity import (
    check_affinity, establish_affinity,
    record_affinity_failure, record_affinity_success,
)
from agent.brain.circuit_breaker import CircuitBreaker
from agent.brain.execution import resolve_model
from agent.brain.logging import BrainTraceLogger

logger = logging.getLogger(__name__)

# Global fingerprint cache shared across sessions
_fingerprint_cache = FingerprintCache(max_entries=1000, ttl=3600)

# Global trace logger
_trace_logger = BrainTraceLogger()

# Routes that can skip Layer 2 when Layer 1 is high-confidence
L1_SKIP_THRESHOLDS = {
    "simple": 0.95,
    "coding": 0.90,
    # complex NEVER skipped — L1 cannot assess reasoning depth
}


def _count_turns(history: List[Dict[str, Any]]) -> int:
    """Count user turns in conversation history."""
    return sum(1 for m in history if m.get("role") == "user")


def _est_tokens_from_meta(l0_result: Optional[RouteDecision]) -> int:
    """Extract estimated token count from Layer 0 metadata."""
    if l0_result and l0_result.metadata:
        return l0_result.metadata.get("estimated_tokens", 0)
    return 0


def route_message(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
    affinity_state: Optional[SessionAffinityState] = None,
) -> RouteDecision:
    """
    Multi-layer intelligent routing pipeline.

    Every layer is wrapped in try/except — a crash in any single layer
    will never break the agent.  The pipeline degrades gracefully to
    the default model (deepseek-v4-pro / complex).

    Args:
        user_input: The user's message.
        history: Conversation history (OpenAI-format messages).
        config: Brain configuration.
        affinity_state: Current session affinity (mutated in place by caller).

    Returns:
        RouteDecision with resolved_model, resolved_provider, resolved_base_url
        filled in by the execution layer.
    """
    traces: List[LayerTrace] = []

    if not config.enabled:
        return EMPTY_DECISION

    turns = _count_turns(history)
    l0_result: Optional[RouteDecision] = None
    l1_result: Optional[RouteDecision] = None
    est_tokens = 0

    # ═══════════════════════════════════════════════════════════════════
    # Layer 0: Preprocessing
    # ═══════════════════════════════════════════════════════════════════
    try:
        l0_result = layer0_preprocess(user_input, history, config)
        if l0_result and l0_result.is_terminal:
            # Vision / doc_extract — no further classification needed
            traces.append(LayerTrace("l0", l0_result.route, l0_result.confidence, l0_result.source))
            cb = CircuitBreaker(config.circuit_breaker)
            decision = resolve_model(l0_result, config, cb)
            _trace_logger.log_trace("", traces)
            return decision
        if l0_result:
            traces.append(LayerTrace("l0", l0_result.route, l0_result.confidence, l0_result.source))
            est_tokens = l0_result.metadata.get("estimated_tokens", 0)
    except Exception as e:
        logger.warning("Layer 0 failed: %s", e)
        traces.append(LayerTrace("l0", meta={"error": str(e)[:100]}))

    # ═══════════════════════════════════════════════════════════════════
    # Layer 0.5: Fingerprint Cache
    # ═══════════════════════════════════════════════════════════════════
    try:
        if config.layer0_5.enabled:
            cached = _fingerprint_cache.get(user_input)
            if cached:
                traces.append(LayerTrace(
                    "l05", cached.route, cached.confidence, cached.source,
                ))
                cb = CircuitBreaker(config.circuit_breaker)
                decision = resolve_model(cached, config, cb,
                                        estimated_tokens=est_tokens,
                                        session_turns=turns)
                _trace_logger.log_trace("", traces)
                return decision
            traces.append(LayerTrace("l05", meta={"hit": False}))
    except Exception as e:
        logger.warning("Layer 0.5 failed: %s", e)

    # ═══════════════════════════════════════════════════════════════════
    # Layer 1: Heuristic
    # ═══════════════════════════════════════════════════════════════════
    try:
        l1_result = layer1_heuristic(user_input, history, turns, est_tokens)
        if l1_result:
            traces.append(LayerTrace(
                "l1", l1_result.route, l1_result.confidence, l1_result.source,
            ))
            # High-confidence simple/coding → skip Layer 2
            threshold = L1_SKIP_THRESHOLDS.get(l1_result.route, 1.0)
            if l1_result.confidence >= threshold:
                cb = CircuitBreaker(config.circuit_breaker)
                decision = resolve_model(l1_result, config, cb,
                                        estimated_tokens=est_tokens,
                                        session_turns=turns)
                _fingerprint_cache.set(user_input, decision)
                _trace_logger.log_trace("", traces)
                return decision
        else:
            traces.append(LayerTrace("l1"))
    except Exception as e:
        logger.warning("Layer 1 failed: %s", e)

    # ═══════════════════════════════════════════════════════════════════
    # Session Affinity Check (between L1 and L2)
    # ═══════════════════════════════════════════════════════════════════
    try:
        aff_decision = check_affinity(affinity_state, l1_result, config.affinity)
        if aff_decision:
            # Verify circuit breaker for affinity model
            cb = CircuitBreaker(config.circuit_breaker)
            if not cb.is_open(
                aff_decision.resolved_provider or "",
                aff_decision.resolved_model or "",
            ):
                traces.append(LayerTrace(
                    "affinity", aff_decision.route,
                    aff_decision.confidence, "affinity_reuse",
                ))
                _trace_logger.log_trace("", traces)
                return aff_decision
            else:
                # Affinity model is broken — release
                logger.debug(
                    "Affinity model %s is circuit-broken, releasing",
                    aff_decision.resolved_model,
                )
                if affinity_state:
                    affinity_state.route = None  # Clear in-place
    except Exception as e:
        logger.warning("Affinity check failed: %s", e)

    # ═══════════════════════════════════════════════════════════════════
    # Layer 2: Lightweight Planner
    # ═══════════════════════════════════════════════════════════════════
    l2_result: RouteDecision
    try:
        l2_result = layer2_planner(user_input, history, config, l1_result)
        traces.append(LayerTrace(
            "l2", l2_result.route, l2_result.confidence, l2_result.source,
        ))
    except Exception as e:
        logger.warning("Layer 2 failed: %s", e)
        l2_result = RouteDecision("complex", 0.1, "l2_crash",
                                  metadata={"error": str(e)[:200]})

    # ═══════════════════════════════════════════════════════════════════
    # Session Affinity Establish (after L2)
    # ═══════════════════════════════════════════════════════════════════
    # Note: affinity_state is mutated in-place by the caller (AIAgent)
    # We return the decision; the caller handles affinity establishment.

    # ═══════════════════════════════════════════════════════════════════
    # Execution Layer
    # ═══════════════════════════════════════════════════════════════════
    try:
        cb = CircuitBreaker(config.circuit_breaker)
        decision = resolve_model(l2_result, config, cb,
                                estimated_tokens=est_tokens,
                                session_turns=turns)
    except Exception as e:
        logger.error("Execution layer failed: %s", e)
        decision = RouteDecision(
            "complex", 0.1, "exec_crash",
            resolved_model="deepseek-v4-pro",
            metadata={"error": str(e)[:200]},
        )

    # Cache and trace
    try:
        _fingerprint_cache.set(user_input, decision)
    except Exception:
        pass

    try:
        _trace_logger.log_trace("", traces)
    except Exception:
        pass

    return decision


# ── Vision Post-Hook Reroute ────────────────────────────────────────────
# After L0 detects an image and routes to the vision model, the vision
# model extracts a text description.  Then we re-route the text-only
# conversation back through the Brain pipeline so the main model handles
# the actual response with full visual context.
# ──────────────────────────────────────────────────────────────────────────


def is_vision_reroute_needed(decision: RouteDecision) -> bool:
    """Check if a route decision needs vision reroute (image→description→main model)."""
    if not decision or not decision.metadata:
        return False
    return (
        decision.route == "vision"
        and decision.metadata.get("reroute_after_extract") is True
    )


def post_vision_reroute(
    vision_description: str,
    original_user_input: str,
    history: list,
    config: BrainConfig,
    affinity_state: object = None,
) -> RouteDecision:
    """
    After vision model extracts an image description, re-route the
    text-only conversation back through the Brain pipeline.

    The vision description is injected as a synthetic user message so the
    main model "knows" what was in the image.  The original user message
    has image refs stripped so L0 does NOT re-detect multimodal content.

    Returns a fully resolved RouteDecision with resolved_model set.
    """
    from agent.brain.affinity import check_affinity as _aff_check
    from agent.brain.layer0 import layer0_preprocess
    from agent.brain.layer1 import layer1_heuristic
    from agent.brain.layer2 import layer2_planner
    from agent.brain.execution import resolve_model
    from agent.brain.circuit_breaker import CircuitBreaker

    # ── Build a text-only user message ──
    text_input = _strip_image_refs(original_user_input)

    # Build modified history with vision context as a synthetic user message
    modified_history = list(history) if history else []
    if vision_description.strip():
        modified_history.append({
            "role": "user",
            "content": (
                "[视觉上下文] 用户上传了一张图片，内容如下：\n"
                f"{vision_description.strip()}"
            ),
        })

    # ── Re-run the routing pipeline (text-only now) ──
    traces = []
    turns = sum(1 for m in modified_history if m.get("role") == "user")
    est_tokens = 0

    # L0: preprocessing (will NOT detect multimodal — image refs are stripped)
    try:
        l0 = layer0_preprocess(text_input, modified_history, config)
        if l0:
            traces.append(("l0", l0.route, l0.confidence, l0.source))
            est_tokens = l0.metadata.get("estimated_tokens", 0)
    except Exception:
        traces.append(("l0_error",))

    # L0.5: fingerprint cache
    try:
        if config.layer0_5.enabled:
            cached = _fingerprint_cache.get(text_input)
            if cached:
                traces.append(("l05", cached.route, cached.confidence, cached.source))
                cb = CircuitBreaker(config.circuit_breaker)
                decision = resolve_model(
                    cached, config, cb,
                    estimated_tokens=est_tokens, session_turns=turns,
                )
                decision.metadata["vision_rerouted"] = True
                return decision
    except Exception:
        pass

    # L1: heuristic
    l1 = None
    try:
        l1 = layer1_heuristic(text_input, modified_history, turns, est_tokens)
        if l1:
            traces.append(("l1", l1.route, l1.confidence, l1.source))
            threshold = {"simple": 0.95, "coding": 0.90}.get(l1.route, 1.0)
            if l1.confidence >= threshold:
                cb = CircuitBreaker(config.circuit_breaker)
                decision = resolve_model(
                    l1, config, cb,
                    estimated_tokens=est_tokens, session_turns=turns,
                )
                decision.metadata["vision_rerouted"] = True
                return decision
    except Exception:
        traces.append(("l1_error",))

    # Session Affinity check
    try:
        aff_decision = _aff_check(affinity_state, l1, config.affinity)
        if aff_decision:
            cb = CircuitBreaker(config.circuit_breaker)
            if not cb.is_open(
                aff_decision.resolved_provider or "",
                aff_decision.resolved_model or "",
            ):
                traces.append(("affinity", aff_decision.route,
                               aff_decision.confidence, "affinity_reuse"))
                aff_decision.metadata["vision_rerouted"] = True
                return aff_decision
    except Exception:
        pass

    # L2: planner
    try:
        l2 = layer2_planner(text_input, modified_history, config, l1)
        traces.append(("l2", l2.route, l2.confidence, l2.source))
    except Exception as e:
        l2 = RouteDecision("complex", 0.1, "l2_crash",
                           metadata={"error": str(e)[:200]})
        traces.append(("l2_error",))

    # Execution
    try:
        cb = CircuitBreaker(config.circuit_breaker)
        decision = resolve_model(l2, config, cb,
                                 estimated_tokens=est_tokens,
                                 session_turns=turns)
    except Exception as e:
        decision = RouteDecision(
            "complex", 0.1, "exec_crash",
            resolved_model="deepseek-v4-pro",
            metadata={"error": str(e)[:200], "vision_rerouted": True},
        )

    decision.metadata["vision_rerouted"] = True
    return decision


def _strip_image_refs(text: str) -> str:
    """Remove image URLs/file paths from user input for clean re-routing."""
    import re
    # Remove markdown images: ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove bare image URLs with image extensions
    text = re.sub(
        r'https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp|svg)\??[^\s]*',
        '', text, flags=re.IGNORECASE,
    )
    # Remove local file paths that look like images
    text = re.sub(
        r'\b\w:[/\\]\S+\.(?:png|jpg|jpeg|gif|webp|bmp|svg)\b',
        '', text, flags=re.IGNORECASE,
    )
    # Remove file:// scheme
    text = re.sub(r'file://\S+', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text
