"""Tool failure tracker — adaptive pathway suggestions on repeated failures.

Tracks consecutive failures per tool name within a session.  When a tool
fails *threshold* times in a row, the tracker injects a structured hint
into the tool result suggesting the model pivot to an alternative approach.

This addresses the "inertia of direction" failure mode where agents
repeatedly invoke the same failing primitive without strategy shifts.
"""

import json
import logging
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default number of consecutive failures before suggesting a pivot.
DEFAULT_PIVOT_THRESHOLD = 3

# Maximum number of pivot hints emitted per tool per session to avoid spam.
MAX_HINTS_PER_TOOL = 2

# Known alternative pathways: tool -> list of (condition, suggestion) tuples.
# The condition is a substring match on the error message; suggestion is the
# hint text injected into the tool result.
_ALTERNATIVE_PATHWAYS: Dict[str, List[Tuple[str, str]]] = {
    "execute_code": [
        (
            "ModuleNotFoundError",
            "The module is not available in the execute_code sandbox. "
            "Consider using the `terminal` tool instead to run a script "
            "with full system access.",
        ),
        (
            "PermissionError",
            "Permission denied in sandbox. Use the `terminal` tool for "
            "operations requiring elevated privileges.",
        ),
        (
            "ImportError",
            "Import failed in the sandboxed environment. Try using "
            "`terminal` to run the script with full Python environment.",
        ),
    ],
    "terminal": [
        (
            "command not found",
            "Command not found. Check if the package is installed, or "
            "try using `execute_code` for Python-based alternatives.",
        ),
        (
            "Permission denied",
            "Permission denied. The operation may require sudo or a "
            "different approach.",
        ),
    ],
    "read_file": [
        (
            "No such file",
            "File not found. Use `search_files` to locate the correct "
            "path before attempting to read.",
        ),
    ],
    "write_file": [
        (
            "Permission denied",
            "Write permission denied. Check file ownership or try a "
            "different path.",
        ),
    ],
    "web_search": [
        (
            "rate limit",
            "Search rate-limited. Try using `browser_navigate` to "
            "access the information directly, or wait before retrying.",
        ),
    ],
    "browser_navigate": [
        (
            "timeout",
            "Navigation timed out. Try `web_search` or `web_extract` "
            "for faster information retrieval.",
        ),
    ],
}


class ToolFailureTracker:
    """Track per-tool consecutive failures and emit pivot hints.

    Thread-safe — tool calls execute concurrently across worker threads.
    """

    def __init__(self, pivot_threshold: int = DEFAULT_PIVOT_THRESHOLD):
        self._threshold = pivot_threshold
        # {tool_name: consecutive_failure_count}
        self._failure_counts: Dict[str, int] = defaultdict(int)
        # {tool_name: number_of_hints_emitted}
        self._hints_emitted: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record_result(self, tool_name: str, result: str, is_error: bool) -> Optional[str]:
        """Record a tool result and return an advisory hint if warranted.

        Returns None when no hint is needed.  Otherwise returns a short
        advisory string that should be *appended* to the tool result so the
        model sees it in-context.
        """
        with self._lock:
            if is_error:
                self._failure_counts[tool_name] += 1
            else:
                # Success resets the counter.
                self._failure_counts[tool_name] = 0
                return None

            count = self._failure_counts[tool_name]
            hints_so_far = self._hints_emitted[tool_name]

            if count < self._threshold or hints_so_far >= MAX_HINTS_PER_TOOL:
                return None

            self._hints_emitted[tool_name] += 1

        # Build the hint outside the lock.
        hint = self._build_hint(tool_name, result)
        if hint:
            logger.info(
                "ToolFailureTracker: %s failed %d consecutive times; "
                "emitting pivot hint (%d/%d)",
                tool_name, count, hints_so_far + 1, MAX_HINTS_PER_TOOL,
            )
        return hint

    def _build_hint(self, tool_name: str, result: str) -> Optional[str]:
        """Construct a pivot hint based on tool name and error content."""
        result_lower = result[:1000].lower() if result else ""

        # Check tool-specific alternatives first.
        alternatives = _ALTERNATIVE_PATHWAYS.get(tool_name, [])
        for condition, suggestion in alternatives:
            if condition.lower() in result_lower:
                return (
                    f"\n\n[PERSISTENCE HINT: This tool has failed {self._threshold}+ "
                    f"consecutive times. {suggestion}]"
                )

        # Generic pivot hint when no specific match.
        return (
            f"\n\n[PERSISTENCE HINT: '{tool_name}' has failed "
            f"{self._threshold}+ consecutive times with similar errors. "
            f"Consider a fundamentally different approach — use a different "
            f"tool, decompose the task, or ask the user for clarification.]"
        )

    def reset(self, tool_name: Optional[str] = None) -> None:
        """Reset failure tracking for a tool or all tools."""
        with self._lock:
            if tool_name:
                self._failure_counts.pop(tool_name, None)
                self._hints_emitted.pop(tool_name, None)
            else:
                self._failure_counts.clear()
                self._hints_emitted.clear()

    def get_failure_counts(self) -> Dict[str, int]:
        """Snapshot of current consecutive failure counts."""
        with self._lock:
            return dict(self._failure_counts)
