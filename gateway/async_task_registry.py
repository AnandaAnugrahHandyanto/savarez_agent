"""
AsyncTaskRegistry -- Fire-and-Forget Inter-Profile Task Management

Tracks async subprocess tasks launched via the async_task tool.
When a subprocess completes, the registry injects the result
into the originating chat via the gateway adapter, exactly like
_run_background_task does for /background commands.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class AsyncTaskEntry:
    """Represents a single async inter-profile task."""

    def __init__(
        self,
        task_id: str,
        profile: str,
        prompt: str,
        source: Any,  # SessionSource
        process: Any,  # subprocess.Popen
        timeout_seconds: int = 600,
    ):
        self.task_id = task_id
        self.profile = profile
        self.prompt = prompt
        self.source = source
        self.process = process
        self.status = "running"
        self.started_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.timeout_seconds = timeout_seconds

    @property
    def duration_str(self) -> str:
        end = self.completed_at or datetime.now()
        delta = end - self.started_at
        total = int(delta.total_seconds())
        m, s = divmod(total, 60)
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    @property
    def is_timed_out(self) -> bool:
        elapsed = (datetime.now() - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds


class AsyncTaskRegistry:
    """
    Thread-safe registry (asyncio.Lock) for async inter-profile tasks.

    Usage:
        registry = AsyncTaskRegistry(gateway)
        task_id = await registry.register(profile, prompt, source, process)
        # ... watcher loop calls registry.check_and_complete(task_id, result)
    """

    def __init__(self, gateway: Any = None):
        self._lock = asyncio.Lock()
        self._tasks: Dict[str, AsyncTaskEntry] = {}
        self._gateway = gateway  # HermesGateway reference, set after construction

    def set_gateway(self, gateway: Any) -> None:
        self._gateway = gateway

    async def register(
        self,
        task_id: str,
        profile: str,
        prompt: str,
        source: Any,
        process: Any,
    ) -> str:
        """Register a new async task. Returns task_id."""
        async with self._lock:
            entry = AsyncTaskEntry(
                task_id=task_id,
                profile=profile,
                prompt=prompt,
                source=source,
                process=process,
            )
            self._tasks[task_id] = entry
            logger.info(
                "AsyncTask registered: %s [profile=%s] for chat=%s",
                task_id, profile, getattr(source, "chat_id", "?"),
            )
        return task_id

    async def list_active(self) -> list:
        """Return list of active (running) task entries."""
        async with self._lock:
            return [
                entry for entry in self._tasks.values()
                if entry.status == "running"
            ]

    async def list_all(self) -> list:
        """Return all task entries (active + completed)."""
        async with self._lock:
            return list(self._tasks.values())

    async def get(self, task_id: str) -> Optional[AsyncTaskEntry]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def complete(self, task_id: str, result: str, error: bool = False) -> None:
        """Mark task complete and inject result into originating chat."""
        async with self._lock:
            entry = self._tasks.get(task_id)
            if not entry:
                logger.warning("AsyncTask complete called for unknown task_id: %s", task_id)
                return
            entry.status = "error" if error else "done"
            entry.completed_at = datetime.now()

        await self._deliver_result(entry, result, error=error)

    async def _deliver_result(
        self, entry: AsyncTaskEntry, result: str, error: bool = False
    ) -> None:
        """Send result message into the originating chat."""
        if not self._gateway:
            logger.error("AsyncTaskRegistry has no gateway reference — cannot deliver result")
            return

        adapter = self._gateway.adapters.get(entry.source.platform)
        if not adapter:
            logger.warning(
                "No adapter for platform %s — cannot deliver async task result %s",
                entry.source.platform, entry.task_id,
            )
            return

        _thread_metadata = (
            {"thread_id": entry.source.thread_id}
            if getattr(entry.source, "thread_id", None)
            else None
        )

        preview = entry.prompt[:60] + ("..." if len(entry.prompt) > 60 else "")

        if error:
            header = (
                f"❌ Async task fallito [profile: {entry.profile}]\n"
                f'Task ID: {entry.task_id}\n'
                f'Durata: {entry.duration_str}\n'
                f'Prompt: "{preview}"\n\n'
            )
        else:
            header = (
                f"✅ Async task completato [profile: {entry.profile}]\n"
                f"Task ID: {entry.task_id}\n"
                f"Durata: {entry.duration_str}\n\n"
            )

        try:
            await adapter.send(
                chat_id=entry.source.chat_id,
                content=header + result,
                metadata=_thread_metadata,
            )
        except Exception as exc:
            logger.exception(
                "Failed to deliver async task result %s: %s", entry.task_id, exc
            )

    async def cleanup_old(self, max_age_hours: int = 1) -> int:
        """Remove completed tasks older than max_age_hours. Returns count removed."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = 0
        async with self._lock:
            stale = [
                tid for tid, entry in self._tasks.items()
                if entry.status in ("done", "error", "timeout")
                and entry.completed_at
                and entry.completed_at < cutoff
            ]
            for tid in stale:
                del self._tasks[tid]
                removed += 1
        if removed:
            logger.debug("AsyncTaskRegistry cleanup: removed %d old tasks", removed)
        return removed


# Module-level singleton — populated by HermesGateway.start()
async_task_registry = AsyncTaskRegistry()
