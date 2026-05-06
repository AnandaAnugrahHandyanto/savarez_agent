"""
Obsidian memory plugin — mirrors Hermes built-in memory to an Obsidian vault.

Writes memory entries as Markdown notes in the vault's Memory/ folder, creates
daily session logs, and surfaces vault context on session start.

Config via environment variables (set in ~/.hermes/.env):
  OBSIDIAN_VAULT_PATH — Path to the Obsidian vault root directory

Vault layout:
  Memory/MEMORY.md        — Mirror of built-in memory store
  Memory/USER.md          — Mirror of built-in user profile
  Memory/daily/           — Per-session daily notes (YYYY-MM-DD.md)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


def _env_value(name: str, default: str = "") -> str:
    """Read from process env, then from ~/.hermes/.env for CLI entrypoints."""
    value = os.getenv(name, "").strip()
    if value:
        return value

    env_file = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))) / ".env"
    if not env_file.exists():
        return default
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            if key.strip() == name:
                return raw.strip().strip('"').strip("'")
    except OSError:
        return default
    return default


class ObsidianMemoryProvider(MemoryProvider):
    """Mirrors Hermes memory to an Obsidian vault."""

    def __init__(self) -> None:
        self._vault_path: Optional[Path] = None
        self._memory_dir: Optional[Path] = None
        self._daily_dir: Optional[Path] = None
        self._session_id: str = ""
        self._session_start: Optional[datetime] = None
        # Turn-based self-review counters
        self._turn_count: int = 0
        self._tool_call_count: int = 0
        self._last_user_review: int = 0
        self._last_skill_review: int = 0
        self._pending_insights: List[str] = []

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "obsidian"

    def is_available(self) -> bool:
        """Check if the vault exists and is writable."""
        vault = _env_value("OBSIDIAN_VAULT_PATH")
        if not vault:
            logger.debug("OBSIDIAN_VAULT_PATH not set")
            return False
        path = Path(vault)
        if not path.is_dir():
            logger.debug("Obsidian vault not found at %s", path)
            return False
        if not os.access(path, os.W_OK):
            logger.debug("Obsidian vault not writable at %s", path)
            return False
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        vault = _env_value("OBSIDIAN_VAULT_PATH")
        self._vault_path = Path(vault)
        self._memory_dir = self._vault_path / "Memory"
        self._daily_dir = self._memory_dir / "daily"
        self._session_id = session_id
        self._session_start = datetime.now(timezone.utc)

        self._memory_dir.mkdir(exist_ok=True)
        self._daily_dir.mkdir(exist_ok=True)

        # Ensure the MEMORY.md and USER.md mirror files exist in vault
        for name in ("MEMORY.md", "USER.md"):
            vault_file = self._memory_dir / name
            if not vault_file.exists():
                vault_file.write_text("")

        logger.info(
            "Obsidian memory provider initialized — vault: %s, session: %s",
            self._vault_path, session_id,
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """No additional tools — mirrors the built-in memory tool."""
        return []

    def shutdown(self) -> None:
        """Write session summary to daily note."""
        if self._daily_dir and self._session_start:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            daily = self._daily_dir / f"{today}.md"
            end_time = datetime.now(timezone.utc).strftime("%H:%M UTC")
            entry = (
                f"\n## Session {self._session_id[:8]}\n"
                f"- **Start**: {self._session_start.strftime('%H:%M UTC')}\n"
                f"- **End**: {end_time}\n"
                f"\n"
            )
            try:
                with open(daily, "a") as f:
                    f.write(entry)
            except OSError as e:
                logger.debug("Failed to write daily note: %s", e)
        logger.debug("Obsidian memory provider shut down")

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        """Count turns and trigger periodic self-reviews."""
        self._turn_count = turn_number
        tool_count = kwargs.get("tool_count", 0)
        self._tool_call_count += tool_count

        # Collect potential insight from user message
        if len(message) > 20 and len(message) < 500:
            self._pending_insights.append(message.strip()[:200])

        # Every 10 user turns — write a USER.md review note
        if turn_number - self._last_user_review >= 10:
            self._write_user_review_note()
            self._last_user_review = turn_number

        # Every 15 tool iterations — note skills that might need updating
        if self._tool_call_count - self._last_skill_review >= 15:
            self._write_skill_review_note()
            self._last_skill_review = self._tool_call_count

    def _write_user_review_note(self) -> None:
        """Append a review prompt to the daily note for the nightly audit."""
        if not self._daily_dir:
            return
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self._daily_dir / f"{today}.md"
        note = (
            f"\n> 🔄 **Self-review trigger** (turn {self._turn_count}): "
            f"Review recent exchanges for new user preferences, corrections, "
            f"or patterns that should be reflected in Memory/USER.md.\n"
        )
        try:
            with open(daily, "a") as f:
                f.write(note)
        except OSError:
            pass

    def _write_skill_review_note(self) -> None:
        """Note that skills may need updating based on recent tool usage."""
        if not self._daily_dir:
            return
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self._daily_dir / f"{today}.md"
        note = (
            f"\n> 🛠️ **Skill review trigger** (tool call {self._tool_call_count}): "
            f"Check if any skills need updating based on recent tool interactions.\n"
        )
        try:
            with open(daily, "a") as f:
                f.write(note)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def system_prompt_block(self) -> str:
        """Tell the agent the vault is available."""
        if not self._vault_path:
            return ""
        return (
            "Obsidian vault is active. Memory writes are persisted to the vault. "
            "You can read vault notes with read_file or search_files by prefixing "
            f"the vault path ({self._memory_dir})."
        )

    # ------------------------------------------------------------------
    # Context prefetch
    # ------------------------------------------------------------------

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return recent daily notes and any available context."""
        if not self._daily_dir:
            return ""

        parts = []
        # Include today's daily note if it exists
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_today = self._daily_dir / f"{today}.md"
        if daily_today.exists():
            try:
                content = daily_today.read_text()
                if content.strip():
                    # Take last ~500 chars to keep it compact
                    recent = content[-500:] if len(content) > 500 else content
                    parts.append(f"Today's vault activity ({today}):\n{recent}")
            except OSError:
                pass

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Memory write mirroring — the core feature
    # ------------------------------------------------------------------

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to vault files."""
        if not self._memory_dir:
            return

        filename = "MEMORY.md" if target == "memory" else "USER.md"
        vault_file = self._memory_dir / filename

        try:
            if action == "add":
                # Append the new entry
                current = vault_file.read_text() if vault_file.exists() else ""
                entry = f"{content}\n"
                vault_file.write_text((current + entry).strip() + "\n")

            elif action == "replace":
                old_text = (metadata or {}).get("old_text", "")
                current = vault_file.read_text() if vault_file.exists() else ""
                if old_text and old_text in current:
                    vault_file.write_text(current.replace(old_text, content))
                else:
                    # Fallback: just append if old_text not found
                    vault_file.write_text((current + f"\n{content}").strip() + "\n")

            elif action == "remove":
                old_text = (metadata or {}).get("old_text", "")
                current = vault_file.read_text() if vault_file.exists() else ""
                if old_text and old_text in current:
                    vault_file.write_text(current.replace(old_text, "").strip() + "\n")

        except OSError as e:
            logger.debug("Obsidian mirror write failed for %s: %s", filename, e)

    # ------------------------------------------------------------------
    # Session end — write daily log entry
    # ------------------------------------------------------------------

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Write a session summary to the daily note."""
        if not self._daily_dir or not self._session_start:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self._daily_dir / f"{today}.md"

        end_time = datetime.now(timezone.utc)
        duration = end_time - self._session_start
        mins = int(duration.total_seconds() / 60)

        # Count turns (user messages) and tool calls
        user_turns = sum(1 for m in messages if m.get("role") == "user")
        tool_calls = sum(1 for m in messages if m.get("role") == "tool")

        entry = (
            f"\n### Session {self._session_id[:12]}\n"
            f"- **Duration**: {mins} min\n"
            f"- **Exchanges**: {user_turns} user turns\n"
            f"- **Tool calls**: {tool_calls}\n"
            f"- **Ended**: {end_time.strftime('%H:%M UTC')}\n"
        )

        # Extract key topics from user messages
        topics = []
        for m in messages:
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                content = m["content"]
                if len(content) < 100 and content.strip():
                    topics.append(content.strip()[:80])
        if topics:
            entry += "- **Topics**:\n"
            for t in topics[-5:]:  # Last 5 topics
                entry += f"  - {t}\n"

        try:
            with open(daily, "a") as f:
                f.write(entry)
        except OSError as e:
            logger.debug("Failed to write session-end daily note: %s", e)
