"""Obsidian memory provider plugin.

Local file-backed long-form memory sink for Hermes. This provider does not add
model-facing tools; it participates via lifecycle hooks to persist long-form
session artifacts and compression-time summaries into an Obsidian vault.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from agent.obsidian_memory import (
    get_obsidian_vault_path,
    obsidian_vault_exists,
    write_obsidian_downshift_note,
)
from tools.memory_tool import _classify_memory_candidate, _normalize_memory_entry, _truncate_for_index

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "enabled": True,
    "capture_on_pre_compress": True,
    "capture_on_session_end": True,
    "mirror_explicit_memory_writes": False,
}


def _config_path(hermes_home: str) -> Path:
    return Path(hermes_home) / "obsidian_memory.json"


def _load_config(hermes_home: str) -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    path = _config_path(hermes_home)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except Exception:
            logger.debug("Failed to parse %s", path, exc_info=True)
    return cfg


def _save_config(values: dict, hermes_home: str) -> None:
    path = _config_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except Exception:
            existing = {}
    existing.update(values or {})
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _serialize_messages(messages: List[Dict[str, Any]], limit: int = 12000) -> str:
    parts: list[str] = []
    current_len = 0
    for msg in messages:
        role = str(msg.get("role", "unknown")).upper()
        content = msg.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if not content:
            continue
        rendered = f"[{role}] {content}"
        parts.append(rendered)
        current_len += len(rendered)
        if current_len > limit:
            break
    return "\n\n".join(parts)[:limit].rstrip()


class ObsidianMemoryProvider(MemoryProvider):
    def __init__(self):
        self._config = dict(_DEFAULT_CONFIG)
        self._session_id = ""
        self._hermes_home = ""
        self._active = False
        self._captured_precompress = False

    @property
    def name(self) -> str:
        return "obsidian"

    def is_available(self) -> bool:
        return obsidian_vault_exists()

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = str(kwargs.get("hermes_home") or "")
        self._config = _load_config(self._hermes_home) if self._hermes_home else dict(_DEFAULT_CONFIG)
        self._active = bool(self._config.get("enabled", True)) and obsidian_vault_exists()
        self._captured_precompress = False

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        _save_config(values, hermes_home)

    def system_prompt_block(self) -> str:
        if not self._active:
            return ""
        return (
            f"Obsidian long-form memory sink active. Vault: {get_obsidian_vault_path()}\n"
            "Use bounded memory for short facts; long-form evidence can be downshifted into the vault via lifecycle hooks."
        )

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        if not self._active or not self._config.get("capture_on_pre_compress", True) or not messages:
            return ""
        transcript = _serialize_messages(messages)
        if not transcript:
            return ""
        note_result = write_obsidian_downshift_note(
            trigger="pre-compress",
            content=transcript,
            title_hint="context compaction handoff",
            route_reason="conversation context was about to be compacted",
            session_id=self._session_id,
            target="memory",
        )
        self._captured_precompress = bool(note_result.get("success"))
        memory_candidates: list[str] = []
        skill_candidates: list[str] = []
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            normalized, _ = _normalize_memory_entry(content)
            route_hint = _classify_memory_candidate("memory", content)
            if route_hint and route_hint.get("route") == "skill":
                candidate = _truncate_for_index(normalized, limit=120)
                if candidate not in skill_candidates:
                    skill_candidates.append(candidate)
            elif normalized:
                candidate = _truncate_for_index(normalized, limit=120)
                if candidate not in memory_candidates:
                    memory_candidates.append(candidate)
        if note_result.get("success"):
            parts = [
                "Long-form transcript excerpt was downshifted to Obsidian before compaction.",
                "Preserve key durable facts, decisions, files, and next steps in the compressed handoff.",
                f"Obsidian note: {note_result.get('path')}",
            ]
        else:
            parts = [
                "Obsidian pre-compress capture failed; preserve durable facts in the compressed handoff and allow session-end fallback.",
                f"Obsidian error: {note_result.get('error', 'unknown error')}",
            ]
        if memory_candidates:
            parts.append("Memory candidates:\n- " + "\n- ".join(memory_candidates[:5]))
        if skill_candidates:
            parts.append("Skill candidates:\n- " + "\n- ".join(skill_candidates[:5]))
        return "\n\n".join(parts)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._active or not self._config.get("capture_on_session_end", True) or not messages:
            return
        if self._captured_precompress:
            return
        transcript = _serialize_messages(messages)
        if not transcript:
            return
        write_obsidian_downshift_note(
            trigger="session-end",
            content=transcript,
            title_hint="session wrap-up",
            route_reason="session ended with long-form conversational context",
            session_id=self._session_id,
            target="memory",
        )

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if not self._active or not self._config.get("mirror_explicit_memory_writes", False):
            return
        if action not in ("add", "replace") or not content:
            return
        write_obsidian_downshift_note(
            trigger="memory-write",
            content=content,
            title_hint="explicit memory write",
            route_reason="explicit durable write mirrored to Obsidian",
            session_id=self._session_id,
            target=target,
        )


def register(ctx) -> None:
    ctx.register_memory_provider(ObsidianMemoryProvider())
