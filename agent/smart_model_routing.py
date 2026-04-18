"""Helpers for optional cheap-vs-strong model routing."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from utils import is_truthy_value

_COMPLEX_KEYWORDS = {
    "debug",
    "debugging",
    "implement",
    "implementation",
    "refactor",
    "patch",
    "traceback",
    "stacktrace",
    "exception",
    "error",
    "analyze",
    "analysis",
    "investigate",
    "architecture",
    "design",
    "compare",
    "benchmark",
    "optimize",
    "optimise",
    "review",
    "terminal",
    "shell",
    "tool",
    "tools",
    "pytest",
    "test",
    "tests",
    "plan",
    "planning",
    "delegate",
    "subagent",
    "cron",
    "docker",
    "kubernetes",
}

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    return is_truthy_value(value, default=default)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_result(model: Any, runtime: Dict[str, Any], label: Optional[str]) -> Dict[str, Any]:
    return {
        "model": model,
        "runtime": {
            "api_key": runtime.get("api_key"),
            "base_url": runtime.get("base_url"),
            "provider": runtime.get("provider"),
            "api_mode": runtime.get("api_mode"),
            "command": runtime.get("command"),
            "args": list(runtime.get("args") or []),
            "credential_pool": runtime.get("credential_pool"),
        },
        "label": label,
        "signature": (
            model,
            runtime.get("provider"),
            runtime.get("base_url"),
            runtime.get("api_mode"),
            runtime.get("command"),
            tuple(runtime.get("args") or ()),
        ),
    }


def _build_primary_result(primary: Dict[str, Any]) -> Dict[str, Any]:
    return _build_result(
        primary.get("model"),
        {
            "api_key": primary.get("api_key"),
            "base_url": primary.get("base_url"),
            "provider": primary.get("provider"),
            "api_mode": primary.get("api_mode"),
            "command": primary.get("command"),
            "args": list(primary.get("args") or []),
            "credential_pool": primary.get("credential_pool"),
        },
        None,
    )


def _normalize_route_entry(route: Any, *, reason: str) -> Optional[Dict[str, Any]]:
    if not isinstance(route, dict):
        return None

    provider = str(route.get("provider") or "").strip().lower()
    model = str(route.get("model") or "").strip()
    if not provider or not model:
        return None

    normalized = dict(route)
    normalized["provider"] = provider
    normalized["model"] = model
    normalized["routing_reason"] = reason
    return normalized


def _resolve_configured_route(route: Optional[Dict[str, Any]], *, label_prefix: str) -> Optional[Dict[str, Any]]:
    if not route:
        return None

    from hermes_cli.runtime_provider import resolve_runtime_provider

    explicit_api_key = None
    api_key_env = str(route.get("api_key_env") or "").strip()
    if api_key_env:
        explicit_api_key = os.getenv(api_key_env) or None

    try:
        runtime = resolve_runtime_provider(
            requested=route.get("provider"),
            explicit_api_key=explicit_api_key,
            explicit_base_url=route.get("base_url"),
        )
    except Exception:
        return None

    return _build_result(
        route.get("model"),
        runtime,
        f"{label_prefix} {route.get('model')} ({runtime.get('provider')})",
    )


def choose_primary_agent_route(routing_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the configured strong/primary route when smart routing is enabled."""
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return None

    return _normalize_route_entry(
        cfg.get("primary_agent"),
        reason="primary_agent",
    )


def choose_cheap_model_route(user_message: str, routing_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the configured cheap-model route when a message looks simple.

    Conservative by design: if the message has signs of code/tool/debugging/
    long-form work, keep the primary model.
    """
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return None

    cheap_model = _normalize_route_entry(
        cfg.get("cheap_model") or {},
        reason="simple_turn",
    )
    if not cheap_model:
        return None

    text = (user_message or "").strip()
    if not text:
        return None

    max_chars = _coerce_int(cfg.get("max_simple_chars"), 160)
    max_words = _coerce_int(cfg.get("max_simple_words"), 28)

    if len(text) > max_chars:
        return None
    if len(text.split()) > max_words:
        return None
    if text.count("\n") > 1:
        return None
    if "```" in text or "`" in text:
        return None
    if _URL_RE.search(text):
        return None

    lowered = text.lower()
    words = {token.strip(".,:;!?()[]{}\"'`") for token in lowered.split()}
    if words & _COMPLEX_KEYWORDS:
        return None

    return cheap_model


def resolve_turn_route(user_message: str, routing_config: Optional[Dict[str, Any]], primary: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the effective model/runtime for one turn.

    Returns a dict with model/runtime/signature/label fields.
    """
    default_primary = _build_primary_result(primary)
    primary_route = choose_primary_agent_route(routing_config)

    def _resolve_effective_primary() -> Dict[str, Any]:
        configured_primary = _resolve_configured_route(
            primary_route,
            label_prefix="smart route → primary",
        )
        return configured_primary or default_primary

    route = choose_cheap_model_route(user_message, routing_config)
    if not route:
        return _resolve_effective_primary()

    cheap_result = _resolve_configured_route(route, label_prefix="smart route →")
    return cheap_result or _resolve_effective_primary()
