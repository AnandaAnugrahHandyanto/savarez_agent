"""Unit tests for MCP stdio lifecycle helpers (TaskGroup bootstrap, backoff, coalescing)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from hermes_mcp.parallel_bootstrap import run_parallel_mcp_discovery
from hermes_mcp.stdio_lifecycle import (
    ToolListChangeCoalescer,
    ascii_safe_for_logs,
    list_tools_with_backoff,
)


@pytest.mark.asyncio
async def test_ascii_safe_for_logs_unicode_and_paths() -> None:
    raw = "tool-\u4e2d\u6587-\\mnt\\wsl$\u516c\u5171\\share"
    out = ascii_safe_for_logs(raw)
    assert out.isascii()
    assert "?" in out or "share" in out


@pytest.mark.asyncio
async def test_list_tools_with_backoff_retries_then_ok() -> None:
    log = logging.getLogger("test_mcp_lifecycle")
    log.setLevel(logging.DEBUG)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("stall")
        return type("R", (), {"tools": []})()

    r = await list_tools_with_backoff(
        flaky,
        op_timeout=0.2,
        max_attempts=5,
        base_backoff=0.01,
        max_backoff=0.05,
        log=log,
        server_name="srv",
    )
    assert hasattr(r, "tools")
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_tool_list_change_coalescer_merges_bursts() -> None:
    log = logging.getLogger("test_mcp_coalesce")
    refreshes = []

    async def refresh():
        refreshes.append(asyncio.get_event_loop().time())

    co = ToolListChangeCoalescer(0.05, refresh, log)
    for _ in range(12):
        await co.signal()
    await asyncio.sleep(0.2)
    assert len(refreshes) == 1
    co.cancel()


@pytest.mark.asyncio
async def test_run_parallel_mcp_discovery_isolation() -> None:
    log = logging.getLogger("test_mcp_tg")

    async def discover(name: str, cfg: dict) -> str:
        if name == "bad":
            raise ValueError("boom")
        await asyncio.sleep(0.01)
        return f"ok-{name}"

    servers = {f"s{i}": {} for i in range(12)}
    servers["bad"] = {}
    out = await run_parallel_mcp_discovery(
        servers,
        discover,
        default_connect_timeout=0.5,
        log=log,
        outer_slack=1.0,
    )
    assert len(out) == 13
    assert isinstance(out["bad"][1], ValueError)
    assert out["s0"][1] == "ok-s0"
