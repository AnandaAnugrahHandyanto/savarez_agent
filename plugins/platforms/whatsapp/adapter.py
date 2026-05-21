"""Plugin-owned WhatsApp override seam.

This spike intentionally stays narrow:
- registers the canonical ``whatsapp`` platform as a plugin override
- delegates runtime behavior to the existing built-in adapter
- exposes an explicit local bridge verification path for ``/health``

It does not broaden WhatsApp logging, message modeling, or storage.
"""

from __future__ import annotations

from typing import Any

from gateway.platforms.whatsapp import (
    WhatsAppAdapter as BuiltinWhatsAppAdapter,
    check_whatsapp_requirements,
)

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 3000


def _bridge_port_from_config(config: Any) -> int:
    extra = getattr(config, "extra", {}) or {}
    raw_port = extra.get("bridge_port", DEFAULT_BRIDGE_PORT)
    try:
        return int(raw_port)
    except (TypeError, ValueError):
        return DEFAULT_BRIDGE_PORT


def bridge_base_url(config: Any = None) -> str:
    """Return the canonical local WhatsApp bridge base URL."""
    return f"http://{DEFAULT_BRIDGE_HOST}:{_bridge_port_from_config(config)}"


def bridge_health_url(config: Any = None) -> str:
    """Return the concrete local bridge health endpoint."""
    return f"{bridge_base_url(config)}/health"


def local_bridge_healthcheck_command(config: Any = None) -> str:
    """Return the founder-visible manual health probe command."""
    return f"curl {bridge_health_url(config)}"


class WhatsAppPluginAdapter(BuiltinWhatsAppAdapter):
    """Thin plugin wrapper around the built-in WhatsApp adapter."""

    def __init__(self, config: Any):
        super().__init__(config)
        self._plugin_bridge_health_url = bridge_health_url(config)

    @property
    def plugin_bridge_health_url(self) -> str:
        return self._plugin_bridge_health_url


def register(ctx) -> None:
    """Register the plugin-owned WhatsApp override."""
    ctx.register_platform(
        name="whatsapp",
        label="WhatsApp",
        adapter_factory=lambda cfg: WhatsAppPluginAdapter(cfg),
        check_fn=check_whatsapp_requirements,
        emoji="💬",
        allow_update_command=True,
        platform_hint=(
            "You are chatting via WhatsApp. Keep replies concise, mobile-friendly, "
            "and aware that the local bridge health endpoint is "
            f"{bridge_health_url()}."
        ),
    )
