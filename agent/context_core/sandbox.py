"""ToolOutputSandbox — isolated staging area for tool outputs.

The sandbox acts as a middleware layer between the raw tool-result messages
produced during a conversation turn and their final form in the message list.
It allows tool outputs to be:

- **Staged** before being committed to the main message list
- **Pruned** using cheap heuristic rules (size, age, deduplication)
- **Summarized** with informative one-line replacements
- **Rolled back** to a previous committed state

The sandbox does NOT hold the full message list — it only stages and manages
the tool_result role messages. Assistant/user/system messages pass through
unchanged.

Usage::

    sandbox = ToolOutputSandbox()
    sandbox.stage(tool_result_msg)

    # Before committing:
    sandbox.prune(max_age_turns=10, max_size_chars=5000)

    # Commit to message list
    committed = sandbox.commit()

    # Or rollback
    sandbox.rollback()
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_PRUNED_PLACEHOLDER = "[Tool output cleared to save context space]"
_DUPLICATE_PLACEHOLDER = "[Duplicate tool output — same content as a more recent call]"


def _summarize_tool_result(tool_name: str, tool_args: str, content: str) -> str:
    """Create an informative 1-line summary of a tool call + result.

    Mirrors the logic from context_compressor.py for consistency.
    """
    import json
    import re

    try:
        args = json.loads(tool_args) if tool_args else {}
    except (json.JSONDecodeError, TypeError):
        args = {}

    content_len = len(content or "")
    line_count = (content or "").count("\n") + 1 if (content or "").strip() else 0

    if tool_name == "terminal":
        cmd = args.get("command", "")
        if len(cmd) > 80:
            cmd = cmd[:77] + "..."
        exit_match = re.search(r'"exit_code"\s*:\s*(-?\d+)', content or "")
        exit_code = exit_match.group(1) if exit_match else "?"
        return f"[terminal] ran `{cmd}` -> exit {exit_code}, {line_count} lines output"

    if tool_name == "read_file":
        path = args.get("path", "?")
        offset = args.get("offset", 1)
        return f"[read_file] read {path} from line {offset} ({content_len:,} chars)"

    if tool_name == "write_file":
        path = args.get("path", "?")
        written_lines = args.get("content", "").count("\n") + 1 if args.get("content") else "?"
        return f"[write_file] wrote to {path} ({written_lines} lines)"

    if tool_name == "search_files":
        pattern = args.get("pattern", "?")
        path = args.get("path", ".")
        target = args.get("target", "content")
        match_count = re.search(r'"total_count"\s*:\s*(\d+)', content or "")
        count = match_count.group(1) if match_count else "?"
        return f"[search_files] {target} search for '{pattern}' in {path} -> {count} matches"

    if tool_name == "patch":
        path = args.get("path", "?")
        mode = args.get("mode", "replace")
        return f"[patch] {mode} in {path} ({content_len:,} chars result)"

    if tool_name in ("browser_navigate", "browser_click", "browser_snapshot",
                     "browser_type", "browser_scroll", "browser_vision"):
        url = args.get("url", "")
        ref = args.get("ref", "")
        detail = f" {url}" if url else (f" ref={ref}" if ref else "")
        return f"[{tool_name}]{detail} ({content_len:,} chars)"

    if tool_name == "web_search":
        query = args.get("query", "?")
        return f"[web_search] query='{query}' ({content_len:,} chars result)"

    if tool_name == "web_extract":
        urls = args.get("urls", [])
        url_desc = urls[0] if isinstance(urls, list) and urls else "?"
        if isinstance(urls, list) and len(urls) > 1:
            url_desc += f" (+{len(urls) - 1} more)"
        return f"[web_extract] {url_desc} ({content_len:,} chars)"

    if tool_name == "delegate_task":
        goal = args.get("goal", "")
        if len(goal) > 60:
            goal = goal[:57] + "..."
        return f"[delegate_task] '{goal}' ({content_len:,} chars result)"

    if tool_name == "execute_code":
        code_preview = (args.get("code") or "")[:60].replace("\n", " ")
        if len(args.get("code", "")) > 60:
            code_preview += "..."
        return f"[execute_code] `{code_preview}` ({line_count} lines output)"

    if tool_name in ("skill_view", "skills_list", "skill_manage"):
        name = args.get("name", "?")
        return f"[{tool_name}] name={name} ({content_len:,} chars)"

    if tool_name == "vision_analyze":
        question = args.get("question", "")[:50]
        return f"[vision_analyze] '{question}' ({content_len:,} chars)"

    if tool_name == "memory":
        action = args.get("action", "?")
        target = args.get("target", "?")
        return f"[memory] {action} on {target}"

    if tool_name == "todo":
        return "[todo] updated task list"

    if tool_name == "clarify":
        return "[clarify] asked user a question"

    if tool_name == "process":
        action = args.get("action", "?")
        sid = args.get("session_id", "?")
        return f"[process] {action} session={sid}"

    # Generic fallback
    first_arg = ""
    for k, v in list(args.items())[:2]:
        sv = str(v)[:40]
        first_arg += f" {k}={sv}"
    return f"[{tool_name}]{first_arg} ({content_len:,} chars result)"


class ToolOutputSandbox:
    """Isolated staging area for tool_result messages.

    Thread-safe for single-writer patterns (as used in the agent loop).
    For multi-threaded use, wrap access in a lock.

    The sandbox maintains three internal lists:
    - ``_staged``: tool_result messages staged but not yet committed
    - ``_committed``: the last committed snapshot (used for rollback)
    - ``_history``: optional rolling history of committed snapshots
    """

    def __init__(
        self,
        max_staged: int = 100,
        max_history: int = 5,
        prune_on_commit: bool = True,
        min_content_len_to_summarize: int = 200,
    ):
        """
        Args:
            max_staged: Maximum number of staged messages before auto-prune.
            max_history: Number of committed snapshots to retain for rollback.
            prune_on_commit: If True, run prune() automatically on commit().
            min_content_len_to_summarize: Tool results shorter than this are
                left unchanged during pruning.
        """
        self.max_staged = max_staged
        self.max_history = max_history
        self.prune_on_commit = prune_on_commit
        self.min_content_len_to_summarize = min_content_len_to_summarize

        self._staged: List[Dict[str, Any]] = []
        self._committed: List[Dict[str, Any]] = []
        self._history: List[List[Dict[str, Any]]] = []
        self._call_id_map: Dict[str, tuple] = {}  # tool_call_id -> (tool_name, args)
        self._stats = {
            "staged_count": 0,
            "pruned_count": 0,
            "dedup_count": 0,
            "committed_count": 0,
            "rollback_count": 0,
        }

    # ------------------------------------------------------------------
    # Staging API
    # ------------------------------------------------------------------

    def stage(self, message: Dict[str, Any]) -> None:
        """Add a tool_result message to the staging area.

        If the staging area exceeds max_staged, auto-prunes oldest entries
        before adding the new one.
        """
        if len(self._staged) >= self.max_staged:
            self._auto_prune()

        msg = message.copy() if isinstance(message, dict) else {"role": "tool", "content": str(message)}
        self._staged.append(msg)
        self._stats["staged_count"] += 1

    def stage_many(self, messages: List[Dict[str, Any]]) -> None:
        """Stage multiple tool_result messages at once."""
        for msg in messages:
            if msg.get("role") == "tool":
                self.stage(msg)

    def register_tool_call(self, call_id: str, tool_name: str, arguments: str) -> None:
        """Register a tool_call so its metadata is available for summarization.

        Call this before staging the corresponding tool_result.
        """
        self._call_id_map[call_id] = (tool_name, arguments)

    def unregister_tool_call(self, call_id: str) -> None:
        """Remove a tool_call registration (e.g., after commit/rollback)."""
        self._call_id_map.pop(call_id, None)

    def clear_staged(self) -> None:
        """Discard all staged messages without committing."""
        self._staged.clear()
        self._call_id_map.clear()

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    @property
    def staged(self) -> List[Dict[str, Any]]:
        """Return a copy of currently staged messages (read-only view)."""
        return [m.copy() for m in self._staged]

    @property
    def committed(self) -> List[Dict[str, Any]]:
        """Return a copy of the last committed messages (read-only view)."""
        return [m.copy() for m in self._committed]

    @property
    def stats(self) -> Dict[str, int]:
        """Return a snapshot of sandbox statistics."""
        return {**self._stats}

    # ------------------------------------------------------------------
    # Commit / Rollback
    # ------------------------------------------------------------------

    def commit(self) -> List[Dict[str, Any]]:
        """Commit staged messages, replacing the last committed snapshot.

        If prune_on_commit is True, runs prune() on staged messages first.

        Returns the new committed list (a copy; mutations won't affect internals).
        """
        if self.prune_on_commit and self._staged:
            self.prune()

        # Save current committed to history
        if self._committed:
            self._history.append([m.copy() for m in self._committed])
            if len(self._history) > self.max_history:
                self._history.pop(0)

        # Commit staged
        self._committed = [m.copy() for m in self._staged]
        self._stats["committed_count"] += len(self._committed)

        # Clear staged
        self._staged.clear()
        self._call_id_map.clear()

        return self.committed

    def rollback(self) -> List[Dict[str, Any]]:
        """Rollback to the last committed snapshot.

        Discards all staged messages and restores the previous committed state
        from history (if available).

        Returns the rolled-back committed list.
        """
        self._staged.clear()
        self._call_id_map.clear()

        if self._history:
            self._committed = self._history.pop()
            self._stats["rollback_count"] += 1
        else:
            # No history — just clear committed
            self._committed = []

        return self.committed

    def hard_reset(self) -> None:
        """Reset all state — staged, committed, and history."""
        self._staged.clear()
        self._committed.clear()
        self._history.clear()
        self._call_id_map.clear()
        self._stats = {k: 0 for k in self._stats}

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def prune(
        self,
        max_age_turns: Optional[int] = None,
        max_size_chars: int = 5000,
        protect_call_ids: Optional[Set[str]] = None,
    ) -> int:
        """Prune staged messages using heuristic rules.

        Pruning rules applied in order:
          1. Deduplication: identical content across messages keeps only newest
          2. Size-based: large tool results (>max_size_chars) are summarized
          3. Age-based: messages older than max_age_turns are summarized

        Args:
            max_age_turns: If set, tool results beyond this age are summarized.
                A "turn" is one message in the staged list (most recent = 0).
            max_size_chars: Tool results longer than this are summarized.
            protect_call_ids: Set of tool_call_ids to never prune/summarize.

        Returns:
            Number of messages that were modified (pruned or summarized).
        """
        if not self._staged:
            return 0

        protect_call_ids = protect_call_ids or set()
        pruned = 0

        # Build call_id -> (tool_name, args) from registered tool calls
        call_id_to_tool = dict(self._call_id_map)

        # Pass 1: Deduplication
        content_hashes: Dict[str, tuple] = {}  # hash -> (index, call_id)
        for i in range(len(self._staged) - 1, -1, -1):
            msg = self._staged[i]
            if msg.get("role") != "tool":
                continue
            content = msg.get("content") or ""
            if isinstance(content, list):
                continue  # Skip multimodal content
            if len(content) < 200:
                continue
            h = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()[:12]
            if h in content_hashes:
                # Older duplicate — replace with placeholder
                self._staged[i] = {**msg, "content": _DUPLICATE_PLACEHOLDER}
                pruned += 1
                self._stats["dedup_count"] += 1
            else:
                content_hashes[h] = (i, msg.get("tool_call_id", "?"))

        # Pass 2: Size and age pruning with summarization
        for i in range(len(self._staged)):
            msg = self._staged[i]
            if msg.get("role") != "tool":
                continue
            call_id = msg.get("tool_call_id", "")
            if call_id in protect_call_ids:
                continue

            content = msg.get("content") or ""
            if isinstance(content, list):
                continue  # Skip multimodal content

            # Check if we should summarize
            should_summarize = False
            reason = ""

            if len(content) > max_size_chars:
                should_summarize = True
                reason = f"size ({len(content)} > {max_size_chars})"
            elif max_age_turns is not None:
                # i=0 is most recent, increasing i means older
                if i >= max_age_turns:
                    should_summarize = True
                    reason = f"age ({i} >= {max_age_turns})"

            if not should_summarize:
                continue

            tool_name, tool_args = call_id_to_tool.get(call_id, ("unknown", ""))
            summary = _summarize_tool_result(tool_name, tool_args, content)
            self._staged[i] = {**msg, "content": summary}
            pruned += 1
            self._stats["pruned_count"] += 1

        if pruned and not logger.isEnabledFor(logging.DEBUG):
            logger.info("ToolOutputSandbox: pruned %d message(s)", pruned)

        return pruned

    def _auto_prune(self) -> None:
        """Auto-prune when staging area is full (called automatically by stage())."""
        # Keep the most recent half of staged messages
        keep_count = max(1, len(self._staged) // 2)
        self._staged = self._staged[-keep_count:]
        logger.debug("ToolOutputSandbox auto-pruned to %d messages", keep_count)

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------

    def inject_into_messages(
        self,
        messages: List[Dict[str, Any]],
        replace_tool_results: bool = True,
    ) -> List[Dict[str, Any]]:
        """Inject sandbox state into a message list.

        Args:
            messages: The full message list (including tool results).
            replace_tool_results: If True, tool_result messages in the message
                list are replaced with their sandbox counterparts using
                tool_call_id matching. If False, staged messages are appended.

        Returns:
            New message list with sandbox state integrated.
        """
        if not self._committed and not self._staged:
            return [m.copy() for m in messages]

        if replace_tool_results:
            # Build tool_call_id -> sandboxed tool_result
            sandbox_map: Dict[str, Dict[str, Any]] = {}
            for msg in list(self._committed) + list(self._staged):
                cid = msg.get("tool_call_id", "")
                if cid:
                    sandbox_map[cid] = msg

            result = []
            for msg in messages:
                if msg.get("role") == "tool":
                    cid = msg.get("tool_call_id", "")
                    if cid in sandbox_map:
                        result.append(sandbox_map[cid].copy())
                        continue
                result.append(msg.copy() if isinstance(msg, dict) else msg)
            return result
        else:
            # Append staged to the end
            result = [m.copy() for m in messages]
            result.extend(self._staged)
            return result

    def extract_tool_results_from_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract all tool_result messages from a message list into the sandbox.

        Returns the messages with tool_result entries removed (they're now staged).
        """
        tool_results = []
        remaining = []
        for msg in messages:
            if msg.get("role") == "tool":
                tool_results.append(msg.copy())
            else:
                remaining.append(msg.copy() if isinstance(msg, dict) else msg)

        self._staged.extend(tool_results)
        return remaining
