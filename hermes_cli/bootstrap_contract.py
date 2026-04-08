"""Shared machine-readable readiness helpers for Hermes surfaces."""

from __future__ import annotations

import io
from contextlib import nullcontext, redirect_stdout
from typing import Any

from hermes_cli.config import get_env_value

_PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "OPENAI_BASE_URL",
    "GLM_API_KEY",
    "ZAI_API_KEY",
    "Z_AI_API_KEY",
    "KIMI_API_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY",
    "KILOCODE_API_KEY",
    "AI_GATEWAY_API_KEY",
    "HF_TOKEN",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
)


def collect_provider_readiness(config: dict[str, Any] | None = None, *, quiet: bool = False) -> dict[str, Any]:
    """Return a compact provider-readiness snapshot for bootstrap flows."""
    config = config or {}
    env_configured = any(bool(get_env_value(name)) for name in _PROVIDER_ENV_VARS)

    oauth = {
        "nous": False,
        "openai_codex": False,
    }
    try:
        from hermes_cli.auth import get_nous_auth_status, get_codex_auth_status

        stream = io.StringIO()
        ctx = redirect_stdout(stream) if quiet else nullcontext()
        with ctx:
            oauth["nous"] = bool(get_nous_auth_status().get("logged_in"))
            oauth["openai_codex"] = bool(get_codex_auth_status().get("logged_in"))
    except Exception:
        pass

    model_cfg = config.get("model")
    config_configured = False
    if isinstance(model_cfg, dict):
        config_configured = bool(
            (model_cfg.get("provider") or "").strip()
            or (model_cfg.get("base_url") or "").strip()
            or (model_cfg.get("api_key") or "").strip()
        )

    return {
        "configured": bool(env_configured or config_configured or any(oauth.values())),
        "env_configured": env_configured,
        "config_configured": config_configured,
        "oauth": oauth,
    }


def build_bootstrap_summary(
    *,
    env_exists: bool,
    config_exists: bool,
    provider_ready: bool,
    gateway_configured: bool | None = None,
    gateway_running: bool | None = None,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    """Build a stable readiness summary for CLI and UI consumers."""
    blockers: list[dict[str, str]] = []
    next_steps: list[str] = []

    if not env_exists:
        blockers.append({
            "code": "env_missing",
            "message": "Hermes environment file is missing.",
        })
        next_steps.append("Run `hermes setup` to create ~/.hermes/.env.")

    if not config_exists:
        blockers.append({
            "code": "config_missing",
            "message": "Hermes config.yaml is missing.",
        })
        next_steps.append("Run `hermes setup` to create ~/.hermes/config.yaml.")

    if not provider_ready:
        blockers.append({
            "code": "provider_not_configured",
            "message": "No usable model provider is configured yet.",
        })
        next_steps.append("Run `hermes model` or `hermes setup` to configure a provider.")

    if gateway_configured is True and gateway_running is False:
        next_steps.append("Run `hermes gateway start` after setup to bring the gateway online.")
    elif gateway_configured is False:
        next_steps.append("Run `hermes gateway setup` if you want Hermes available on chat platforms.")

    if issues:
        next_steps.append("Run `hermes doctor` for detailed diagnostics.")

    # Keep guidance stable and deduplicated for UI consumers.
    deduped_steps: list[str] = []
    seen = set()
    for step in next_steps:
        if step not in seen:
            deduped_steps.append(step)
            seen.add(step)

    return {
        "ready": not blockers,
        "blocking_checks": blockers,
        "recommended_next_steps": deduped_steps,
        "issue_count": len(issues or []),
    }
