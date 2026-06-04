"""Gateway context handoff policy helpers.

A context handoff is the gateway-side safety valve that compresses an oversized
conversation into a fresh session before the next agent run.  Keeping the policy
in a small pure module makes the thresholds testable without booting the full
gateway runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ContextHandoffPolicy:
    """Resolved thresholds for proactive session handoff."""

    enabled: bool
    token_threshold: int
    hard_message_limit: int


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_int(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _coerce_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def resolve_context_handoff_policy(
    user_config: Mapping[str, Any] | None,
    *,
    context_length: int,
) -> ContextHandoffPolicy:
    """Resolve proactive handoff thresholds from ``compression`` config.

    Defaults are intentionally earlier than the historical gateway hygiene
    threshold.  The 60k absolute cap protects providers that become slow before
    their advertised context limit, while the ratio still scales down for small
    context windows.
    """

    cfg: Mapping[str, Any] = {}
    if isinstance(user_config, Mapping):
        maybe_cfg = user_config.get("compression", {})
        if isinstance(maybe_cfg, Mapping):
            cfg = maybe_cfg

    enabled = _coerce_bool(cfg.get("handoff_enabled"), True)
    ratio = _coerce_float(cfg.get("handoff_threshold"), 0.60, minimum=0.05, maximum=0.95)
    max_prompt_tokens = _coerce_int(cfg.get("handoff_max_prompt_tokens"), 60_000, minimum=1)
    hard_message_limit = _coerce_int(
        cfg.get("hygiene_hard_message_limit"),
        400,
        minimum=1,
    )

    safe_context_length = max(int(context_length or 0), 1)
    ratio_threshold = max(int(safe_context_length * ratio), 1)
    token_threshold = min(ratio_threshold, max_prompt_tokens)

    return ContextHandoffPolicy(
        enabled=enabled,
        token_threshold=token_threshold,
        hard_message_limit=hard_message_limit,
    )


def should_handoff_context(
    *,
    tokens: int,
    message_count: int,
    policy: ContextHandoffPolicy,
) -> bool:
    """Return True when the gateway should hand off to a fresh session."""

    if not policy.enabled:
        return False
    return tokens >= policy.token_threshold or message_count >= policy.hard_message_limit
