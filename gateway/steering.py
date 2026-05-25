"""Gateway steering helpers.

Steering is the non-destructive busy-message path: the gateway acknowledges
only when the current step is slow, then injects a structured interruption
context into the running worker so the worker decides whether to continue or
stop at a breakpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from hermes_cli.config import cfg_get
from utils import is_truthy_value

logger = logging.getLogger(__name__)


DEFAULT_ACK_TEMPLATE = (
    "⚡️ Message reçu — je termine (itération {current}/{total}) et je te réponds."
)

DEFAULT_CONTEXT_TEMPLATE = """---
⚠️ Interruption — itération {current}/{total} en cours.
Message de {user}: "{message}"

Tu dois:
1. Répondre au message
2. Décider si tu t'arrêtes ou si tu continues:
   - Si le message est lié à la tâche en cours, intègre-le, réponds, et reprends le travail
   - Si c'est un changement de sujet ou un stop/pause explicite, réponds, puis marque un point d'arrêt structuré en terminant par:
     <hermes_steering_breakpoint>{{"reason":"...","resume_hint":"..."}}</hermes_steering_breakpoint>
---"""


@dataclass(frozen=True)
class SteeringConfig:
    enabled: bool = True
    ack_threshold_seconds: float = 5.0
    ack_timeout_seconds: float = 3.0
    landing_timeout_seconds: float = 30.0
    iteration_hard_timeout: float = 120.0
    auto_resume: bool = True
    ack_template: str = DEFAULT_ACK_TEMPLATE
    interruption_template: str = DEFAULT_CONTEXT_TEMPLATE


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _template_vars(
    *,
    message: str = "",
    user: str = "l'utilisateur",
    activity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    activity = activity or {}
    current = activity.get("api_call_count") or activity.get("current") or 0
    total = activity.get("max_iterations") or activity.get("total") or 0
    step_elapsed = activity.get("seconds_since_activity") or 0
    elapsed_min = 0
    try:
        elapsed_min = int(float(activity.get("run_elapsed_seconds") or 0) // 60)
    except (TypeError, ValueError):
        elapsed_min = 0
    return {
        "current": current,
        "iteration": current,
        "total": total,
        "max_iterations": total,
        "current_tool": activity.get("current_tool") or "",
        "iteration_elapsed_seconds": step_elapsed,
        "elapsed_min": elapsed_min,
        "user": user or "l'utilisateur",
        "message": message or "",
    }


def load_steering_config(config: Mapping[str, Any] | None) -> SteeringConfig:
    """Return steering config with defaults applied to a raw config mapping."""
    raw = cfg_get(config, "steering", default={}) if config else {}
    if not isinstance(raw, Mapping):
        raw = {}
    defaults = SteeringConfig()
    return SteeringConfig(
        enabled=is_truthy_value(raw.get("enabled"), default=defaults.enabled),
        ack_threshold_seconds=_coerce_float(
            raw.get("ack_threshold_seconds"),
            defaults.ack_threshold_seconds,
        ),
        ack_timeout_seconds=_coerce_float(
            raw.get("ack_timeout_seconds"),
            defaults.ack_timeout_seconds,
        ),
        landing_timeout_seconds=_coerce_float(
            raw.get("landing_timeout_seconds"),
            defaults.landing_timeout_seconds,
        ),
        iteration_hard_timeout=_coerce_float(
            raw.get("iteration_hard_timeout"),
            defaults.iteration_hard_timeout,
        ),
        auto_resume=is_truthy_value(raw.get("auto_resume"), default=defaults.auto_resume),
        ack_template=str(raw.get("ack_template") or defaults.ack_template),
        interruption_template=str(
            raw.get("interruption_template") or defaults.interruption_template
        ),
    )


def render_ack(
    steering: SteeringConfig,
    *,
    message: str = "",
    user: str = "l'utilisateur",
    activity: Mapping[str, Any] | None = None,
) -> str:
    """Render the configured ack template, falling back on a safe default."""
    values = _template_vars(message=message, user=user, activity=activity)
    try:
        return steering.ack_template.format(**values)
    except Exception as exc:
        logger.warning("Invalid steering ack_template, using default: %s", exc)
        return DEFAULT_ACK_TEMPLATE.format(**values)


def render_interruption_context(
    steering: SteeringConfig,
    *,
    message: str,
    user: str = "l'utilisateur",
    activity: Mapping[str, Any] | None = None,
) -> str:
    """Render the worker-visible interruption context block."""
    values = _template_vars(message=message, user=user, activity=activity)
    try:
        return steering.interruption_template.format(**values)
    except Exception as exc:
        logger.warning("Invalid steering interruption_template, using default: %s", exc)
        return DEFAULT_CONTEXT_TEMPLATE.format(**values)


def should_send_ack(
    steering: SteeringConfig,
    activity: Mapping[str, Any] | None,
) -> bool:
    """Return True when the current step has exceeded the ack threshold."""
    if not steering.enabled:
        return False
    threshold = max(0.0, steering.ack_threshold_seconds)
    if threshold <= 0:
        return True
    try:
        elapsed = float((activity or {}).get("seconds_since_activity") or 0)
    except (TypeError, ValueError):
        elapsed = 0.0
    return elapsed >= threshold
