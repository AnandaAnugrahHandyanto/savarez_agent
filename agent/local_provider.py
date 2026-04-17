"""Local LLM provider detection and stale-timeout helpers for run_agent."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

from agent.model_metadata import is_local_endpoint

_FORCE_ENV = "HERMES_FORCE_LOCAL_PROVIDER"
# config.yaml → model.local_inference: true  (custom domains tunneled to local GPUs)
_CFG_LOCAL_INFERENCE = "local_inference"


def is_local_provider(
    base_url: Optional[str],
    *,
    model_cfg: Optional[Mapping[str, Any]] = None,
) -> bool:
    """True when the active endpoint should use local-provider timeouts and probes.

    Triggers on RFC1918/localhost URLs, optional ``model.local_inference`` in
    config, or ``HERMES_FORCE_LOCAL_PROVIDER=1``.
    """
    if os.getenv(_FORCE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if model_cfg and isinstance(model_cfg, Mapping):
        v = model_cfg.get(_CFG_LOCAL_INFERENCE)
        if v is True:
            return True
        if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
            return True
    return bool(base_url and is_local_endpoint(base_url))


def resolve_local_stream_stale_timeout() -> float:
    """Seconds before the outer streaming stale watchdog may fire for *local* providers.

    ``HERMES_LOCAL_STREAM_STALE_TIMEOUT`` (default ``3600``): use ``0`` or ``inf``
    for no cap (infinity). Minimum 1.0 when finite.
    """
    raw = os.getenv("HERMES_LOCAL_STREAM_STALE_TIMEOUT", "3600").strip().lower()
    if raw in ("0", "inf", "infinite", "none"):
        return float("inf")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 3600.0


def resolve_local_api_call_stale_timeout() -> float:
    """Same semantics as :func:`resolve_local_stream_stale_timeout` for non-streaming calls."""
    raw = os.getenv("HERMES_LOCAL_API_CALL_STALE_TIMEOUT", "3600").strip().lower()
    if raw in ("0", "inf", "infinite", "none"):
        return float("inf")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 3600.0


def _est_message_tokens(messages: list) -> int:
    return sum(len(str(v)) for v in messages) // 4


def compute_stream_stale_timeout(
    *,
    base_url: Optional[str],
    model_cfg: Optional[Mapping[str, Any]],
    stream_stale_timeout_base: float,
    messages: list,
) -> float:
    """Wall-clock seconds before the streaming stale detector may kill the connection."""
    if is_local_provider(base_url, model_cfg=model_cfg):
        t = resolve_local_stream_stale_timeout()
        if t == float("inf"):
            return t
        est = _est_message_tokens(messages)
        if est > 100_000:
            return max(t, 600.0)
        if est > 50_000:
            return max(t, 450.0)
        return t
    est = _est_message_tokens(messages)
    if est > 100_000:
        return max(stream_stale_timeout_base, 300.0)
    if est > 50_000:
        return max(stream_stale_timeout_base, 240.0)
    return stream_stale_timeout_base


def compute_api_call_stale_timeout(
    *,
    base_url: Optional[str],
    model_cfg: Optional[Mapping[str, Any]],
    stale_base: float,
    messages: list,
) -> float:
    """Wall-clock seconds before the non-streaming stale detector may kill the call."""
    if is_local_provider(base_url, model_cfg=model_cfg):
        t = resolve_local_api_call_stale_timeout()
        if t == float("inf"):
            return t
        est = _est_message_tokens(messages)
        if est > 100_000:
            return max(t, 600.0)
        if est > 50_000:
            return max(t, 450.0)
        return t
    est = _est_message_tokens(messages)
    if est > 100_000:
        return max(stale_base, 600.0)
    if est > 50_000:
        return max(stale_base, 450.0)
    return stale_base
