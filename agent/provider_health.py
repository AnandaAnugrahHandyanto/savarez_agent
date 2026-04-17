"""Optional HTTP probes for local OpenAI-compatible LLM servers."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from agent.model_metadata import _normalize_base_url

logger = logging.getLogger(__name__)

# Short probes — run at most once per agent session when streaming to a local backend.
_PROBE_TIMEOUT = 0.75
_HEALTH_PATHS = ("/healthz", "/health", "/v1/models")


def _probe_root(base_url: str) -> str:
    s = _normalize_base_url(base_url)
    if s.endswith("/v1"):
        s = s[:-3]
    return s.rstrip("/")


def probe_local_provider_health(base_url: str) -> Optional[str]:
    """GET known health paths; return the first path that returned HTTP < 500, else None."""
    if not (base_url or "").strip():
        return None
    root = _probe_root(base_url)
    for path in _HEALTH_PATHS:
        url = f"{root}{path}"
        try:
            with httpx.Client(timeout=_PROBE_TIMEOUT) as client:
                r = client.get(url)
            if 200 <= r.status_code < 300:
                return path
        except Exception:
            continue
    return None


def maybe_log_local_provider_health(agent: object) -> None:
    """One-shot probe for local providers; logs only, never raises."""
    if getattr(agent, "_local_provider_health_probed", False):
        return
    base_url = getattr(agent, "base_url", None) or ""
    from agent.local_provider import is_local_provider

    model_cfg = getattr(agent, "_model_yaml_cfg", None)
    if not is_local_provider(base_url, model_cfg=model_cfg):
        return
    setattr(agent, "_local_provider_health_probed", True)
    path = probe_local_provider_health(base_url)
    if path:
        logger.debug("Local provider health OK (%s on %s)", path, base_url)
    else:
        logger.warning(
            "Local provider health probe found no /healthz|/health|/v1/models on %s — "
            "long prefill is still normal for ollama/vLLM/llama.cpp",
            base_url,
        )
