#!/usr/bin/env python3
"""
Memory Tool Module - Persistent Curated Memory

Provides bounded, file-backed memory that persists across sessions. Two stores:
  - MEMORY.md: agent's personal notes and observations (environment facts, project
    conventions, tool quirks, things learned)
  - USER.md: what the agent knows about the user (preferences, communication style,
    expectations, workflow habits)

Both are injected into the system prompt as a frozen snapshot at session start.
Mid-session writes update storage immediately (durable) but do NOT change
the system prompt -- this preserves the prefix cache for the entire session.
The snapshot refreshes on the next session start.

V2: When engine='sqlite' in config, uses MemoryEngine (SQLite + FTS5) as backend.
When engine='flat', uses legacy MEMORY.md/USER.md flat files.
"""

import fcntl
import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Where memory files live
MEMORY_DIR = get_hermes_home() / "memories"

ENTRY_DELIMITER = "\n§\n"


# ---------------------------------------------------------------------------
# Memory content scanning — lightweight check for injection/exfiltration
# in content that gets injected into the system prompt.
# ---------------------------------------------------------------------------

_MEMORY_THREAT_PATTERNS = [
    # Prompt injection
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # Exfiltration via curl/wget with secrets
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets"),
    # Persistence via shell rc
    (r'authorized_keys', "ssh_backdoor"),
    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access"),
    (r'\$HOME/\.hermes/\.env|\~/\.hermes/\.env', "hermes_env"),
]

# Subset of invisible chars for injection detection
_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_memory_content(content: str) -> Optional[str]:
    """Scan memory content for injection/exfil patterns. Returns error string if blocked."""
    # Check invisible unicode
    for char in _INVISIBLE_CHARS:
        if char in content:
            return f"Blocked: content contains invisible unicode character U+{ord(char):04X} (possible injection)."

    # Check threat patterns
    for pattern, pid in _MEMORY_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Blocked: content matches threat pattern '{pid}'. Memory entries are injected into the system prompt and must not contain injection or exfiltration payloads."

    return None


class MemoryStore:
    """
    Bounded curated memory with persistence. One instance per AIAgent.

    When initialized with a MemoryEngine, delegates all storage to SQLite.
    Otherwise falls back to legacy flat-file behavior (MEMORY.md / USER.md).

    Maintains frozen snapshot pattern regardless of backend:
      - Snapshot captured at load time, used for system prompt injection.
      - Never mutated mid-session. Keeps prefix cache stable.
      - Live state mutated by tool calls, persisted immediately.
    """

    def __init__(self, memory_char_limit: int = 2200, user_char_limit: int = 1375,
                 engine=None):
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit

        # V2 engine (optional — None = flat file mode)
        self._engine = engine

        # Flat-file state (only used when _engine is None)
        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []

        # Frozen snapshot for system prompt
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}

    @property
    def engine(self):
        """Access the underlying MemoryEngine (or None for flat mode)."""
        return self._engine

    def load_from_disk(self):
        """Load entries and capture system prompt snapshot.

        SQLite mode: runs migration from flat files if needed, then snapshots.
        Flat mode: reads MEMORY.md / USER.md directly.
        """
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        if self._engine is not None:
            # SQLite mode — migrate flat files on first run, then snapshot
            self._engine.migrate_from_flat_files(memory_dir=MEMORY_DIR)
            self._engine.snapshot()
            self._system_prompt_snapshot = {
                "memory": self._engine.get_snapshot("memory") or "",
                "user": self._engine.get_snapshot("user") or "",
            }
        else:
            # Legacy flat-file mode
            self.memory_entries = self._read_file(MEMORY_DIR / "MEMORY.md")
            self.user_entries = self._read_file(MEMORY_DIR / "USER.md")

            # Deduplicate entries (preserves order, keeps first occurrence)
            self.memory_entries = list(dict.fromkeys(self.memory_entries))
            self.user_entries = list(dict.fromkeys(self.user_entries))

            # Capture frozen snapshot for system prompt injection
            self._system_prompt_snapshot = {
                "memory": self._render_block("memory", self.memory_entries),
                "user": self._render_block("user", self.user_entries),
            }

    # -- Public API (add/replace/remove) -------------------------------------

    def add(self, target: str, content: str, type: str = "general") -> Dict[str, Any]:
        """Append a new entry. Returns error if blocked or duplicate."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        # Scan for injection/exfiltration before accepting
        scan_error = _scan_memory_content(content)
        if scan_error:
            return {"success": False, "error": scan_error}

        if self._engine is not None:
            result = self._engine.add(content, target=target, type=type, source="agent")
            if result["success"]:
                return self._engine_success_response(target, "Entry added.")
            return result

        # --- Legacy flat-file path ---
        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            limit = self._char_limit(target)

            if content in entries:
                return self._success_response(target, "Entry already exists (no duplicate added).")

            new_entries = entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))

            if new_total > limit:
                current = self._char_count(target)
                return {
                    "success": False,
                    "error": (
                        f"Memory at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": entries,
                    "usage": f"{current:,}/{limit:,}",
                }

            entries.append(content)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str, type: str = None) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        scan_error = _scan_memory_content(new_content)
        if scan_error:
            return {"success": False, "error": scan_error}

        if self._engine is not None:
            # Find matching memory by substring
            matches = self._engine_find_by_substring(target, old_text)
            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}
            if len(matches) > 1:
                unique = set(m["content"] for m in matches)
                if len(unique) > 1:
                    previews = [m["content"][:80] + ("..." if len(m["content"]) > 80 else "") for m in matches]
                    return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}

            mem = matches[0]
            result = self._engine.replace(mem["id"], new_content)
            if result["success"]:
                return self._engine_success_response(target, "Entry replaced.")
            return result

        # --- Legacy flat-file path ---
        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}

            idx = matches[0][0]
            limit = self._char_limit(target)

            test_entries = entries.copy()
            test_entries[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test_entries))

            if new_total > limit:
                return {
                    "success": False,
                    "error": (
                        f"Replacement would put memory at {new_total:,}/{limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                }

            entries[idx] = new_content
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove the entry containing old_text substring."""
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}

        if self._engine is not None:
            matches = self._engine_find_by_substring(target, old_text)
            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}
            if len(matches) > 1:
                unique = set(m["content"] for m in matches)
                if len(unique) > 1:
                    previews = [m["content"][:80] + ("..." if len(m["content"]) > 80 else "") for m in matches]
                    return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}

            mem = matches[0]
            result = self._engine.remove(mem["id"])
            if result["success"]:
                return self._engine_success_response(target, "Entry removed.")
            return result

        # --- Legacy flat-file path ---
        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {"success": False, "error": f"Multiple entries matched '{old_text}'. Be more specific.", "matches": previews}

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry removed.")

    def search(self, target: str, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search memories by query. Only available with SQLite engine."""
        if self._engine is None:
            return {"success": False, "error": "Search requires engine='sqlite' in config."}

        results = self._engine.search(query, target=target, limit=limit)
        # Reinforce accessed memories
        for r in results:
            self._engine.reinforce(r["id"])

        return {
            "success": True,
            "target": target,
            "query": query,
            "results": [
                {
                    "id": r["id"][:8],
                    "content": r["content"],
                    "type": r.get("type", "general"),
                    "relevance": r.get("relevance_score", 0),
                    "tier": r.get("tier", "active"),
                    "access_count": r.get("access_count", 0),
                }
                for r in results
            ],
            "count": len(results),
        }

    def format_for_system_prompt(self, target: str) -> Optional[str]:
        """Return the frozen snapshot for system prompt injection.

        Returns the state captured at load_from_disk() time, NOT the live state.
        Returns None if the snapshot is empty.
        """
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # -- Engine helpers (SQLite mode) ----------------------------------------

    def _engine_find_by_substring(self, target: str, substring: str) -> list:
        """Find active memories in engine whose content contains substring."""
        all_mems = self._engine.get_active_memories(target)
        return [m for m in all_mems if substring in m["content"]]

    def _engine_success_response(self, target: str, message: str = None) -> Dict[str, Any]:
        """Build success response compatible with existing format, from engine."""
        memories = self._engine.get_active_memories(target)
        entries = [m["content"] for m in memories]
        total_chars = sum(len(e) for e in entries)
        limit = self._char_limit(target)
        pct = min(100, int((total_chars / limit) * 100)) if limit > 0 else 0

        resp = {
            "success": True,
            "target": target,
            "entries": entries,
            "usage": f"{pct}% — {total_chars:,}/{limit:,} chars",
            "entry_count": len(entries),
        }
        if message:
            resp["message"] = message
        return resp

    # -- Legacy flat-file helpers --------------------------------------------

    @staticmethod
    @contextmanager
    def _file_lock(path: Path):
        """Acquire an exclusive file lock for read-modify-write safety."""
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    @staticmethod
    def _path_for(target: str) -> Path:
        if target == "user":
            return MEMORY_DIR / "USER.md"
        return MEMORY_DIR / "MEMORY.md"

    def _reload_target(self, target: str):
        fresh = self._read_file(self._path_for(target))
        fresh = list(dict.fromkeys(fresh))
        self._set_entries(target, fresh)

    def save_to_disk(self, target: str):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._write_file(self._path_for(target), self._entries_for(target))

    def _entries_for(self, target: str) -> List[str]:
        if target == "user":
            return self.user_entries
        return self.memory_entries

    def _set_entries(self, target: str, entries: List[str]):
        if target == "user":
            self.user_entries = entries
        else:
            self.memory_entries = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        return len(ENTRY_DELIMITER.join(entries))

    def _char_limit(self, target: str) -> int:
        if target == "user":
            return self.user_char_limit
        return self.memory_char_limit

    def _success_response(self, target: str, message: str = None) -> Dict[str, Any]:
        entries = self._entries_for(target)
        current = self._char_count(target)
        limit = self._char_limit(target)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        resp = {
            "success": True,
            "target": target,
            "entries": entries,
            "usage": f"{pct}% — {current:,}/{limit:,} chars",
            "entry_count": len(entries),
        }
        if message:
            resp["message"] = message
        return resp

    def _render_block(self, target: str, entries: List[str]) -> str:
        if not entries:
            return ""

        limit = self._char_limit(target)
        content = ENTRY_DELIMITER.join(entries)
        current = len(content)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        if target == "user":
            header = f"USER PROFILE (who the user is) [{pct}% — {current:,}/{limit:,} chars]"
        else:
            header = f"MEMORY (your personal notes) [{pct}% — {current:,}/{limit:,} chars]"

        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"

    @staticmethod
    def _read_file(path: Path) -> List[str]:
        if not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return []

        if not raw.strip():
            return []

        entries = [e.strip() for e in raw.split(ENTRY_DELIMITER)]
        return [e for e in entries if e]

    @staticmethod
    def _write_file(path: Path, entries: List[str]):
        content = ENTRY_DELIMITER.join(entries) if entries else ""
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=".mem_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, str(path))
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except (OSError, IOError) as e:
            raise RuntimeError(f"Failed to write memory file {path}: {e}")


def memory_tool(
    action: str,
    target: str = "memory",
    content: str = None,
    old_text: str = None,
    type: str = "general",
    search_query: str = None,
    store: Optional[MemoryStore] = None,
) -> str:
    """
    Single entry point for the memory tool. Dispatches to MemoryStore methods.
    Returns JSON string with results.
    """
    if store is None:
        return json.dumps({"success": False, "error": "Memory is not available. It may be disabled in config or this environment."}, ensure_ascii=False)

    if target not in ("memory", "user"):
        return json.dumps({"success": False, "error": f"Invalid target '{target}'. Use 'memory' or 'user'."}, ensure_ascii=False)

    if action == "add":
        if not content:
            return json.dumps({"success": False, "error": "Content is required for 'add' action."}, ensure_ascii=False)
        result = store.add(target, content, type=type)

    elif action == "replace":
        if not old_text:
            return json.dumps({"success": False, "error": "old_text is required for 'replace' action."}, ensure_ascii=False)
        if not content:
            return json.dumps({"success": False, "error": "content is required for 'replace' action."}, ensure_ascii=False)
        result = store.replace(target, old_text, content, type=type)

    elif action == "remove":
        if not old_text:
            return json.dumps({"success": False, "error": "old_text is required for 'remove' action."}, ensure_ascii=False)
        result = store.remove(target, old_text)

    elif action == "search":
        if not search_query:
            return json.dumps({"success": False, "error": "search_query is required for 'search' action."}, ensure_ascii=False)
        result = store.search(target, search_query)

    else:
        return json.dumps({"success": False, "error": f"Unknown action '{action}'. Use: add, replace, remove, search"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


def check_memory_requirements() -> bool:
    """Memory tool has no external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "Save durable information to persistent memory that survives across sessions. "
        "Memory is injected into future turns, so keep it compact and focused on facts "
        "that will still matter later.\n\n"
        "MEMORY TYPES AND WHEN TO SAVE (do this proactively, don't wait to be asked):\n"
        "- 'user': Info about the user's role, goals, preferences, knowledge. Save when you learn "
        "details about who they are. Goal: tailor future behavior to this specific user.\n"
        "- 'correction' (feedback): Guidance the user gives — both what to avoid and what to keep doing. "
        "Save when user corrects your approach ('no not that', 'don't', 'stop doing X') OR confirms "
        "a non-obvious approach worked ('yes exactly', 'perfect'). Include *why* so you can judge edge cases. "
        "Record from failure AND success — if you only save corrections, you drift from validated approaches.\n"
        "- 'project': Ongoing work context — who is doing what, why, by when. Convert relative dates to "
        "absolute dates (e.g. 'Thursday' -> '2026-03-05'). These decay fast; include why.\n"
        "- 'reference': Pointers to external systems — URLs, Linear projects, Slack channels, dashboards. "
        "Save when you learn where to find info outside the project directory.\n"
        "- 'preference': User habits, conventions, workflow patterns, recurring instructions.\n\n"
        "PRIORITY: User preferences and corrections > environment facts > procedural knowledge. "
        "The most valuable memory prevents the user from having to repeat themselves.\n\n"
        "WHAT NOT TO SAVE:\n"
        "- Code patterns, conventions, architecture, file paths, or project structure — derive by reading code.\n"
        "- Git history, recent changes, or who-changed-what — git log / git blame are authoritative.\n"
        "- Debugging solutions or fix recipes — the fix is in the code; the commit message has context.\n"
        "- Anything already documented in CLAUDE.md / project docs.\n"
        "- Ephemeral task details: in-progress work, temporary state, current conversation context.\n"
        "These exclusions apply even when the user explicitly asks. If they ask to save a PR list or "
        "activity summary, ask what was *surprising* or *non-obvious* — that is the part worth keeping.\n\n"
        "STALENESS CAVEAT: Memories are claims about past state. Verify before asserting as current fact. "
        "Memory records can become stale over time. Before answering the user or building assumptions "
        "based solely on information in memory records, verify that the memory is still correct by reading "
        "the current state of files or resources. If a recalled memory conflicts with current information, "
        "trust what you observe now — and update or remove the stale memory.\n\n"
        "TRUSTING RECALL — Before recommending from memory:\n"
        "- If the memory names a file path: check the file exists.\n"
        "- If the memory names a function or flag: grep for it.\n"
        "- If the user is about to act on your recommendation, verify first.\n"
        "'The memory says X exists' is not the same as 'X exists now.'\n\n"
        "TWO TARGETS:\n"
        "- 'user': who the user is — name, role, preferences, communication style, pet peeves\n"
        "- 'memory': your notes — environment facts, project conventions, tool quirks, lessons learned\n\n"
        "ACTIONS: add (new entry), replace (update existing — old_text identifies it), "
        "remove (delete — old_text identifies it), search (find memories by query).\n\n"
        "SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "search"],
                "description": "The action to perform."
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which memory store: 'memory' for personal notes, 'user' for user profile."
            },
            "content": {
                "type": "string",
                "description": "The entry content. Required for 'add' and 'replace'."
            },
            "old_text": {
                "type": "string",
                "description": "Short unique substring identifying the entry to replace or remove."
            },
            "type": {
                "type": "string",
                "enum": ["general", "preference", "correction", "project", "reference"],
                "description": "Memory type (optional). preference=user habits, correction=behavioral fix, project=ongoing work, reference=external system pointer."
            },
            "search_query": {
                "type": "string",
                "description": "Search query for 'search' action. Returns ranked matching memories."
            },
        },
        "required": ["action", "target"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""),
        target=args.get("target", "memory"),
        content=args.get("content"),
        old_text=args.get("old_text"),
        type=args.get("type", "general"),
        search_query=args.get("search_query"),
        store=kw.get("store")),
    check_fn=check_memory_requirements,
    emoji="🧠",
)
