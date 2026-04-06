"""
AsyncTaskRegistry -- Fire-and-Forget Inter-Profile Task Management

Tracks async subprocess tasks launched via the async_task tool.
When a subprocess completes, the registry injects the result
into the originating chat via the gateway adapter, exactly like
_run_background_task does for /background commands.
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
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
    ):
        self.task_id = task_id
        self.profile = profile
        self.prompt = prompt
        self.source = source
        self.process = process
        self.status = "running"
        self.started_at = datetime.now()
        self.completed_at: Optional[datetime] = None

    @property
    def duration_str(self) -> str:
        end = self.completed_at or datetime.now()
        delta = end - self.started_at
        total = int(delta.total_seconds())
        m, s = divmod(total, 60)
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"



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
        # Persist immediately so restart can resume context
        await self.persist()
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

        # Update persisted state — remove completed task
        await self.persist()
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
            content = f"❌ {result}"
        else:
            content = result

        try:
            from gateway.platforms.base import BasePlatformAdapter

            # Extract MEDIA: tags and images from result before sending
            media_files, content = BasePlatformAdapter.extract_media(content)
            images, text_content = BasePlatformAdapter.extract_images(content)

            # Send text if any
            if text_content.strip():
                await adapter.send(
                    chat_id=entry.source.chat_id,
                    content=text_content,
                    metadata=_thread_metadata,
                )
            elif not images and not media_files:
                # No text, no images, no media — send placeholder
                await adapter.send(
                    chat_id=entry.source.chat_id,
                    content="(task completato senza output testuale)",
                    metadata=_thread_metadata,
                )

            # Send images
            for image_url, alt_text in (images or []):
                try:
                    await adapter.send_image(
                        chat_id=entry.source.chat_id,
                        image_url=image_url,
                        caption=alt_text,
                    )
                except Exception:
                    pass

            # Send media files (HTML, PDF, etc.)
            for media_path, _is_voice in (media_files or []):
                try:
                    await adapter.send_document(
                        chat_id=entry.source.chat_id,
                        file_path=media_path,
                    )
                except Exception:
                    pass
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


    def _state_path(self) -> Path:
        """Path to the JSON file that persists active tasks across restarts."""
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home()) / "async_tasks_state.json"

    async def persist(self) -> None:
        """Save active tasks to disk so they survive a gateway restart."""
        async with self._lock:
            data = []
            for entry in self._tasks.values():
                if entry.status != "running":
                    continue
                # We can't persist the process object itself — save enough
                # info to reconstruct the task description on resume.
                src = entry.source
                data.append({
                    "task_id": entry.task_id,
                    "profile": entry.profile,
                    "prompt": entry.prompt,
                    "started_at": entry.started_at.isoformat(),
                    "source_platform": src.platform.value if src else None,
                    "source_chat_id": src.chat_id if src else None,
                    "source_thread_id": getattr(src, "thread_id", None),
                })
        try:
            self._state_path().write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("AsyncTaskRegistry: failed to persist state: %s", exc)

    async def load_persisted(self) -> list:
        """Load tasks persisted from a previous gateway run.

        Returns list of dicts with task info — the processes are gone,
        but the metadata is enough for the boot wakeup message.
        """
        path = self._state_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            # Clear persisted file immediately — tasks won't be restarted automatically,
            # just reported to the user so they can decide what to do.
            path.unlink(missing_ok=True)
            return data
        except Exception as exc:
            logger.warning("AsyncTaskRegistry: failed to load persisted state: %s", exc)
            return []


# Module-level singleton — populated by HermesGateway.start()
async_task_registry = AsyncTaskRegistry()
