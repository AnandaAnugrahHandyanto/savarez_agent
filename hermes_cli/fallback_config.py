"""Helpers for reading the effective fallback provider chain from config."""

from __future__ import annotations

import os
from typing import Any, Optional


def _normalized_base_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().rstrip("/")


def _iter_fallback_entries(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        candidates = [raw]
    elif isinstance(raw, list):
        candidates = raw
    else:
        return []

    entries: list[dict[str, Any]] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        provider = str(entry.get("provider") or "").strip()
        model = str(entry.get("model") or "").strip()
        if not provider or not model:
            continue

        normalized = dict(entry)
        normalized["provider"] = provider
        normalized["model"] = model

        base_url = _normalized_base_url(entry.get("base_url"))
        if base_url:
            normalized["base_url"] = base_url

        entries.append(normalized)
    return entries


def _entry_identity(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("provider") or "").strip().lower(),
        str(entry.get("model") or "").strip().lower(),
        _normalized_base_url(entry.get("base_url")).lower(),
    )


def resolve_explicit_api_key_for_fallback(
    entry: dict[str, Any] | None,
) -> Optional[str]:
    """Return the api_key string that should be forwarded to
    ``resolve_runtime_provider`` for a single fallback entry.

    Honors three sources, in order:

    1. Inline ``api_key`` on the entry (raw secret pasted into config.yaml).
    2. Env var named by ``api_key_env`` (Hermes' documented form, matches
       the Azure Foundry / custom_providers guides).
    3. Env var named by ``key_env`` (the canonical field name on
       ``custom_providers`` — accepted for parity so an operator can copy
       a custom_providers block straight into ``fallback_providers``
       without renaming the key).

    Env vars are looked up via :func:`hermes_cli.config.get_env_value` so
    values persisted in ``~/.hermes/.env`` (the per-profile dotenv) are
    honored alongside the live environment. Falls back to ``os.getenv``
    if that import path explodes (matches the rest of the runtime
    provider resolution: never fail closed just because an optional
    import didn't work).

    Returns ``None`` when nothing is configured or the named env var is
    unset / empty — the caller (typically the fallback loop in
    ``cli.py`` or ``gateway/run.py``) should then let
    ``resolve_runtime_provider`` perform its own credential-pool /
    env-var lookups.
    """
    if not isinstance(entry, dict):
        return None
    inline = entry.get("api_key")
    if isinstance(inline, str) and inline.strip():
        return inline.strip()
    for hint_key in ("api_key_env", "key_env"):
        env_name = str(entry.get(hint_key) or "").strip()
        if not env_name:
            continue
        value = None
        try:
            from hermes_cli.config import get_env_value
            value = get_env_value(env_name)
        except Exception:
            value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    return None


def get_fallback_chain(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the effective fallback chain merged across old and new config keys.

    ``fallback_providers`` remains the primary source of truth and keeps its
    order. Legacy ``fallback_model`` entries are appended afterwards unless
    they target the same provider/model/base_url route as an earlier entry.
    The returned list always contains fresh dict copies.
    """

    config = config or {}
    chain: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for key in ("fallback_providers", "fallback_model"):
        for entry in _iter_fallback_entries(config.get(key)):
            identity = _entry_identity(entry)
            if identity in seen:
                continue
            seen.add(identity)
            chain.append(entry)

    return chain
