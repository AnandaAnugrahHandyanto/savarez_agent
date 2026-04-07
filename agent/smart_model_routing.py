"""Helpers for optional cheap-vs-strong model routing."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Sequence

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
    "authentication",
    "auth",
    "security",
    "secret",
    "credential",
    "migration",
    "schema",
    "database",
    "api",
    "token",
    "integration",
    "regression",
    "vulnerability",
    "restart",
    "service",
    "systemctl",
    "journalctl",
    "log",
    "logs",
    "incident",
    "run",
    "execute",
    "check",
    "test",
    "health",
    "healthcheck",
    "doctor",
    "fuehre",
    "führe",
    "teste",
    "pruefe",
    "prüfe",
    "ausfuehren",
    "ausführen",
}

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    return is_truthy_value(value, default=default)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", word.strip().lower())


def _coerce_keyword_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence):
        return set()
    out: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        norm = _normalize_word(item)
        if norm:
            out.add(norm)
    return out


def _coerce_regexes(value: Any) -> list[re.Pattern[str]]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence):
        return []
    out: list[re.Pattern[str]] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            out.append(re.compile(item, flags=re.IGNORECASE))
        except re.error:
            continue
    return out


def _tokenize_words(text: str) -> set[str]:
    return {_normalize_word(token) for token in text.split() if _normalize_word(token)}


def _coerce_route_definition(route: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(route, dict):
        return None
    provider = str(route.get("provider") or "").strip().lower()
    model = str(route.get("model") or "").strip()
    if not provider or not model:
        return None
    return {
        "provider": provider,
        "model": model,
        "base_url": str(route.get("base_url") or "").strip() or None,
        "api_key_env": str(route.get("api_key_env") or "").strip() or None,
    }


def _is_route_simple(user_message: str, routing_config: Optional[Dict[str, Any]]) -> bool:
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return False

    text = (user_message or "").strip()
    if not text:
        return False

    max_chars = _coerce_int(cfg.get("max_simple_chars"), 160)
    max_words = _coerce_int(cfg.get("max_simple_words"), 28)
    max_newlines = _coerce_int(cfg.get("max_newlines"), 1)

    if len(text) > max_chars:
        return False
    if len(text.split()) > max_words:
        return False
    if text.count("\n") > max_newlines:
        return False
    if _coerce_bool(cfg.get("forbid_code_fences"), True) and ("```" in text or "`" in text):
        return False
    if _coerce_bool(cfg.get("forbid_urls"), True) and _URL_RE.search(text):
        return False

    words = _tokenize_words(text.lower())
    complex_keywords = set(_COMPLEX_KEYWORDS)
    complex_keywords.update(_coerce_keyword_set(cfg.get("complex_keywords")))
    if words & complex_keywords:
        return False

    for pattern in _coerce_regexes(cfg.get("forbidden_patterns")):
        if pattern.search(text):
            return False

    return True


def choose_cheap_model_route(user_message: str, routing_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the configured cheap-model route when a message looks simple.

    Conservative by design: if the message has signs of code/tool/debugging/
    long-form work, keep the primary model.
    """
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return None

    cheap_model = _coerce_route_definition(cfg.get("cheap_model"))
    if not cheap_model:
        return None
    if not _is_route_simple(user_message, cfg):
        return None

    route = dict(cheap_model)
    route["routing_reason"] = "simple_turn"
    return route


def choose_expensive_model_route(user_message: str, routing_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the configured strong-model override when a message looks complex."""
    cfg = routing_config or {}
    if not _coerce_bool(cfg.get("enabled"), False):
        return None
    if _is_route_simple(user_message, cfg):
        return None

    expensive_model = _coerce_route_definition(cfg.get("expensive_model"))
    if not expensive_model:
        return None

    route = dict(expensive_model)
    route["routing_reason"] = "complex_turn"
    return route


def resolve_turn_route(user_message: str, routing_config: Optional[Dict[str, Any]], primary: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the effective model/runtime for one turn.

    Returns a dict with model/runtime/signature/label fields.
    """
    route = choose_cheap_model_route(user_message, routing_config)
    if not route:
        route = choose_expensive_model_route(user_message, routing_config)
    if not route:
        return {
            "model": primary.get("model"),
            "runtime": {
                "api_key": primary.get("api_key"),
                "base_url": primary.get("base_url"),
                "provider": primary.get("provider"),
                "api_mode": primary.get("api_mode"),
                "command": primary.get("command"),
                "args": list(primary.get("args") or []),
                "credential_pool": primary.get("credential_pool"),
            },
            "label": None,
            "signature": (
                primary.get("model"),
                primary.get("provider"),
                primary.get("base_url"),
                primary.get("api_mode"),
                primary.get("command"),
                tuple(primary.get("args") or ()),
            ),
        }

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
        return {
            "model": primary.get("model"),
            "runtime": {
                "api_key": primary.get("api_key"),
                "base_url": primary.get("base_url"),
                "provider": primary.get("provider"),
                "api_mode": primary.get("api_mode"),
                "command": primary.get("command"),
                "args": list(primary.get("args") or []),
                "credential_pool": primary.get("credential_pool"),
            },
            "label": None,
            "signature": (
                primary.get("model"),
                primary.get("provider"),
                primary.get("base_url"),
                primary.get("api_mode"),
                primary.get("command"),
                tuple(primary.get("args") or ()),
            ),
        }

    primary_model = str(primary.get("model") or "unknown")
    primary_provider = str(primary.get("provider") or "unknown")
    routed_model = str(route.get("model") or "unknown")
    routed_provider = str(runtime.get("provider") or "unknown")

    return {
        "model": route.get("model"),
        "runtime": {
            "api_key": runtime.get("api_key"),
            "base_url": runtime.get("base_url"),
            "provider": runtime.get("provider"),
            "api_mode": runtime.get("api_mode"),
            "command": runtime.get("command"),
            "args": list(runtime.get("args") or []),
        },
        "label": f"smart route: {primary_model} ({primary_provider}) -> {routed_model} ({routed_provider})",
        "signature": (
            route.get("model"),
            runtime.get("provider"),
            runtime.get("base_url"),
            runtime.get("api_mode"),
            runtime.get("command"),
            tuple(runtime.get("args") or ()),
        ),
    }
