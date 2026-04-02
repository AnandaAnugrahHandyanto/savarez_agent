#!/usr/bin/env python3
"""
Memory Tool Module - Persistent Curated Memory

Provides bounded, DB-backed memory that persists across sessions. Two stores:
  - memory: agent's personal notes and observations (environment facts, project
    conventions, tool quirks, things learned)
  - user: what the agent knows about the user (preferences, communication style,
    expectations, workflow habits)

Both are injected into the system prompt as a frozen snapshot at session start.
Mid-session writes update the DB immediately (durable) but do NOT change
the system prompt -- this preserves the prefix cache for the entire session.
The snapshot refreshes on the next session start.

Flat files (MEMORY.md / USER.md) are kept as READ-ONLY backups.
On first load, entries are migrated from flat files to DB if DB is empty.

Entry delimiter: § (section sign). Entries can be multiline.
Character limits (not tokens) because char counts are model-independent.

Design:
- Single `memory` tool with action parameter: add, replace, remove, read
- replace/remove use short unique substring matching (not full text or IDs)
- Behavioral guidance lives in the tool schema description
- Frozen snapshot pattern: system prompt is stable, tool responses show live state
- DB-backed: all mutations go to SQLite; flat files are never written after migration
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Where memory flat files live (kept as read-only backup)
MEMORY_DIR = get_hermes_home() / "memories"

ENTRY_DELIMITER = "\n§\n"

# Default compaction threshold (80% fill)
DEFAULT_COMPACTION_THRESHOLD = 0.80


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
    (r'\$HOME/\.ssh|~/\.ssh', "ssh_access"),
    (r'\$HOME/\.hermes/\.env|~/\.hermes/\.env', "hermes_env"),
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
    Bounded curated memory with DB persistence. One instance per AIAgent.

    Maintains two parallel states:
      - _system_prompt_snapshot: frozen at load time, used for system prompt injection.
        Never mutated mid-session. Keeps prefix cache stable.
      - memory_entries / user_entries: live state, mutated by tool calls, persisted to DB.
        Tool responses always reflect this live state.

    Flat files (MEMORY.md / USER.md) are kept as read-only backups.
    First load migrates flat file content into DB if DB is empty.
    """

    def __init__(
        self,
        memory_char_limit: int = 2200,
        user_char_limit: int = 1375,
        db_path: Path = None,
        config: dict = None,
        memory_dir: Path = None,
    ):
        # Hot tier injection limits (what gets auto-injected into system prompt).
        # In DB mode these are soft guides for hot tier selection, not hard storage limits.
        # In flat file mode these are the hard storage limits (legacy behavior).
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit

        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []
        # Frozen snapshot for system prompt -- set once at load_from_disk()
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}

        # DB config
        self._db_path = db_path  # None = no DB, use flat files only
        self._config = config or {}
        self._vec_available = False

        # Flat file directory (defaults to global MEMORY_DIR, overridable for testing)
        self._memory_dir = memory_dir if memory_dir is not None else MEMORY_DIR

        # Hot tier config — how many recent entries to auto-inject and their char budget
        memory_cfg = self._config.get("memory", {})
        self._hot_entry_count = int(memory_cfg.get("hot_entry_count", 10))
        self._hot_char_limit_memory = int(memory_cfg.get("hot_char_limit", memory_char_limit))
        self._hot_char_limit_user = int(memory_cfg.get("hot_char_limit_user", user_char_limit))

        # Warm tier compaction threshold — compact when warm tier exceeds this many entries
        self._warm_compaction_threshold = int(memory_cfg.get("warm_compaction_threshold", 20))

        # Compaction threshold (legacy — used for fill ratio checks in compact())
        self._compaction_threshold = float(
            memory_cfg.get("compaction_threshold", DEFAULT_COMPACTION_THRESHOLD)
        )

    def _get_db_conn(self):
        """Open a fresh connection with sqlite-vec loaded if available.

        Also ensures the memories table exists — guards against cases where
        MemoryStore is used before SessionDB has initialized the schema.
        """
        import sqlite3
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            try:
                sqlite_vec.load(conn)
                self._vec_available = True
            finally:
                # Always disable extension loading, even if load fails
                try:
                    conn.enable_load_extension(False)
                except Exception:
                    pass
        except Exception:
            self._vec_available = False
        # Ensure memories table exists (idempotent)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    content TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    compacted_at REAL,
                    source_count INTEGER DEFAULT 1
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_target ON memories(target, level)"
            )
            conn.commit()
        except Exception:
            pass  # Table may already exist or DB may be read-only
        return conn

    def load_from_disk(self):
        """Load entries from DB (with flat file migration fallback), capture system prompt snapshot."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)

        if self._db_path is not None:
            self._load_from_db()
        else:
            # Fallback: load from flat files (no DB configured)
            self.memory_entries = self._read_flat_file(self._memory_dir / "MEMORY.md")
            self.user_entries = self._read_flat_file(self._memory_dir / "USER.md")
            # Deduplicate entries (preserves order, keeps first occurrence)
            self.memory_entries = list(dict.fromkeys(self.memory_entries))
            self.user_entries = list(dict.fromkeys(self.user_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", self.memory_entries),
            "user": self._render_block("user", self.user_entries),
        }

    def _load_from_db(self):
        """Load entries from DB. Migrate flat files if DB is empty."""
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()
                # Check if DB has any entries
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM memories WHERE level = 1"
                )
                row = cursor.fetchone()
                db_count = row["cnt"] if row else 0

                if db_count == 0:
                    # DB is empty — attempt one-time flat file migration
                    self._migrate_flat_files_to_db(cursor)
                    conn.commit()

                # Load HOT tier only — most recent N entries within char budget.
                # Warm entries (older level=1) stay in DB, retrieved via memory_search.
                for target, char_limit in [
                    ("memory", self._hot_char_limit_memory),
                    ("user", self._hot_char_limit_user),
                ]:
                    cursor.execute(
                        """
                        SELECT content FROM memories
                        WHERE target = ? AND level = 1
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (target, self._hot_entry_count),
                    )
                    # Reverse so oldest-first order is preserved in system prompt
                    hot_entries = [r["content"] for r in reversed(cursor.fetchall())]
                    hot_entries = list(dict.fromkeys(hot_entries))

                    # Trim to char budget (drop oldest if over budget)
                    while hot_entries and len(ENTRY_DELIMITER.join(hot_entries)) > char_limit:
                        hot_entries.pop(0)

                    if target == "memory":
                        self.memory_entries = hot_entries
                    else:
                        self.user_entries = hot_entries

            finally:
                conn.close()

        except Exception as e:
            logger.warning("Failed to load memories from DB, falling back to flat files: %s", e)
            # Fallback to flat files
            self.memory_entries = self._read_flat_file(self._memory_dir / "MEMORY.md")
            self.user_entries = self._read_flat_file(self._memory_dir / "USER.md")
            self.memory_entries = list(dict.fromkeys(self.memory_entries))
            self.user_entries = list(dict.fromkeys(self.user_entries))

    def _migrate_flat_files_to_db(self, cursor):
        """One-time migration: read flat files and insert entries into DB."""
        for target, filename in [("memory", "MEMORY.md"), ("user", "USER.md")]:
            flat_path = self._memory_dir / filename
            entries = self._read_flat_file(flat_path)
            entries = list(dict.fromkeys(entries))  # deduplicate
            now = time.time()
            for entry in entries:
                cursor.execute(
                    "INSERT INTO memories (target, content, level, created_at) VALUES (?, ?, 1, ?)",
                    (target, entry, now),
                )
        logger.info("Migrated flat file memory entries to DB")

    def _db_reload_target(self, target: str):
        """Re-read live entries for a target from DB into in-memory state."""
        if self._db_path is None:
            return
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM memories WHERE target = ? AND level = 1 ORDER BY id ASC",
                    (target,),
                )
                rows = cursor.fetchall()
            finally:
                conn.close()
            entries = list(dict.fromkeys([r["content"] for r in rows]))
            self._set_entries(target, entries)
        except Exception as e:
            logger.warning("Failed to reload memories from DB: %s", e)

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

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Append a new entry. Returns error if it would exceed the char limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        # Scan for injection/exfiltration before accepting
        scan_error = _scan_memory_content(content)
        if scan_error:
            return {"success": False, "error": scan_error}

        if self._db_path is not None:
            result = self._add_to_db(target, content)
        else:
            result = self._add_to_flat_files(target, content)
        return result

    def _add_to_db(self, target: str, content: str) -> Dict[str, Any]:

        """Add entry to DB.

        In DB mode storage is unlimited — only checks for exact duplicates.
        Does NOT load all rows (would be O(n) as DB grows); uses a targeted
        EXISTS query for duplicate detection instead.
        """
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()

                # Duplicate check — targeted query, not full table scan
                cursor.execute(
                    "SELECT 1 FROM memories WHERE target = ? AND level = 1 AND content = ? LIMIT 1",
                    (target, content),
                )
                if cursor.fetchone():
                    return self._success_response(target, "Entry already exists (no duplicate added).")

                # Insert into DB — no hard storage limit in DB mode
                cursor.execute(
                    "INSERT INTO memories (target, content, level, created_at) VALUES (?, ?, 1, ?)",
                    (target, content, time.time()),
                )
                conn.commit()
                # Append to in-memory hot tier (will be naturally pruned on next load)
                self._entries_for(target).append(content)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to add memory to DB: %s", e)
            return {"success": False, "error": f"DB write failed: {e}"}

        return self._success_response(target, "Entry added.")

    def _add_to_flat_files(self, target: str, content: str) -> Dict[str, Any]:
        """Fallback: add entry to flat files (legacy mode)."""
        path = self._path_for(target)
        with self._file_lock(path):
            # Re-read from disk under lock
            entries = self._read_flat_file(path)
            entries = list(dict.fromkeys(entries))
            self._set_entries(target, entries)

            limit = self._char_limit(target)

            # Reject exact duplicates
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
            self._write_flat_file(path, entries)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        # Scan replacement content for injection/exfiltration
        scan_error = _scan_memory_content(new_content)
        if scan_error:
            return {"success": False, "error": scan_error}

        if self._db_path is not None:
            return self._replace_in_db(target, old_text, new_content)
        else:
            return self._replace_in_flat_files(target, old_text, new_content)

    def _replace_in_db(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Replace entry in DB."""
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, content FROM memories WHERE target = ? AND level = 1 ORDER BY id ASC",
                    (target,),
                )
                rows = cursor.fetchall()
                entries = [(r["id"], r["content"]) for r in rows]

                matches = [(row_id, e) for row_id, e in entries if old_text in e]

                if len(matches) == 0:
                    return {"success": False, "error": f"No entry matched '{old_text}'."}

                if len(matches) > 1:
                    unique_texts = set(e for _, e in matches)
                    if len(unique_texts) > 1:
                        previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                        return {
                            "success": False,
                            "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                            "matches": previews,
                        }

                row_id = matches[0][0]
                all_contents = [e for _, e in entries]
                idx = next(i for i, (rid, _) in enumerate(entries) if rid == row_id)

                # DB mode: no hard storage limit — replace unconditionally.
                # Hot tier selection at load time handles injection budget.

                cursor.execute(
                    "UPDATE memories SET content = ? WHERE id = ?",
                    (new_content, row_id),
                )
                conn.commit()

                # Update in-memory state
                updated = [e if i != idx else new_content for i, e in enumerate(all_contents)]
                self._set_entries(target, updated)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to replace memory in DB: %s", e)
            return {"success": False, "error": f"DB write failed: {e}"}

        return self._success_response(target, "Entry replaced.")

    def _replace_in_flat_files(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Fallback: replace entry in flat files."""
        path = self._path_for(target)
        with self._file_lock(path):
            entries = self._read_flat_file(path)
            entries = list(dict.fromkeys(entries))
            self._set_entries(target, entries)

            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }

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
            self._write_flat_file(path, entries)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove the entry containing old_text substring."""
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}

        if self._db_path is not None:
            return self._remove_from_db(target, old_text)
        else:
            return self._remove_from_flat_files(target, old_text)

    def _remove_from_db(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove entry from DB."""
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, content FROM memories WHERE target = ? AND level = 1 ORDER BY id ASC",
                    (target,),
                )
                rows = cursor.fetchall()
                entries = [(r["id"], r["content"]) for r in rows]

                matches = [(row_id, e) for row_id, e in entries if old_text in e]

                if len(matches) == 0:
                    return {"success": False, "error": f"No entry matched '{old_text}'."}

                if len(matches) > 1:
                    unique_texts = set(e for _, e in matches)
                    if len(unique_texts) > 1:
                        previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                        return {
                            "success": False,
                            "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                            "matches": previews,
                        }

                row_id = matches[0][0]
                cursor.execute("DELETE FROM memories WHERE id = ?", (row_id,))
                conn.commit()

                # Update in-memory state
                updated = [e for rid, e in entries if rid != row_id]
                # If dupes exist, still remove only first
                if len(matches) > 1:
                    first_rid = matches[0][0]
                    updated = [e for rid, e in entries if rid != first_rid]
                self._set_entries(target, updated)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to remove memory from DB: %s", e)
            return {"success": False, "error": f"DB write failed: {e}"}

        return self._success_response(target, "Entry removed.")

    def _remove_from_flat_files(self, target: str, old_text: str) -> Dict[str, Any]:
        """Fallback: remove entry from flat files."""
        path = self._path_for(target)
        with self._file_lock(path):
            entries = self._read_flat_file(path)
            entries = list(dict.fromkeys(entries))
            self._set_entries(target, entries)

            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if len(matches) == 0:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self._write_flat_file(path, entries)

        return self._success_response(target, "Entry removed.")

    def compact(self, target: str, call_llm=None) -> dict:
        """
        LLM-based compaction. Takes all live entries for target, calls LLM to
        consolidate them into fewer denser entries, writes result back, marks
        old entries as level=2 (compacted).

        Returns dict with success, old_count, new_count, chars_before, chars_after.

        call_llm: callable matching agent.auxiliary_client.call_llm signature:
            call_llm(task, messages, max_tokens, temperature) -> response
        If None, returns error.
        """
        if call_llm is None:
            return {"success": False, "error": "No LLM client available for compaction."}

        # In DB mode: load ALL level=1 entries (hot + warm) from DB for compaction.
        # This is critical — self._entries_for() only has the hot tier in memory.
        # We also track IDs so we archive exactly these rows and no others.
        source_ids: list = []
        if self._db_path is not None:
            try:
                conn = self._get_db_conn()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, content FROM memories WHERE target = ? AND level = 1 ORDER BY id ASC",
                        (target,),
                    )
                    rows = cursor.fetchall()
                finally:
                    conn.close()
                source_ids = [r["id"] for r in rows]
                entries = [r["content"] for r in rows]
            except Exception as e:
                return {"success": False, "error": f"Failed to load entries for compaction: {e}"}
        else:
            entries = self._entries_for(target)

        if not entries:
            return {"success": False, "error": f"No entries to compact in '{target}'."}

        if len(entries) < 2:
            return {"success": False, "error": "Need at least 2 entries to compact."}

        old_count = len(entries)
        chars_before = len(ENTRY_DELIMITER.join(entries))

        # Minimum threshold — don't compact already-sparse memory.
        # DB mode: require at least 3 entries total (warm tier should have entries to compact).
        # Flat file mode: require at least 40% fill.
        # NOTE: Compaction operates on all live (level=1) entries together.
        # Aging (compact only old entries, leave recent untouched) is deferred —
        # see bkith ConversationCompactor for reference if needed later.
        if self._db_path is not None:
            min_entries = 3
            if old_count < min_entries:
                return {
                    "success": False,
                    "error": f"Only {old_count} entries — need at least {min_entries} to compact.",
                }
        else:
            limit = self._char_limit(target)
            fill = chars_before / limit if limit > 0 else 0
            min_fill = 0.40
            if fill < min_fill:
                return {
                    "success": False,
                    "error": (
                        f"Memory at {fill:.0%} fill — below minimum threshold ({min_fill:.0%}) for compaction. "
                        "No compaction needed."
                    ),
                }

        entries_block = ENTRY_DELIMITER.join(entries)
        # Budget: target 70% of current chars, hard ceiling at current chars
        char_budget = max(200, int(chars_before * 0.70))

        prompt = (
            "You are a memory compaction system. Below are memory entries for an AI agent.\n\n"
            "Consolidate these into the minimum number of dense entries that preserve ALL important information.\n"
            "Rules:\n"
            "- Merge related facts into single entries\n"
            "- Remove exact duplicates and near-duplicates\n"
            "- Preserve ALL specific details (names, values, URLs, conventions)\n"
            "- Keep entries that are still relevant and actionable\n"
            "- Be terse — facts only, no prose connectors or elaboration. Every word must earn its place.\n"
            "- Write each entry as a single dense paragraph (no bullets within an entry)\n"
            "- Separate entries with exactly: \\n§\\n\n"
            "- Do NOT invent or add information not present in the source entries\n"
            f"- HARD LIMIT: total output must be under {char_budget} characters\n"
            "- Target: reduce entry count by at least 30% while keeping all signal\n\n"
            f"Source entries ({chars_before} chars):\n{entries_block}\n\n"
            f"Compacted entries (§-separated, must be under {char_budget} chars total):"
        )

        try:
            response = call_llm(
                task="compact_memory",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=min(2048, char_budget * 2),  # rough token estimate
                temperature=0.3,
            )
            raw_output = response.choices[0].message.content.strip()
        except Exception as e:
            return {"success": False, "error": f"LLM call failed: {e}"}

        # Parse the compacted entries
        new_entries = [e.strip() for e in raw_output.split(ENTRY_DELIMITER)]
        new_entries = [e for e in new_entries if e]

        if not new_entries:
            return {"success": False, "error": "LLM returned empty compaction result."}

        # Security scan compacted entries — LLM output goes back into the system prompt
        for entry in new_entries:
            scan_error = _scan_memory_content(entry)
            if scan_error:
                return {"success": False, "error": f"Compaction blocked: {scan_error}"}

        # Verify improvement — rollback if compaction made things worse
        new_char_count = sum(len(e) for e in new_entries) + (len(ENTRY_DELIMITER) * (len(new_entries) - 1))
        no_char_improvement = new_char_count >= chars_before
        no_entry_improvement = len(new_entries) >= old_count
        if no_char_improvement and no_entry_improvement:
            return {
                "success": False,
                "error": (
                    f"Compaction produced no improvement ({old_count} → {len(new_entries)} entries, "
                    f"{chars_before:,} → {new_char_count:,} chars). Original entries kept."
                ),
            }

        # Write to DB
        if self._db_path is not None:
            try:
                conn = self._get_db_conn()
                try:
                    cursor = conn.cursor()
                    now = time.time()

                    # Archive ONLY the specific rows that were part of the compaction input.
                    # Using source_ids prevents archiving rows added concurrently or
                    # rows not loaded during this compaction pass.
                    if source_ids:
                        placeholders = ",".join("?" * len(source_ids))
                        cursor.execute(
                            f"UPDATE memories SET level = 2, compacted_at = ? WHERE id IN ({placeholders})",
                            (now, *source_ids),
                        )
                    else:
                        # Flat file mode fallback — no IDs available
                        cursor.execute(
                            "UPDATE memories SET level = 2, compacted_at = ? WHERE target = ? AND level = 1",
                            (now, target),
                        )

                    # Insert new compacted entries as level=1 (live)
                    for entry in new_entries:
                        cursor.execute(
                            "INSERT INTO memories (target, content, level, created_at, source_count) VALUES (?, ?, 1, ?, ?)",
                            (target, entry, now, old_count),
                        )

                    conn.commit()
                    self._set_entries(target, new_entries)
                finally:
                    conn.close()
            except Exception as e:
                return {"success": False, "error": f"DB write failed: {e}"}
        else:
            # Flat file mode — replace entries
            self._set_entries(target, new_entries)
            self._write_flat_file(self._path_for(target), new_entries)

        new_count = len(new_entries)
        chars_after = self._char_count(target)

        return {
            "success": True,
            "target": target,
            "old_count": old_count,
            "new_count": new_count,
            "chars_before": chars_before,
            "chars_after": chars_after,
            "reduction_pct": round((1 - new_count / old_count) * 100, 1) if old_count > 0 else 0,
        }

    def fill_ratio(self, target: str) -> float:
        """Return hot tier fill as a fraction of the hot char limit (0.0–1.0).
        Used for display/diagnostics only in DB mode."""
        limit = self._char_limit(target)
        if limit <= 0:
            return 0.0
        return self._char_count(target) / limit

    def warm_entry_count(self, target: str) -> int:
        """Return the number of warm (non-hot) live entries for a target.

        Warm entries = all level=1 entries minus the hot_entry_count most recent.
        These are stored in DB but not auto-injected into the system prompt.
        """
        if self._db_path is None:
            return 0
        try:
            conn = self._get_db_conn()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM memories WHERE target = ? AND level = 1",
                    (target,),
                )
                row = cursor.fetchone()
                total = row["cnt"] if row else 0
            finally:
                conn.close()
            return max(0, total - self._hot_entry_count)
        except Exception:
            return 0

    @property
    def warm_compaction_threshold(self) -> int:
        """Number of warm entries that triggers compaction."""
        return self._warm_compaction_threshold

    @property
    def compaction_threshold(self) -> float:
        """Fill ratio at which compaction is triggered (legacy — flat file mode)."""
        return self._compaction_threshold

    def format_for_system_prompt(self, target: str) -> Optional[str]:
        """
        Return the frozen snapshot for system prompt injection.

        This returns the state captured at load_from_disk() time, NOT the live
        state. Mid-session writes do not affect this. This keeps the system
        prompt stable across all turns, preserving the prefix cache.

        Returns None if the snapshot is empty (no entries at load time).
        """
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # -- Internal helpers --

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
        """Render a system prompt block with header and usage indicator."""
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

    def _path_for(self, target: str) -> Path:
        if target == "user":
            return self._memory_dir / "USER.md"
        return self._memory_dir / "MEMORY.md"

    @staticmethod
    def _read_flat_file(path: Path) -> List[str]:
        """Read a memory flat file and split into entries."""
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
    def _write_flat_file(path: Path, entries: List[str]):
        """Write entries to a flat file using atomic temp-file + rename (legacy fallback)."""
        import tempfile
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

    @staticmethod
    def _file_lock(path: Path):
        """Acquire an exclusive file lock for read-modify-write safety (flat files only)."""
        import fcntl
        from contextlib import contextmanager

        @contextmanager
        def _lock():
            lock_path = path.with_suffix(path.suffix + ".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = open(lock_path, "w")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                fd.close()

        return _lock()

    # Backward compat: save_to_disk is a no-op when using DB
    def save_to_disk(self, target: str):
        """Legacy method — no-op when DB-backed. Flat file mode writes via _write_flat_file."""
        pass


def memory_tool(
    action: str,
    target: str = "memory",
    content: str = None,
    old_text: str = None,
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
        result = store.add(target, content)

    elif action == "replace":
        if not old_text:
            return json.dumps({"success": False, "error": "old_text is required for 'replace' action."}, ensure_ascii=False)
        if not content:
            return json.dumps({"success": False, "error": "content is required for 'replace' action."}, ensure_ascii=False)
        result = store.replace(target, old_text, content)

    elif action == "remove":
        if not old_text:
            return json.dumps({"success": False, "error": "old_text is required for 'remove' action."}, ensure_ascii=False)
        result = store.remove(target, old_text)

    else:
        return json.dumps({"success": False, "error": f"Unknown action '{action}'. Use: add, replace, remove"}, ensure_ascii=False)

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
        "WHEN TO SAVE (do this proactively, don't wait to be asked):\n"
        "- User corrects you or says 'remember this' / 'don't do that again'\n"
        "- User shares a preference, habit, or personal detail (name, role, timezone, coding style)\n"
        "- You discover something about the environment (OS, installed tools, project structure)\n"
        "- You learn a convention, API quirk, or workflow specific to this user's setup\n"
        "- You identify a stable fact that will be useful again in future sessions\n\n"
        "PRIORITY: User preferences and corrections > environment facts > procedural knowledge. "
        "The most valuable memory prevents the user from having to repeat themselves.\n\n"
        "Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO "
        "state to memory; use session_search to recall those from past transcripts.\n"
        "If you've discovered a new way to do something, solved a problem that could be "
        "necessary later, save it as a skill with the skill tool.\n\n"
        "TWO TARGETS:\n"
        "- 'user': who the user is -- name, role, preferences, communication style, pet peeves\n"
        "- 'memory': your notes -- environment facts, project conventions, tool quirks, lessons learned\n\n"
        "ACTIONS: add (new entry), replace (update existing -- old_text identifies it), "
        "remove (delete -- old_text identifies it).\n\n"
        "SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove"],
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
        store=kw.get("store")),
    check_fn=check_memory_requirements,
    emoji="🧠",
)
