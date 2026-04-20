"""Gateway startup config -> environment bridge helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from hermes_cli import config as hermes_config

logger = logging.getLogger(__name__)


_AUX_TASK_ENV = {
    "vision": {
        "provider": "AUXILIARY_VISION_PROVIDER",
        "model": "AUXILIARY_VISION_MODEL",
        "base_url": "AUXILIARY_VISION_BASE_URL",
        "api_key": "AUXILIARY_VISION_API_KEY",
    },
    "web_extract": {
        "provider": "AUXILIARY_WEB_EXTRACT_PROVIDER",
        "model": "AUXILIARY_WEB_EXTRACT_MODEL",
        "base_url": "AUXILIARY_WEB_EXTRACT_BASE_URL",
        "api_key": "AUXILIARY_WEB_EXTRACT_API_KEY",
    },
    "approval": {
        "provider": "AUXILIARY_APPROVAL_PROVIDER",
        "model": "AUXILIARY_APPROVAL_MODEL",
        "base_url": "AUXILIARY_APPROVAL_BASE_URL",
        "api_key": "AUXILIARY_APPROVAL_API_KEY",
    },
}

_TERMINAL_ENV_MAP = {
    "backend": "TERMINAL_ENV",
    "cwd": "TERMINAL_CWD",
    "timeout": "TERMINAL_TIMEOUT",
    "lifetime_seconds": "TERMINAL_LIFETIME_SECONDS",
    "docker_image": "TERMINAL_DOCKER_IMAGE",
    "docker_forward_env": "TERMINAL_DOCKER_FORWARD_ENV",
    "singularity_image": "TERMINAL_SINGULARITY_IMAGE",
    "modal_image": "TERMINAL_MODAL_IMAGE",
    "daytona_image": "TERMINAL_DAYTONA_IMAGE",
    "ssh_host": "TERMINAL_SSH_HOST",
    "ssh_user": "TERMINAL_SSH_USER",
    "ssh_port": "TERMINAL_SSH_PORT",
    "ssh_key": "TERMINAL_SSH_KEY",
    "container_cpu": "TERMINAL_CONTAINER_CPU",
    "container_memory": "TERMINAL_CONTAINER_MEMORY",
    "container_disk": "TERMINAL_CONTAINER_DISK",
    "container_persistent": "TERMINAL_CONTAINER_PERSISTENT",
    "docker_volumes": "TERMINAL_DOCKER_VOLUMES",
    "sandbox_dir": "TERMINAL_SANDBOX_DIR",
    "persistent_shell": "TERMINAL_PERSISTENT_SHELL",
}


def load_gateway_startup_bridge_config(hermes_home: Path) -> dict[str, Any]:
    """Load user-authored config for gateway startup env bridging."""
    try:
        cfg = hermes_config.read_user_config(
            expand_env=True,
            merge_defaults=False,
            config_path=hermes_home / "config.yaml",
        )
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        logger.debug("Could not load startup bridge config from %s", hermes_home / "config.yaml")
        return {}



def apply_gateway_startup_env_bridge(cfg: dict[str, Any]) -> None:
    """Bridge selected config values into environment variables for gateway startup."""
    if not isinstance(cfg, dict):
        return

    # Top-level simple values (fallback only — don't override .env)
    for key, value in cfg.items():
        if isinstance(value, (str, int, float, bool)) and key not in os.environ:
            os.environ[key] = str(value)

    # Terminal config is nested — bridge to TERMINAL_* env vars.
    # config.yaml overrides .env for these since it's the documented config path.
    terminal_cfg = cfg.get("terminal", {})
    if isinstance(terminal_cfg, dict):
        for cfg_key, env_var in _TERMINAL_ENV_MAP.items():
            if cfg_key not in terminal_cfg:
                continue
            value = terminal_cfg[cfg_key]
            # Skip cwd placeholder values (".", "auto", "cwd") — the gateway
            # resolves these to Path.home() later.
            if cfg_key == "cwd" and str(value) in (".", "auto", "cwd"):
                continue
            if isinstance(value, list):
                os.environ[env_var] = json.dumps(value)
            else:
                os.environ[env_var] = str(value)

    # Compression config is read directly from config.yaml by run_agent.py
    # and auxiliary_client.py — no env var bridging needed.
    auxiliary_cfg = cfg.get("auxiliary", {})
    if isinstance(auxiliary_cfg, dict):
        for task_key, env_map in _AUX_TASK_ENV.items():
            task_cfg = auxiliary_cfg.get(task_key, {})
            if not isinstance(task_cfg, dict):
                continue
            provider = str(task_cfg.get("provider", "") or "").strip()
            model = str(task_cfg.get("model", "") or "").strip()
            base_url = str(task_cfg.get("base_url", "") or "").strip()
            api_key = str(task_cfg.get("api_key", "") or "").strip()
            if provider and provider != "auto":
                os.environ[env_map["provider"]] = provider
            if model:
                os.environ[env_map["model"]] = model
            if base_url:
                os.environ[env_map["base_url"]] = base_url
            if api_key:
                os.environ[env_map["api_key"]] = api_key

    agent_cfg = cfg.get("agent", {})
    if isinstance(agent_cfg, dict):
        if "max_turns" in agent_cfg:
            os.environ["HERMES_MAX_ITERATIONS"] = str(agent_cfg["max_turns"])
        # Env var from .env takes precedence where noted.
        if "gateway_timeout" in agent_cfg and "HERMES_AGENT_TIMEOUT" not in os.environ:
            os.environ["HERMES_AGENT_TIMEOUT"] = str(agent_cfg["gateway_timeout"])
        if "gateway_timeout_warning" in agent_cfg and "HERMES_AGENT_TIMEOUT_WARNING" not in os.environ:
            os.environ["HERMES_AGENT_TIMEOUT_WARNING"] = str(agent_cfg["gateway_timeout_warning"])
        if "gateway_notify_interval" in agent_cfg and "HERMES_AGENT_NOTIFY_INTERVAL" not in os.environ:
            os.environ["HERMES_AGENT_NOTIFY_INTERVAL"] = str(agent_cfg["gateway_notify_interval"])
        if "restart_drain_timeout" in agent_cfg and "HERMES_RESTART_DRAIN_TIMEOUT" not in os.environ:
            os.environ["HERMES_RESTART_DRAIN_TIMEOUT"] = str(agent_cfg["restart_drain_timeout"])

    display_cfg = cfg.get("display", {})
    if isinstance(display_cfg, dict):
        if "busy_input_mode" in display_cfg and "HERMES_GATEWAY_BUSY_INPUT_MODE" not in os.environ:
            os.environ["HERMES_GATEWAY_BUSY_INPUT_MODE"] = str(display_cfg["busy_input_mode"])

    # Timezone: bridge config.yaml → HERMES_TIMEZONE env var.
    # HERMES_TIMEZONE from .env takes precedence (already in os.environ).
    tz_cfg = cfg.get("timezone", "")
    if tz_cfg and isinstance(tz_cfg, str) and "HERMES_TIMEZONE" not in os.environ:
        os.environ["HERMES_TIMEZONE"] = tz_cfg.strip()

    security_cfg = cfg.get("security", {})
    if isinstance(security_cfg, dict):
        redact = security_cfg.get("redact_secrets")
        if redact is not None:
            os.environ["HERMES_REDACT_SECRETS"] = str(redact).lower()


__all__ = [
    "apply_gateway_startup_env_bridge",
    "load_gateway_startup_bridge_config",
]
