"""Gateway sandbox configuration helpers."""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_VALID_BACKENDS: frozenset = frozenset(
    {"local", "docker", "modal", "daytona", "ssh", "singularity"}
)


def get_gateway_terminal_backend(config: dict) -> Optional[str]:
    """Return the gateway-level terminal backend override, or None if not set."""
    return config.get("gateway", {}).get("terminal_backend")


def get_gateway_sandbox_lifetime(config: dict) -> int:
    """Return sandbox session lifetime in seconds (default 3600)."""
    return config.get("gateway", {}).get("sandbox_lifetime", 3600)


def should_warn_insecure_gateway(config: dict) -> bool:
    """True if gateway is running with local backend and no gateway override."""
    terminal_backend = config.get("terminal", {}).get("backend", "local")
    gateway_backend = get_gateway_terminal_backend(config)
    return terminal_backend == "local" and not gateway_backend


def apply_gateway_backend_to_env(config: dict) -> None:
    """Set TERMINAL_ENV to gateway.terminal_backend if configured."""
    backend = get_gateway_terminal_backend(config)
    if not backend:
        return
    if backend not in _VALID_BACKENDS:
        logger.warning(
            "Unknown gateway.terminal_backend %r — ignoring. Valid values: %s",
            backend,
            ", ".join(sorted(_VALID_BACKENDS)),
        )
        return
    os.environ["TERMINAL_ENV"] = backend
    image = config.get("gateway", {}).get("sandbox_image") or config.get(
        "terminal", {}
    ).get("docker_image", "nikolaik/python-nodejs:python3.11-nodejs20")
    os.environ.setdefault("TERMINAL_DOCKER_IMAGE", image)
    logger.info(
        "Gateway terminal backend override: %s (image: %s)", backend, image
    )
