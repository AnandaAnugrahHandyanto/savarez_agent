"""Kasia-specific status helpers for hermes status."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.request import urlopen

from gateway.kasia_config import DEFAULT_KASIA_BRIDGE_PORT


def fetch_kasia_bridge_health(bridge_port: Optional[int]) -> dict[str, Any] | None:
    """Best-effort bridge health fetch for the local Kasia bridge."""
    port = bridge_port or DEFAULT_KASIA_BRIDGE_PORT
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def kasia_status_lines(kasia_settings, *, health: dict[str, Any] | None = None) -> list[str]:
    """Render operator-facing Kasia detail lines for hermes status."""
    lines: list[str] = []
    if kasia_settings.kns_url:
        lines.append(f"    KNS:        {kasia_settings.kns_url}")
    if kasia_settings.indexer_urls:
        lines.append(f"    Indexers:   {len(kasia_settings.indexer_urls)} configured")
    if kasia_settings.node_wborsh_urls:
        lines.append(f"    Nodes:      {len(kasia_settings.node_wborsh_urls)} configured")
    broadcast_channels = list(kasia_settings.allowed_broadcast_channels)
    if broadcast_channels:
        lines.append(
            "    Broadcasts: publish allowlist for "
            + ", ".join(f"#{channel}" for channel in broadcast_channels)
        )

    active_indexer = (health.get("indexerPool") or {}).get("activeUrl") if health else None
    active_indexer = active_indexer or (health or {}).get("indexerUrl")
    active_node = (health.get("nodePool") or {}).get("activeUrl") if health else None
    active_node = active_node or (health or {}).get("nodeUrl")
    if active_indexer:
        lines.append(f"    Active indexer: {active_indexer}")
    if active_node:
        lines.append(f"    Active node:    {active_node}")
    if (health or {}).get("indexerPool", {}).get("degraded"):
        lines.append("    Indexer pool:   degraded / failover active")
    if (health or {}).get("nodePool", {}).get("degraded"):
        lines.append("    Node pool:      degraded / failover active")
    return lines
