"""Shared Codex subscription usage guardrail helpers.

The cron watchdog writes ``codex_usage_pause.json`` in the shared Hermes root
when any tracked Codex 5-hour/session or weekly bucket reaches the configured
threshold. Runtime dispatch paths use this module to fail closed before starting
new Codex-backed autonomous work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


CODEX_USAGE_PAUSE_FILENAME = "codex_usage_pause.json"


def codex_usage_pause_path(root: Optional[Path | str] = None) -> Path:
    """Return the pause-sentinel path for the shared Hermes root."""
    if root is None:
        from hermes_constants import get_default_hermes_root

        root_path = get_default_hermes_root()
    else:
        root_path = Path(root).expanduser()
    return root_path / CODEX_USAGE_PAUSE_FILENAME


def is_codex_usage_paused(root: Optional[Path | str] = None) -> bool:
    """Return True when the usage watchdog pause sentinel currently exists."""
    try:
        return codex_usage_pause_path(root).exists()
    except OSError:
        # Fail closed: if the root cannot be inspected, don't launch new
        # subscription-backed autonomous work while the guardrail is in doubt.
        return True


def provider_model_uses_codex(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> bool:
    """Best-effort check for whether a provider/model context is Codex-backed.

    The ChatGPT Codex backend URL is authoritative because Hermes credential
    resolution gives explicit ``base_url`` values routing precedence. Without
    this override, a config that says ``provider: openrouter`` but points
    ``base_url`` at ``chatgpt.com/backend-api/codex`` could start Codex-backed
    workers while the pause sentinel is active.

    Otherwise explicit non-Codex providers win over model names that happen to
    contain ``codex``.
    """
    provider_s = str(provider or "").strip().lower()
    model_s = str(model or "").strip().lower()
    base_s = str(base_url or "").strip().lower()

    if "chatgpt.com" in base_s and "/backend-api/codex" in base_s:
        return True
    if provider_s:
        return provider_s == "openai-codex"
    return "codex" in model_s


def delegation_config_uses_codex(cfg: dict[str, Any], parent_agent: Any = None) -> bool:
    """Return True if a delegate_task call would route to Codex.

    ``delegation.provider`` / ``delegation.base_url`` override inheritance. If
    neither is set, the child inherits the parent agent provider/model context.
    """
    cfg = cfg or {}
    cfg_provider = str(cfg.get("provider") or "").strip() or None
    cfg_model = str(cfg.get("model") or "").strip() or None
    cfg_base_url = str(cfg.get("base_url") or "").strip() or None

    if cfg_provider or cfg_base_url:
        return provider_model_uses_codex(
            provider=cfg_provider,
            model=cfg_model,
            base_url=cfg_base_url,
        )

    parent_provider = getattr(parent_agent, "provider", None) if parent_agent is not None else None
    parent_model = cfg_model or (getattr(parent_agent, "model", None) if parent_agent is not None else None)
    parent_base_url = getattr(parent_agent, "base_url", None) if parent_agent is not None else None
    return provider_model_uses_codex(
        provider=parent_provider,
        model=parent_model,
        base_url=parent_base_url,
    )


def format_codex_usage_pause_message(
    *,
    root: Optional[Path | str] = None,
    source: str = "autonomous dispatch",
) -> str:
    """Human-readable message for dispatchers that refuse to start work."""
    path = codex_usage_pause_path(root)
    return (
        f"Codex usage guardrail is active for {source}: the watchdog wrote "
        f"{path} after a 5-hour/session or weekly Codex bucket reached the "
        "90% pause threshold. New Codex-backed autonomous work is blocked "
        "until Will approves continuing on paid credits or the sentinel is "
        "cleared after limits reset."
    )
