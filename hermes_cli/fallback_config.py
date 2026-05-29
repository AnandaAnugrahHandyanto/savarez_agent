"""Helpers for reading the effective fallback provider chain from config."""

from __future__ import annotations

from typing import Any


_OPUS_48_MARKERS = (
    "opus-4.8",
    "opus4.8",
    "opus_4_8",
    "opus-4-8",
    "opus 4.8",
)


def is_opus_48_model(model: Any) -> bool:
    """Return True when a model slug/name identifies the disallowed Opus 4.8."""

    normalized = str(model or "").strip().lower().replace("_", "-")
    compact = normalized.replace("-", "").replace(" ", "")
    return any(marker in normalized for marker in _OPUS_48_MARKERS) or "opus48" in compact


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


def _entry_identity(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(entry.get("provider") or "").strip().lower(),
        str(entry.get("model") or "").strip().lower(),
        _normalized_base_url(entry.get("base_url")).lower(),
        str(entry.get("reasoning_effort") or "").strip().lower(),
    )


def sanitize_fallback_chain(raw: Any) -> list[dict[str, Any]]:
    """Normalize, de-duplicate, and policy-filter fallback entries.

    Opus 4.8 is not allowed as an active default, runtime fallback, cron
    fallback, or delegated-child inherited fallback. Keeping the filter here
    makes stale config safe even when callers pass the legacy single-dict shape.
    """

    chain: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry in _iter_fallback_entries(raw):
        if is_opus_48_model(entry.get("model")):
            continue
        identity = _entry_identity(entry)
        if identity in seen:
            continue
        seen.add(identity)
        chain.append(entry)
    return chain


def role_fallback_chain(role: str, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the effective fallback chain for a worker role.

    Configured ``role_fallbacks.<role>`` entries win. Builder-like roles get the
    requested deterministic recovery ladder when no explicit role override is
    present: MiniMax M2.7 → GPT 5.5 medium → GPT 5.5 xhigh. Reviewer/hardening
    roles use the ordinary sanitized global fallback chain unless overridden.
    """

    config = config or {}
    role_key = str(role or "").strip().lower()
    role_overrides = config.get("role_fallbacks") or {}
    if isinstance(role_overrides, dict) and role_key in role_overrides:
        return sanitize_fallback_chain(role_overrides.get(role_key))

    if role_key in {"builder", "implementer", "worker", "optimizer", "refactor"}:
        return sanitize_fallback_chain([
            {"provider": "minimax", "model": "MiniMax-M2.7", "reasoning_effort": "medium"},
            {"provider": "openai-codex", "model": "gpt-5.5", "reasoning_effort": "medium"},
            {"provider": "openai-codex", "model": "gpt-5.5", "reasoning_effort": "xhigh"},
        ])

    return get_fallback_chain(config)


def get_fallback_chain(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the effective fallback chain merged across old and new config keys.

    ``fallback_providers`` remains the primary source of truth and keeps its
    order. Legacy ``fallback_model`` entries are appended afterwards unless
    they target the same provider/model/base_url route as an earlier entry.
    The returned list always contains fresh dict copies and excludes disallowed
    Opus 4.8 routes.
    """

    config = config or {}
    return sanitize_fallback_chain([
        *(_iter_fallback_entries(config.get("fallback_providers"))),
        *(_iter_fallback_entries(config.get("fallback_model"))),
    ])
