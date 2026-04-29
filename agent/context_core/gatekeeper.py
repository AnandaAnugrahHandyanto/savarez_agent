"""GateKeeper — policy layer that gates when and how compression may run.

The GateKeeper enforces a set of configurable policies ("gates") that must
all pass before a compression operation is permitted to proceed.  This allows
the context engine to make safer, more informed decisions about when to
compact — for example, refusing compression if:

- The session is too short (not enough history to justify compression)
- A critical operation is in flight (e.g., delegate_task sent but not resolved)
- The previous compression was recent and ineffective
- Context is not actually over threshold (stale token count)
- Certain user preferences or session metadata disallow it

Each gate is a named callable that returns a `GateResult` (pass/fail + reason).
The GateKeeper evaluates all gates and aggregates their results.  If any gate
fails, compression is blocked with an explanatory message.

Usage::

    gk = GateKeeper()
    gk.register_gate("min_history", min_history_gate(min_messages=15))
    gk.register_gate("context_threshold", threshold_gate())

    result = gk.evaluate(messages=..., prompt_tokens=..., session_state=...)
    if not result.allowed:
        print(f"Blocked: {result.reason}")
    else:
        # proceed with compression
        compressed = engine.compress(messages)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Types
# ------------------------------------------------------------------

GateFn = Callable[["GateContext"], "GateResult"]


@dataclass
class GateResult:
    """Result of evaluating a single gate."""

    name: str
    """Identifier of the gate that produced this result."""

    allowed: bool
    """True if the gate passed, False if it blocked the operation."""

    reason: str = ""
    """Human-readable explanation (always set, even on pass)."""

    details: Dict[str, Any] = field(default_factory=dict)
    """Additional structured details about the gate evaluation."""

    @classmethod
    def pass_(cls, name: str, reason: str = "ok", **details) -> "GateResult":
        return cls(name=name, allowed=True, reason=reason, details=details)

    @classmethod
    def fail(cls, name: str, reason: str, **details) -> "GateResult":
        return cls(name=name, allowed=False, reason=reason, details=details)


@dataclass
class GateContext:
    """Context object passed to all gate functions at evaluation time."""

    messages: List[Dict[str, Any]]
    """Current full message list."""

    prompt_tokens: int = 0
    """Token count from the most recent API response prompt."""

    threshold_tokens: int = 0
    """The configured compression threshold in tokens."""

    context_length: int = 0
    """Model's context window size."""

    session_id: str = ""
    """Current session identifier."""

    compression_count: int = 0
    """Number of compressions already performed in this session."""

    last_compression_savings_pct: float = 100.0
    """Percentage of tokens saved by the most recent compression."""

    time_since_last_compression: float = 0.0
    """Seconds elapsed since the last compression finished."""

    session_start_time: float = 0.0
    """Unix timestamp when the session started."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Arbitrary key-value store for passing additional context to gates."""


@dataclass
class GateEvaluation:
    """Aggregated result of evaluating all gates."""

    allowed: bool
    """True only if ALL gates passed."""

    results: List[GateResult]
    """Individual results from each gate."""

    reason: str = ""
    """Summary of why compression was blocked (empty if allowed)."""

    blocked_by: List[str] = field(default_factory=list)
    """List of gate names that failed."""

    @property
    def all_passed(self) -> bool:
        """Alias for allowed (for readability)."""
        return self.allowed

    def summary(self) -> str:
        """Human-readable one-line summary."""
        if self.allowed:
            return f"Allowed ({len(self.results)} gates passed)"
        blocked = ", ".join(self.blocked_by)
        return f"Blocked by {len(self.blocked_by)} gate(s): {blocked}"


# ------------------------------------------------------------------
# Common gate factories
# ------------------------------------------------------------------

def min_history_gate(min_messages: int = 10, min_turns: int = 5) -> GateFn:
    """Block if the conversation has too few messages/turns to justify compression.

    Args:
        min_messages: Minimum total messages required.
        min_turns: Minimum number of user<->assistant exchanges.
    """
    def gate(ctx: GateContext) -> GateResult:
        n_msgs = len(ctx.messages)
        # Count user<->assistant pairs as turns
        user_count = sum(1 for m in ctx.messages if m.get("role") == "user")

        if n_msgs < min_messages:
            return GateResult.fail(
                "min_history",
                f"Only {n_msgs} messages (minimum {min_messages})",
                n_messages=n_msgs,
                min_messages=min_messages,
            )
        if user_count < min_turns:
            return GateResult.fail(
                "min_history",
                f"Only {user_count} user turns (minimum {min_turns})",
                user_turns=user_count,
                min_turns=min_turns,
            )
        return GateResult.pass_(
            "min_history",
            f"{n_msgs} messages, {user_count} user turns — sufficient history",
            n_messages=n_msgs,
            user_turns=user_count,
        )
    return gate


def context_threshold_gate(margin_tokens: int = 500) -> GateFn:
    """Block if prompt tokens are not sufficiently over the threshold.

    This prevents compression from firing on stale token counts or marginal
    overruns that may resolve themselves (e.g., model output reduced context
    usage on the next turn).

    Args:
        margin_tokens: How many tokens above threshold before allowing compression.
    """
    def gate(ctx: GateContext) -> GateResult:
        over = ctx.prompt_tokens - ctx.threshold_tokens
        if over < margin_tokens:
            return GateResult.fail(
                "context_threshold",
                f"Only {over} tokens over threshold (need >={margin_tokens} margin)",
                over_threshold=over,
                margin_tokens=margin_tokens,
                prompt_tokens=ctx.prompt_tokens,
                threshold_tokens=ctx.threshold_tokens,
            )
        return GateResult.pass_(
            "context_threshold",
            f"{over} tokens over threshold — threshold gate passed",
            over_threshold=over,
            prompt_tokens=ctx.prompt_tokens,
            threshold_tokens=ctx.threshold_tokens,
        )
    return gate


def anti_thrash_gate(
    max_ineffective_compressions: int = 2,
    min_savings_pct: float = 10.0,
) -> GateFn:
    """Block if recent compressions were all ineffective (thrashing protection).

    This mirrors the anti-thrashing logic from ContextCompressor.

    Args:
        max_ineffective_compressions: Number of consecutive low-savings compressions
            allowed before blocking.
        min_savings_pct: Minimum required savings percentage to be considered effective.
    """
    def gate(ctx: GateContext) -> GateResult:
        # ctx.compression_count is the count BEFORE this compression would fire
        ineffective = ctx.compression_count >= max_ineffective_compressions
        low_savings = ctx.last_compression_savings_pct < min_savings_pct

        if ineffective and low_savings:
            return GateResult.fail(
                "anti_thrash",
                f"Compression blocked — last {max_ineffective_compressions}+ "
                f"compressions saved <{min_savings_pct}% each",
                compression_count=ctx.compression_count,
                last_savings_pct=ctx.last_compression_savings_pct,
                min_savings_pct=min_savings_pct,
            )
        return GateResult.pass_(
            "anti_thrash",
            "Anti-thrash gate passed",
            compression_count=ctx.compression_count,
            last_savings_pct=ctx.last_compression_savings_pct,
        )
    return gate


def cooldown_gate(min_interval_seconds: float = 60.0) -> GateFn:
    """Block if the minimum interval between compressions has not elapsed.

    Args:
        min_interval_seconds: Minimum seconds between the last compression
            and the next one.
    """
    def gate(ctx: GateContext) -> GateResult:
        if ctx.time_since_last_compression < min_interval_seconds:
            return GateResult.fail(
                "cooldown",
                f"Cooldown active — {ctx.time_since_last_compression:.0f}s "
                f"since last compression (minimum {min_interval_seconds}s)",
                elapsed=ctx.time_since_last_compression,
                min_interval=min_interval_seconds,
            )
        return GateResult.pass_(
            "cooldown",
            f"{ctx.time_since_last_compression:.0f}s since last compression",
            elapsed=ctx.time_since_last_compression,
        )
    return gate


def session_age_gate(min_age_seconds: float = 120.0) -> GateFn:
    """Block if the session is too young (user might be about to send more context).

    Args:
        min_age_seconds: Minimum session age in seconds before compression is allowed.
    """
    def gate(ctx: GateContext) -> GateResult:
        session_age = time.time() - ctx.session_start_time
        if session_age < min_age_seconds:
            return GateResult.fail(
                "session_age",
                f"Session only {session_age:.0f}s old (minimum {min_age_seconds}s)",
                session_age_seconds=session_age,
                min_age_seconds=min_age_seconds,
            )
        return GateResult.pass_(
            "session_age",
            f"Session {session_age:.0f}s old — age gate passed",
            session_age_seconds=session_age,
        )
    return gate


def delegate_in_flight_gate() -> GateFn:
    """Block if there is a delegate_task tool call that has not yet returned.

    Compression during an in-flight delegation can cause the subagent's context
    to be corrupted or the delegation result to be lost.
    """
    def gate(ctx: GateContext) -> GateResult:
        in_flight = False
        pending_call_ids: List[str] = []

        for msg in ctx.messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        if fn.get("name") == "delegate_task":
                            tc_id = tc.get("id", "")
                            pending_call_ids.append(tc_id)
                    else:
                        fn = getattr(tc, "function", None)
                        if fn and getattr(fn, "name", "") == "delegate_task":
                            tc_id = getattr(tc, "id", "")
                            pending_call_ids.append(tc_id)

        # Check if any pending delegate results are missing
        surviving_call_ids: Set[str] = set()
        for msg in ctx.messages:
            if msg.get("role") == "tool":
                cid = msg.get("tool_call_id", "")
                if cid in pending_call_ids:
                    in_flight = False
                    break
                surviving_call_ids.add(cid)

        for cid in pending_call_ids:
            if cid not in surviving_call_ids:
                in_flight = True
                break

        if in_flight:
            return GateResult.fail(
                "delegate_in_flight",
                "Compression blocked — delegate_task is in flight",
                pending_delegate_ids=pending_call_ids,
            )
        return GateResult.pass_("delegate_in_flight", "No in-flight delegate_task")
    return gate


# ------------------------------------------------------------------
# GateKeeper
# ------------------------------------------------------------------

class GateKeeper:
    """Policy evaluation engine for context compression gates.

    The GateKeeper holds a registry of named gate functions and evaluates
    them on demand.  All gates must pass for the overall operation to be
    allowed.  Individual gates can be dynamically registered, unregistered,
    enabled, or disabled.

    Thread-safe for single-writer patterns (as used in the agent loop).
    """

    def __init__(
        self,
        gates: Optional[List[GateFn]] = None,
        default_policy: str = "allow",
        quiet: bool = False,
    ):
        """
        Args:
            gates: Initial list of gate functions to register.
            default_policy: What to do if no gates are registered.
                "allow" = permissive (default), "deny" = restrictive.
            quiet: Suppress info-level log messages.
        """
        self.default_policy = default_policy
        self.quiet = quiet

        self._gates: Dict[str, GateFn] = {}
        self._enabled: Dict[str, bool] = {}
        self._stats = {
            "evaluate_count": 0,
            "block_count": 0,
            "allow_count": 0,
            "gate_pass_counts": {},
            "gate_fail_counts": {},
        }

        if gates:
            for gate_fn in gates:
                self.register_gate(gate_fn.__name__, gate_fn)

    # ------------------------------------------------------------------
    # Gate registration
    # ------------------------------------------------------------------

    def register_gate(
        self,
        name: str,
        gate_fn: GateFn,
        enabled: bool = True,
    ) -> None:
        """Register a gate function under *name*."""
        self._gates[name] = gate_fn
        self._enabled[name] = enabled
        logger.debug("GateKeeper: registered gate '%s'", name)

    def unregister_gate(self, name: str) -> bool:
        """Remove a gate by name. Returns True if it existed."""
        if name in self._gates:
            del self._gates[name]
            del self._enabled[name]
            return True
        return False

    def enable_gate(self, name: str) -> None:
        """Enable a registered gate."""
        if name in self._enabled:
            self._enabled[name] = True

    def disable_gate(self, name: str) -> None:
        """Disable a registered gate (evaluation will pass it automatically)."""
        if name in self._enabled:
            self._enabled[name] = False

    def is_gate_enabled(self, name: str) -> bool:
        """Return True if the gate is currently enabled."""
        return self._enabled.get(name, False)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, ctx: GateContext) -> GateEvaluation:
        """Evaluate all registered (and enabled) gates against the context.

        All gates are evaluated regardless of individual results (no short-circuit).
        The GateEvaluation aggregates the overall result.

        Args:
            ctx: The context object with current conversation state.

        Returns:
            A GateEvaluation with the aggregated result and per-gate breakdowns.
        """
        self._stats["evaluate_count"] += 1

        if not self._gates:
            result = GateEvaluation(
                allowed=(self.default_policy == "allow"),
                results=[],
                reason="" if self.default_policy == "allow" else "No gates registered",
            )
            if result.allowed:
                self._stats["allow_count"] += 1
            else:
                self._stats["block_count"] += 1
            return result

        results: List[GateResult] = []
        blocked_by: List[str] = []

        for name, gate_fn in self._gates.items():
            if not self._enabled.get(name, False):
                continue

            try:
                result = gate_fn(ctx)
            except Exception as e:
                logger.warning("GateKeeper: gate '%s' raised %s — treating as fail", name, e)
                result = GateResult.fail(name, f"Gate raised exception: {e}")

            results.append(result)

            if result.allowed:
                self._stats["gate_pass_counts"][name] = \
                    self._stats["gate_pass_counts"].get(name, 0) + 1
            else:
                blocked_by.append(name)
                self._stats["gate_fail_counts"][name] = \
                    self._stats["gate_fail_counts"].get(name, 0) + 1

        allowed = len(blocked_by) == 0

        if allowed:
            self._stats["allow_count"] += 1
            reason = f"All {len(results)} gate(s) passed"
        else:
            self._stats["block_count"] += 1
            reason = f"Blocked by {len(blocked_by)} gate(s): {', '.join(blocked_by)}"

        evaluation = GateEvaluation(
            allowed=allowed,
            results=results,
            reason=reason,
            blocked_by=blocked_by,
        )

        if not self.quiet:
            if allowed:
                logger.info("GateKeeper: %s", reason)
            else:
                for r in results:
                    if not r.allowed:
                        logger.info("GateKeeper: gate '%s' blocked — %s", r.name, r.reason)

        return evaluation

    def check(self, **kwargs) -> bool:
        """Shorthand: evaluate and return just the allowed boolean.

        Builds a GateContext from kwargs (messages required; other fields optional).
        """
        ctx = GateContext(messages=kwargs.pop("messages", []), **kwargs)
        return self.evaluate(ctx).allowed

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def gate_names(self) -> List[str]:
        """List of registered gate names."""
        return list(self._gates.keys())

    @property
    def enabled_gate_names(self) -> List[str]:
        """List of currently enabled gate names."""
        return [n for n, e in self._enabled.items() if e]

    @property
    def stats(self) -> Dict[str, Any]:
        """Return a snapshot of GateKeeper statistics."""
        return {**self._stats, "registered_gates": self.gate_names}
