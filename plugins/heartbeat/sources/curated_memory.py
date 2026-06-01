"""Read-only curated built-in memory Heartbeat source."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from ..models import SourceObservation


def collect_curated_memory(config: Dict[str, Any]) -> SourceObservation:
    now = datetime.now(timezone.utc).isoformat()
    max_chars = int(config.get("max_chars", 6000))
    try:
        from tools.memory_tool import MemoryStore

        store = MemoryStore(memory_char_limit=max_chars, user_char_limit=max_chars)
        store.load_from_disk()
        text = "\n\n".join(
            part
            for part in (
                store.format_for_system_prompt("memory"),
                store.format_for_system_prompt("user"),
            )
            if part
        )
        truncated = len(text) > max_chars
        text = text[:max_chars]
        return SourceObservation(
            source="curated_memory",
            collected_at=now,
            summary=text or "No curated memory entries.",
            truncated=truncated,
        )
    except Exception as exc:
        return SourceObservation(
            source="curated_memory",
            collected_at=now,
            summary="Curated memory source unavailable.",
            error=str(exc),
        )
