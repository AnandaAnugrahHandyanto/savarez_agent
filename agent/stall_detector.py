"""Stall detector: stop when N consecutive tool calls produce no progress.

Tracks the action signature (tool name + normalized arguments) of each tool
call batch executed in the agent loop.  When consecutive batches repeat the
same action, the detector warns the LLM and eventually hard-stops to prevent
burning the entire iteration budget on hopeless retries.

Design follows the "Harness Engineering" framework's recommendation:
"no progress — repeating the same action across consecutive rounds" is one
of the 4 essential stop conditions for any agent harness.

See issue #41313 for the full proposal.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StallDetectorConfig:
    """Configuration for the stall detector."""

    # Number of consecutive identical batches to trigger a warning.
    consecutive_threshold: int = 3
    # Sliding window size for pattern detection.
    window_size: int = 7
    # Number of identical batches within the window to trigger a warning.
    window_threshold: int = 5
    # Max stall warnings before hard-stop (0 = disabled).
    max_stalls: int = 2


@dataclass
class StallDetection:
    """Result of a stall check."""

    is_stall: bool = False
    message: str = ""
    hard_stop: bool = False


class StallDetector:
    """Detects when the agent repeats the same tool calls without progress.

    Usage::

        detector = StallDetector()
        # After each tool-call batch:
        sig = StallDetector.tool_batch_signature(tool_calls)
        result = detector.check(sig)
        if result.is_stall:
            # Inject result.message into the conversation
            if result.hard_stop:
                # Break the loop

    The detector resets at the start of each ``run_conversation`` turn via
    :meth:`reset`.
    """

    def __init__(self, config: Optional[StallDetectorConfig] = None) -> None:
        self.config = config or StallDetectorConfig()
        self._recent_signatures: deque[str] = deque(
            maxlen=self.config.window_size
        )
        self._consecutive_count: int = 0
        self._last_signature: Optional[str] = None
        self._stall_count: int = 0

    def reset(self) -> None:
        """Reset detector state for a new turn."""
        self._recent_signatures.clear()
        self._consecutive_count = 0
        self._last_signature = None
        self._stall_count = 0

    @staticmethod
    def tool_batch_signature(tool_calls: Any) -> str:
        """Compute a normalized signature for a batch of tool calls.

        The signature captures tool names and a hash of their arguments so
        that identical calls (same tool, same args) produce the same sig,
        while different arguments produce different sigs.

        Returns a compact string like ``"read_file+patch[a3b2c1]"``.
        """
        if not tool_calls:
            return ""

        parts = []
        for tc in sorted(tool_calls, key=lambda t: _tc_name(t)):
            name = _tc_name(tc)
            args_raw = _tc_args(tc)
            # Normalize args: sort keys, dump to canonical JSON, hash.
            try:
                if isinstance(args_raw, str):
                    args_obj = json.loads(args_raw)
                else:
                    args_obj = args_raw or {}
                canonical = json.dumps(
                    args_obj, sort_keys=True, separators=(",", ":")
                )
            except (json.JSONDecodeError, TypeError):
                canonical = str(args_raw)
            arg_hash = hashlib.md5(canonical.encode()).hexdigest()[:6]
            parts.append(f"{name}[{arg_hash}]")

        return "+".join(parts)

    def check(self, batch_signature: str) -> StallDetection:
        """Check whether the current batch indicates a stall.

        Args:
            batch_signature: Output of :meth:`tool_batch_signature`.

        Returns:
            :class:`StallDetection` with ``is_stall=True`` if a stall is
            detected.  ``hard_stop=True`` when the agent should terminate.
        """
        if not batch_signature:
            return StallDetection()

        self._recent_signatures.append(batch_signature)

        # Check consecutive repetition.
        if batch_signature == self._last_signature:
            self._consecutive_count += 1
        else:
            self._consecutive_count = 1
            self._last_signature = batch_signature

        # ── Consecutive threshold ──
        if self._consecutive_count >= self.config.consecutive_threshold:
            return self._trigger_stall(
                f"The agent has repeated the exact same tool call batch "
                f"({batch_signature}) {self._consecutive_count} times in a "
                f"row.  Summarize what you have learned so far, propose a "
                f"different approach, or ask the user for guidance."
            )

        # ── Window threshold ──
        if len(self._recent_signatures) >= self.config.window_size:
            counts: Dict[str, int] = {}
            for sig in self._recent_signatures:
                counts[sig] = counts.get(sig, 0) + 1
            max_count = max(counts.values())
            if max_count >= self.config.window_threshold:
                dominant = max(counts, key=counts.get)
                return self._trigger_stall(
                    f"In the last {self.config.window_size} tool-call "
                    f"batches, {max_count} had the same action signature "
                    f"({dominant}).  The agent appears to be stuck in a "
                    f"loop.  Try a fundamentally different approach or ask "
                    f"the user for help."
                )

        return StallDetection()

    def _trigger_stall(self, message: str) -> StallDetection:
        self._stall_count += 1
        hard = (
            self.config.max_stalls > 0
            and self._stall_count > self.config.max_stalls
        )
        if hard:
            message = (
                f"⚠️ Stall detector: the agent has been detected stalling "
                f"{self._stall_count} times.  Terminating to prevent "
                f"wasting the iteration budget.  Please rephrase your "
                f"request or break it into smaller steps."
            )
        logger.warning(
            "Stall detected (count=%d, hard_stop=%s): %s",
            self._stall_count,
            hard,
            message[:200],
        )
        return StallDetection(
            is_stall=True,
            message=message,
            hard_stop=hard,
        )


# ── Helpers ─────────────────────────────────────────────────────────────

def _tc_name(tc: Any) -> str:
    """Extract tool name from a tool_call object or dict."""
    if hasattr(tc, "function"):
        return tc.function.name or ""
    if isinstance(tc, dict):
        func = tc.get("function", {})
        return func.get("name", "") if isinstance(func, dict) else ""
    return ""


def _tc_args(tc: Any) -> Any:
    """Extract arguments from a tool_call object or dict."""
    if hasattr(tc, "function"):
        return tc.function.arguments or {}
    if isinstance(tc, dict):
        func = tc.get("function", {})
        return func.get("arguments", {}) if isinstance(func, dict) else {}
    return {}
