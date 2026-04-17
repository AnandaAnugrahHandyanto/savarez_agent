"""Parallel MCP server bootstrap using ``asyncio.TaskGroup`` and per-server timeouts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Tuple


async def run_parallel_mcp_discovery(
    servers: Dict[str, dict],
    discover_one: Callable[[str, dict], Awaitable[T]],
    *,
    default_connect_timeout: float,
    log: logging.Logger,
    outer_slack: float = 8.0,
) -> Dict[str, Tuple[str, Any]]:
    """Start one guarded task per server; return mapping name -> (name, result|exc).

    Inner coroutines never raise into the ``TaskGroup``; failures are captured
    as values so a single bad server cannot cancel healthy peers.
    """
    log.debug("MCP TaskGroup discovery starting (%d server(s))", len(servers))
    results: Dict[str, Tuple[str, Any]] = {}
    lock = asyncio.Lock()

    async def guarded(name: str, cfg: dict) -> None:
        cap = float(cfg.get("connect_timeout", default_connect_timeout)) + outer_slack
        try:
            out = await asyncio.wait_for(discover_one(name, cfg), timeout=cap)
            payload: Any = out
        except Exception as exc:
            payload = exc
        async with lock:
            results[name] = (name, payload)

    async with asyncio.TaskGroup() as tg:
        for name, cfg in servers.items():
            tg.create_task(guarded(name, cfg), name=f"mcp-discover-{name}")
    return results
