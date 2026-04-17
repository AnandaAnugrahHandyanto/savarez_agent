"""Stdio MCP lifecycle helpers: ASCII-safe logs, list_tools backoff, notify coalescing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Optional, TypeVar

T = TypeVar("T")

_DEFAULT_LIST_TOOLS_ATTEMPTS = 5
_DEFAULT_BASE_BACKOFF = 0.25
_DEFAULT_MAX_BACKOFF = 30.0


def ascii_safe_for_logs(text: str, max_len: int = 4096) -> str:
    """Encode log text as ASCII (unknown chars -> '?'), aligned with conservative disk logs."""
    if not isinstance(text, str):
        text = str(text)
    safe = text.encode("ascii", "replace").decode("ascii")
    if len(safe) > max_len:
        return safe[: max_len - 3] + "..."
    return safe


async def list_tools_with_backoff(
    list_coro: Callable[[], Awaitable[T]],
    *,
    op_timeout: float,
    max_attempts: int = _DEFAULT_LIST_TOOLS_ATTEMPTS,
    base_backoff: float = _DEFAULT_BASE_BACKOFF,
    max_backoff: float = _DEFAULT_MAX_BACKOFF,
    log: logging.Logger,
    server_name: str,
) -> T:
    """Run ``list_tools``-style coroutine with per-attempt timeout and exponential backoff."""
    delay = base_backoff
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.wait_for(list_coro(), timeout=op_timeout)
        except TimeoutError as exc:
            last_exc = exc
            log.warning(
                "MCP server '%s': list_tools timed out (attempt %d/%d, next backoff %.2fs)",
                ascii_safe_for_logs(server_name),
                attempt,
                max_attempts,
                delay,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_exc = exc
            log.warning(
                "MCP server '%s': list_tools %s (attempt %d/%d, next backoff %.2fs): %s",
                ascii_safe_for_logs(server_name),
                type(exc).__name__,
                attempt,
                max_attempts,
                delay,
                ascii_safe_for_logs(str(exc)),
            )
        if attempt == max_attempts:
            assert last_exc is not None
            raise last_exc
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_backoff)
    raise RuntimeError("list_tools_with_backoff: unreachable")


class ToolListChangeCoalescer:
    """Coalesce ``tools/list_changed`` bursts into one refresh after a quiet window."""

    __slots__ = ("_debounce_s", "_refresh", "_log", "_gen", "_runner")

    def __init__(
        self,
        debounce_s: float,
        refresh: Callable[[], Awaitable[None]],
        log: logging.Logger,
    ) -> None:
        self._debounce_s = debounce_s
        self._refresh = refresh
        self._log = log
        self._gen = 0
        self._runner: Optional[asyncio.Task] = None

    def cancel(self) -> None:
        if self._runner and not self._runner.done():
            self._runner.cancel()

    async def signal(self) -> None:
        self._gen += 1
        if self._runner is not None and not self._runner.done():
            return
        self._runner = asyncio.create_task(self._coalesced_loop(), name="mcp-tool-list-coalesce")

    async def _coalesced_loop(self) -> None:
        try:
            while True:
                seen = self._gen
                await asyncio.sleep(self._debounce_s)
                if self._gen == seen:
                    await self._refresh()
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("MCP coalesced tool-list refresh failed")
        finally:
            self._runner = None
