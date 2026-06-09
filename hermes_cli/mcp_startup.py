"""Shared CLI/TUI-safe helpers for background MCP discovery."""

from __future__ import annotations

import os
import threading
from typing import Optional

_mcp_discovery_lock = threading.Lock()
_mcp_discovery_started = False
_mcp_discovery_thread: Optional[threading.Thread] = None


def _has_configured_mcp_servers() -> bool:
    """Cheap config probe so non-MCP users avoid importing the MCP stack."""
    try:
        from hermes_cli.config import read_raw_config

        mcp_servers = (read_raw_config() or {}).get("mcp_servers")
        return isinstance(mcp_servers, dict) and len(mcp_servers) > 0
    except Exception:
        # Be conservative: if config probing fails, try discovery in the
        # background so startup still can't block.
        return True


def start_background_mcp_discovery(*, logger, thread_name: str) -> None:
    """Spawn one shared background MCP discovery thread for this process."""
    global _mcp_discovery_started, _mcp_discovery_thread

    with _mcp_discovery_lock:
        if _mcp_discovery_started:
            return
        _mcp_discovery_started = True
        if not _has_configured_mcp_servers():
            return

        def _discover() -> None:
            try:
                from tools.mcp_tool import discover_mcp_tools

                discover_mcp_tools()
            except Exception:
                logger.debug("Background MCP tool discovery failed", exc_info=True)

        thread = threading.Thread(
            target=_discover,
            name=thread_name,
            daemon=True,
        )
        _mcp_discovery_thread = thread
        thread.start()


def wait_for_mcp_discovery(timeout: float | None = None) -> None:
    """Briefly wait for background MCP discovery before the first tool snapshot.

    Timeout resolution order:
      1. Explicit ``timeout`` argument (callers like CLI can override)
      2. ``HERMES_MCP_DISCOVERY_TIMEOUT`` env var (seconds, user-tunable)
      3. Default 0.75s (original fast-start heuristic)
    """
    if timeout is None:
        try:
            timeout = float(os.environ.get("HERMES_MCP_DISCOVERY_TIMEOUT", "0.75"))
        except (TypeError, ValueError):
            timeout = 0.75
    thread = _mcp_discovery_thread
    if thread is None or not thread.is_alive():
        return
    thread.join(timeout=timeout)
