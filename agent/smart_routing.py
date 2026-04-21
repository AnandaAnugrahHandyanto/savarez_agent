"""Conservative per-turn smart model routing.

Routes obviously simple prompts to a cheaper model when
``smart_model_routing`` is enabled in config.yaml.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_COMPLEX_PATTERNS = (
    r"```",
    r"\btraceback\b",
    r"\bstack\s+trace\b",
    r"\berror:\b",
    r"\bexception\b",
    r"\bfailing\s+test\b",
    r"\bdebug\b",
    r"\bfix\b",
    r"\bpatch\b",
    r"\brefactor\b",
    r"\bimplement\b",
    r"\bwrite\s+code\b",
    r"\bcode\b",
    r"\brepo\b",
    r"\bfunction\b",
    r"\bclass\b",
    r"\bserver\b",
    r"\bapi\b",
    r"\bendpoint\b",
    r"\bsql\b",
    r"\bmigration\b",
    r"\bbuild\b",
    r"\btest\b",
    r"\bfile\b",
    r"\bconfig\b",
    r"\bjson\b",
    r"\byaml\b",
    r"\bpython\b",
    r"\bjavascript\b",
    r"\btypescript\b",
    r"\bbash\b",
    r"\bshell\b",
    r"\bdocker\b",
    r"\bgit\b",
    r"\bterminal\b",
    r"\btool\b",
    r"\bport\b",
    r"/[\w./-]+",
)

_COMPLEX_RE = re.compile("|".join(_COMPLEX_PATTERNS), re.IGNORECASE)


def _load_smart_routing_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
        routing = config.get("smart_model_routing", {}) if isinstance(config, dict) else {}
        return routing if isinstance(routing, dict) else {}
    except Exception:
        return {}


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _simple_turn_reason(user_message: str, routing_config: Dict[str, Any] | None = None) -> tuple[bool, str]:
    routing = routing_config if isinstance(routing_config, dict) else _load_smart_routing_config()
    text = (user_message or "").strip()
    if not text:
        return False, "empty"

    max_chars = _coerce_positive_int(routing.get("max_simple_chars"), 500)
    max_words = _coerce_positive_int(routing.get("max_simple_words"), 80)
    words = len(text.split())
    chars = len(text)

    if chars > max_chars:
        return False, f"chars>{max_chars}"
    if words > max_words:
        return False, f"words>{max_words}"
    if _COMPLEX_RE.search(text):
        return False, "technical-pattern"
    return True, "simple"


def is_simple_turn(user_message: str, routing_config: Dict[str, Any] | None = None) -> bool:
    is_simple, _ = _simple_turn_reason(user_message, routing_config)
    return is_simple


def build_route_notice(
    default_model: str,
    default_runtime: Dict[str, Any],
    effective_model: str,
    runtime: Dict[str, Any],
) -> str | None:
    default_signature = (
        default_model,
        default_runtime.get("provider"),
        default_runtime.get("base_url"),
        default_runtime.get("api_mode"),
        default_runtime.get("command"),
        tuple(default_runtime.get("args") or ()),
    )
    effective_signature = (
        effective_model,
        runtime.get("provider"),
        runtime.get("base_url"),
        runtime.get("api_mode"),
        runtime.get("command"),
        tuple(runtime.get("args") or ()),
    )
    if effective_signature == default_signature:
        return None
    provider = runtime.get("provider") or "unknown-provider"
    return f"⚡ Smart routing: using {effective_model} via {provider} for this turn."



def resolve_turn_route(
    user_message: str,
    default_model: str,
    default_runtime: Dict[str, Any],
    routing_config: Dict[str, Any] | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """Return the effective (model, runtime) for a single turn.

    Falls back to the provided default route unless a cheap route is both
    configured and appropriate for this user message.
    """
    routing = routing_config if isinstance(routing_config, dict) else _load_smart_routing_config()
    if not routing.get("enabled"):
        return default_model, dict(default_runtime)

    cheap_model = routing.get("cheap_model", {})
    if not isinstance(cheap_model, dict):
        return default_model, dict(default_runtime)

    cheap_provider = str(cheap_model.get("provider") or "").strip()
    cheap_model_name = str(cheap_model.get("model") or "").strip()
    if not cheap_provider or not cheap_model_name:
        return default_model, dict(default_runtime)

    is_simple, reason = _simple_turn_reason(user_message, routing)
    if not is_simple:
        logger.debug(
            "Smart routing skipped for %s (%s)",
            default_model or "default-model",
            reason,
        )
        return default_model, dict(default_runtime)

    runtime = dict(default_runtime)
    runtime["provider"] = cheap_provider
    runtime["base_url"] = str(cheap_model.get("base_url") or "").strip() or None
    runtime["api_mode"] = str(cheap_model.get("api_mode") or "").strip() or None

    explicit_key = cheap_model.get("api_key")
    if runtime["base_url"]:
        runtime["api_key"] = "" if explicit_key is None else str(explicit_key)
    else:
        runtime["api_key"] = str(explicit_key).strip() if explicit_key not in (None, "") else None

    runtime["command"] = None
    runtime["args"] = []
    runtime["credential_pool"] = None

    logger.info(
        "Smart routing applied: %s (%s) -> %s (%s)",
        default_model or "default-model",
        default_runtime.get("provider") or "default-provider",
        cheap_model_name,
        cheap_provider,
    )
    return cheap_model_name, runtime
