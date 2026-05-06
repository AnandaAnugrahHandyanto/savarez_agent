"""Obsidian Layer 3 memory provider.

Local filesystem-backed memory provider for Danny's Obsidian vault.  It keeps
large, on-demand operational context outside the tiny built-in memory prompt and
writes disciplined breadcrumbs for session/task start, tool checkpoints,
compaction, and session end.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

_SHARED_NOTES = (
    "Agent-Shared/user-profile.md",
    "Agent-Shared/project-state.md",
    "Agent-Shared/decisions-log.md",
)


def _now() -> datetime:
    return datetime.now().astimezone()


class ObsidianMemoryProvider(MemoryProvider):
    """Filesystem-backed Layer 3 memory provider for an Obsidian vault."""

    name = "obsidian"

    def __init__(self) -> None:
        self.vault_path: Optional[Path] = None
        self.hermes_home: Optional[Path] = None
        self.session_id = ""
        self.platform = ""
        self.agent_identity = "eva"
        self.agent_folder = "Agent-Eva"
        self.read_char_limit = 2500
        self.checkpoint_every = 4
        self._tool_count = 0
        self._turn_count = 0
        self._last_query = ""
        self._session_started = False

    # -- Discovery ---------------------------------------------------------
    def _resolve_vault_path(self) -> Optional[Path]:
        env = (os.environ.get("OBSIDIAN_VAULT_PATH") or "").strip()
        candidates: list[Path] = []
        if env:
            candidates.append(Path(env).expanduser())

        # Profile/global .env fallback in case env was not exported.
        homes = []
        if self.hermes_home:
            homes.append(self.hermes_home)
        homes.append(Path.home() / ".hermes")
        for home in homes:
            env_file = home / ".env"
            if not env_file.exists():
                continue
            try:
                for line in env_file.read_text(errors="ignore").splitlines():
                    if line.startswith("OBSIDIAN_VAULT_PATH="):
                        value = line.split("=", 1)[1].strip().strip('"\'')
                        if value:
                            candidates.append(Path(value).expanduser())
            except Exception:
                pass

        # macOS Obsidian config fallback.
        obsidian_cfg = Path.home() / "Library/Application Support/obsidian/obsidian.json"
        if obsidian_cfg.exists():
            try:
                data = json.loads(obsidian_cfg.read_text(errors="ignore"))
                for vault in (data.get("vaults") or {}).values():
                    p = vault.get("path") if isinstance(vault, dict) else None
                    if p:
                        candidates.append(Path(p).expanduser())
            except Exception:
                pass

        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_dir() and (
                    (candidate / "VAULT-INDEX.md").exists()
                    or any(candidate.glob("*.md"))
                    or (candidate / "Agent-Shared").exists()
                ):
                    return candidate
            except Exception:
                continue
        return None

    def _agent_folder_for_identity(self, identity: str) -> str:
        ident = (identity or "").strip().lower()
        if ident == "eva":
            return "Agent-Eva"
        if ident in {"hermes", "default"}:
            return "Agent-Hermes"
        # Keep unknown Hermes profiles out of other agents' lanes.
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", identity or "Hermes").strip("-") or "Hermes"
        return f"Agent-{safe}"

    # -- Required MemoryProvider API --------------------------------------
    def is_available(self) -> bool:
        return self._resolve_vault_path() is not None

    def initialize(self, session_id: str, **kwargs) -> None:
        self.session_id = session_id or ""
        self.hermes_home = Path(kwargs.get("hermes_home") or os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
        self.platform = kwargs.get("platform") or ""
        self.agent_identity = kwargs.get("agent_identity") or "eva"
        self.agent_folder = self._agent_folder_for_identity(self.agent_identity)
        config = kwargs.get("config") or {}
        memory_cfg = config.get("memory", {}) if isinstance(config, dict) else {}
        self.read_char_limit = int(memory_cfg.get("obsidian_read_char_limit") or 2500)
        self.checkpoint_every = int(memory_cfg.get("obsidian_checkpoint_tool_calls") or 4)
        self.vault_path = self._resolve_vault_path()
        if not self.vault_path:
            raise RuntimeError("Obsidian vault not found; set OBSIDIAN_VAULT_PATH")
        self._ensure_lane()
        self._append_daily("session-start", f"Automatic Obsidian provider initialized for `{self.agent_identity}` on `{self.platform}`; session `{self.session_id}`.")
        self._append_working(f"- {_now().strftime('%Y-%m-%d %H:%M')}: Session `{self.session_id}` started on `{self.platform}`; Layer 3 provider active.")
        self._session_started = True

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def system_prompt_block(self) -> str:
        if not self.vault_path:
            return ""
        return f"""## Obsidian Layer 3 Memory
- Active vault: `{self.vault_path}`.
- Memory layers: (1) built-in compact memory, (2) AGENTS.md + SOUL.md rules, (3) Obsidian vault on-demand memory, (4) session_search archive.
- Read Layer 3 at session start, after compaction, and when task details are needed.
- Write task starts, checkpoints every 3-5 substantial tool calls, completions, corrections, and session-end flushes.
- Use `Agent-Shared/` for cross-agent truth and `{self.agent_folder}/` for this profile's tactical state.
- Never write inside `Agent-Aria/`, `Agent-Hermes/`, or `Agent-Cowork/` unless you are that agent/profile.
- Promote durable facts, decisions, and repeatable mistakes into canonical shared notes."""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self.vault_path:
            return ""
        self._last_query = query or ""
        paths = [
            "VAULT-INDEX.md",
            "Agent-Shared/memory-operations.md",
            *_SHARED_NOTES,
            f"{self.agent_folder}/working-context.md",
            f"{self.agent_folder}/daily/{_now().date().isoformat()}.md",
        ]
        parts: list[str] = []
        for rel in paths:
            text = self._read_note(rel)
            if text:
                parts.append(f"### {rel}\n{text}")
        if not parts:
            return ""
        return "## Obsidian Layer 3 recalled context\n" + "\n\n".join(parts)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self.vault_path:
            return
        # Lightweight turn breadcrumb; detailed content stays in session archive.
        if self._turn_count == 1 or self._turn_count % 3 == 0:
            user_preview = self._one_line(user_content, 180)
            assistant_preview = self._one_line(assistant_content, 180)
            self._append_daily("turn-sync", f"User: {user_preview}\n  Assistant: {assistant_preview}")

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        self._turn_count += 1
        if self._turn_count == 1:
            self._append_daily("task-start", self._one_line(message, 300))

    def on_tool_call_complete(self, tool_name: str, args: Dict[str, Any], result: str, **kwargs) -> None:
        if not self.vault_path:
            return
        self._tool_count += 1
        if self._tool_count % max(1, self.checkpoint_every) != 0:
            return
        status = "error" if kwargs.get("is_error") else "ok"
        summary = f"Tool checkpoint #{self._tool_count}: `{tool_name}` {status}; result: {self._one_line(result, 240)}"
        self._append_daily("checkpoint", summary)
        self._append_working(f"- {_now().strftime('%Y-%m-%d %H:%M')}: {summary}")

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        self._append_daily("pre-compaction", "Context compression triggered; re-read Layer 3 vault notes after compaction before continuing.")
        return "After compression, re-read Obsidian Layer 3: VAULT-INDEX, Agent-Shared/memory-operations, current project-state, and active agent working-context/daily note."

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        self._append_daily("session-end", f"Session `{self.session_id}` ended/flushed. Turns observed: {self._turn_count}; tool calls observed: {self._tool_count}.")
        self._append_working(f"- {_now().strftime('%Y-%m-%d %H:%M')}: Session `{self.session_id}` flushed; turns `{self._turn_count}`, tools `{self._tool_count}`.")

    def on_session_switch(self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False, **kwargs) -> None:
        self._append_daily("session-switch", f"Session changed `{parent_session_id}` -> `{new_session_id}`; reset={reset}.")
        self.session_id = new_session_id or self.session_id
        if reset:
            self._tool_count = 0
            self._turn_count = 0

    # -- File helpers ------------------------------------------------------
    def _ensure_lane(self) -> None:
        assert self.vault_path is not None
        for rel in ("Agent-Shared", self.agent_folder, f"{self.agent_folder}/daily"):
            (self.vault_path / rel).mkdir(parents=True, exist_ok=True)
        wc = self.vault_path / self.agent_folder / "working-context.md"
        if not wc.exists():
            wc.write_text(f"# {self.agent_identity.title()} Working Context\n\n## Current State\n", encoding="utf-8")
        mistakes = self.vault_path / self.agent_folder / "mistakes.md"
        if not mistakes.exists():
            mistakes.write_text(f"# {self.agent_identity.title()} Mistakes\n\nRepeatable failure modes to avoid.\n", encoding="utf-8")

    def _read_note(self, rel: str) -> str:
        assert self.vault_path is not None
        path = self.vault_path / rel
        if not path.exists() or not path.is_file():
            return ""
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            return ""
        limit = max(500, int(self.read_char_limit))
        return text[:limit] + ("\n...[truncated]" if len(text) > limit else "")

    def _append_note(self, rel: str, content: str) -> None:
        if not self.vault_path:
            return
        path = self.vault_path / rel
        if "Agent-Aria" in path.parts:
            raise RuntimeError("Refusing to write inside Agent-Aria")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n")

    def _append_daily(self, event: str, text: str) -> None:
        today = _now().date().isoformat()
        rel = f"{self.agent_folder}/daily/{today}.md"
        path = self.vault_path / rel if self.vault_path else None
        if path and not path.exists():
            self._append_note(rel, f"---\ntype: daily\nagent: {self.agent_identity}\ndate: {today}\ntags: [memory-system, {self.agent_identity}, daily]\n---\n\n# {self.agent_identity.title()} Daily - {today}\n")
        self._append_note(rel, f"\n## {_now().strftime('%H:%M')} - {event}\n- {text}")

    def _append_working(self, line: str) -> None:
        self._append_note(f"{self.agent_folder}/working-context.md", line)

    @staticmethod
    def _one_line(value: Any, limit: int) -> str:
        text = str(value or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit] + ("..." if len(text) > limit else "")


def register(ctx) -> None:
    ctx.register_memory_provider(ObsidianMemoryProvider())
