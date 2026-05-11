"""Skills Hub guard — runtime escalation/downgrade + tool blocking.

Evaluated during tool-call dispatch in `_execute_tool_calls_sequential`.
Reads Brain's route classification and applies runtime adjustments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, List

from .config import SkillsHubConfig

logger = logging.getLogger(__name__)


@dataclass
class EscalationDecision:
    """Result of a guard check."""
    action: str           # "allow" | "escalate" | "downgrade" | "block"
    target_route: str     # the route after adjustment
    reason: str           # human-readable explanation
    blocked_tool: str = "" # which tool triggered the block


class SkillsHubGuard:
    """Runtime tool guard for skill execution.

    Two-phase evaluation per tool call:
    1. **Route adjustment**: check escalation/downgrade conditions against runtime state.
    2. **Tool check**: if route is simple, check tool against blocklist.

    Conditions are evaluated as simple boolean checks against a RuntimeState
    object that's updated per-turn and per-tool-call.

    Usage:
        guard = SkillsHubGuard(config)
        result = guard.check(brain_route="simple", tool_name="delegate_task",
                             runtime_state={"tool_chain_steps": 2, "requires_planning": False})
    """

    def __init__(self, config: SkillsHubConfig):
        self.config = config
        self._escalation_evaluators = _compile_conditions(config.escalation)
        self._downgrade_evaluators = _compile_conditions(config.downgrade)

    def adjust_route(self, brain_route: str, runtime_state: dict) -> str:
        """Adjust route based on escalation/downgrade conditions.

        Returns the (possibly adjusted) route string.
        """
        if not self.config.enabled:
            return brain_route

        # Downgrade: complex → simple (conservative — all conditions must match)
        if brain_route == "complex" and self._downgrade_evaluators:
            if _eval_all(self._downgrade_evaluators, runtime_state):
                logger.info(
                    "skills_hub: downgraded complex→simple (all conditions met: %s)",
                    self.config.downgrade,
                )
                return "simple"

        # Escalation: simple → complex (aggressive — any condition triggers)
        if brain_route == "simple" and self._escalation_evaluators:
            if _eval_any(self._escalation_evaluators, runtime_state):
                logger.info(
                    "skills_hub: escalated simple→complex (condition triggered: %s, state=%s)",
                    self.config.escalation,
                    runtime_state,
                )
                return "complex"

        return brain_route

    def check_tool(self, route: str, tool_name: str) -> EscalationDecision:
        """Check if a tool is allowed on the current route.

        Returns EscalationDecision with action and reason.
        """
        if not self.config.enabled:
            return EscalationDecision(action="allow", target_route=route,
                                      reason="skills_hub disabled")

        blocked = self.config.blocked_for(route)
        if tool_name in blocked:
            block_action = self.config.on_block
            if block_action == "escalate":
                escalate_to = self.config.escalate_to
                logger.info(
                    "skills_hub: blocked %s on route=%s, escalating to %s",
                    tool_name, route, escalate_to,
                )
                return EscalationDecision(
                    action="escalate",
                    target_route=escalate_to,
                    reason=f"{tool_name} is blocked on {route} route, escalating to {escalate_to}",
                    blocked_tool=tool_name,
                )
            elif block_action == "skip":
                logger.info(
                    "skills_hub: skipping %s on route=%s (blocked)",
                    tool_name, route,
                )
                return EscalationDecision(
                    action="block",
                    target_route=route,
                    reason=f"{tool_name} is blocked on {route} route, skipping",
                    blocked_tool=tool_name,
                )
            else:  # "warn" or unknown
                logger.warning(
                    "skills_hub: %s is blocked on route=%s but action=%s, allowing",
                    tool_name, route, block_action,
                )

        return EscalationDecision(action="allow", target_route=route,
                                  reason="tool allowed")


# ── Condition evaluators ──

def _compile_conditions(conditions: List[str]) -> List:
    """Compile condition strings into callable evaluators.

    Each condition is a simple expression like:
    - "tool_chain_steps >= 5"
    - "requires_planning"         (truthy check)
    - "not requires_planning"     (falsy check)
    - "decision_complexity >= high"
    """
    evaluators = []
    for cond in conditions:
        evaluators.append(_parse_condition(cond.strip()))
    return evaluators


def _parse_condition(cond: str):
    """Parse a single condition string into a callable.

    Supported forms:
    - "key"          → lambda state: bool(state.get("key"))
    - "not key"      → lambda state: not bool(state.get("key"))
    - "key op val"   → lambda state: _compare(state.get("key"), op, val)
    """
    parts = cond.split(maxsplit=2)

    # "not key"
    if len(parts) == 2 and parts[0] == "not":
        key = parts[1]
        return lambda state, k=key: not bool(state.get(k))

    # "key" (bare boolean)
    if len(parts) == 1:
        key = parts[0]
        return lambda state, k=key: bool(state.get(k))

    # "key op val"
    if len(parts) == 3:
        key, op, val = parts
        return lambda state, k=key, o=op, v=val: _compare(state.get(k), o, v)

    # Fallback: truthy check
    return lambda state, c=cond: bool(state.get(c))


def _compare(value, op: str, target: str) -> bool:
    """Compare a runtime value with a target using the given operator.

    Handles both numeric (>=, <=, ==, !=, >, <) and string (==, !=) comparisons.
    Handles None gracefully (always returns False).
    """
    if value is None:
        return False

    # Try numeric comparison
    try:
        num_val = int(value) if not isinstance(value, (int, float)) else value
        num_target = int(target)

        if op == ">=":
            return num_val >= num_target
        elif op == "<=":
            return num_val <= num_target
        elif op == ">":
            return num_val > num_target
        elif op == "<":
            return num_val < num_target
        elif op == "==":
            return num_val == num_target
        elif op == "!=":
            return num_val != num_target
    except (ValueError, TypeError):
        pass

    # String comparison
    str_val = str(value)
    if op == "==":
        return str_val == target
    elif op == "!=":
        return str_val != target
    elif op == ">=":
        return str_val >= target
    elif op == "<=":
        return str_val <= target

    return False


def _eval_all(evaluators: List, state: dict) -> bool:
    """All evaluators must return True (AND logic — used for downgrade)."""
    return all(eval_fn(state) for eval_fn in evaluators)


def _eval_any(evaluators: List, state: dict) -> bool:
    """Any evaluator returning True is sufficient (OR logic — used for escalation)."""
    return any(eval_fn(state) for eval_fn in evaluators)
