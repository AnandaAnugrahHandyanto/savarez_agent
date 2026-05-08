"""Signal-based skill-creation nudge evaluator.

The evaluator is intentionally pure and best suited for unit tests. Agent loop
code feeds it user messages plus completed tool call/result pairs; it records
which S1-S4 signals fired in the current window.
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass, field
from pathlib import PurePosixPath


def _terminal_signature(args: dict) -> str:
    cmd = str((args or {}).get("command") or "").strip()
    if not cmd:
        return ""
    parts = cmd.split()
    head = parts[0].rsplit("/", 1)[-1] if parts else ""
    sub = parts[1] if len(parts) > 1 else ""
    if head in {"git", "gh", "kubectl"}:
        return f"{head} {sub}".strip()
    return head


def _path_signature(args: dict) -> str:
    raw = (args or {}).get("path") or (args or {}).get("file_path") or ""
    path = str(raw).strip()
    if not path:
        return ""
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


_PER_TOOL_SIG = {
    "terminal": _terminal_signature,
    "process": _terminal_signature,
    "read_file": _path_signature,
    "write_file": _path_signature,
    "edit_file": _path_signature,
}


def _hash_error(text: str) -> str:
    return hashlib.sha1(text[:200].encode("utf-8", "replace")).hexdigest()[:16]


@dataclass
class SignalEvaluator:
    repeated_threshold: int = 3
    error_threshold: int = 2
    common_clis_suppressed: list[str] = field(default_factory=list)
    cli_window_days: int = 30
    user_phrases: list[str] = field(default_factory=list)

    fired_signals: set[str] = field(default_factory=set)
    _tool_calls: deque = field(default_factory=lambda: deque(maxlen=20))
    _error_counts: dict[str, int] = field(default_factory=dict)
    _failed_clis: set[str] = field(default_factory=set)

    def observe_user_message(self, text: str) -> None:
        if not text:
            return
        lowered = text.lower()
        for phrase in self.user_phrases:
            if phrase and phrase.lower() in lowered:
                self.fired_signals.add("S3")
                return

    def observe_tool_call(
        self,
        tool_name: str,
        args: dict | None,
        *,
        success: bool | None = None,
    ) -> None:
        args = args or {}
        sig_fn = _PER_TOOL_SIG.get(tool_name)
        if sig_fn is not None:
            sig = sig_fn(args)
            if sig:
                self._tool_calls.append((tool_name, sig))
                count = sum(1 for name, seen_sig in self._tool_calls if name == tool_name and seen_sig == sig)
                if count >= self.repeated_threshold:
                    self.fired_signals.add("S1")

        if tool_name not in ("terminal", "process"):
            return

        cmd = str(args.get("command") or "").strip()
        if not cmd:
            return
        head = cmd.split()[0].rsplit("/", 1)[-1]
        if not head or head in self.common_clis_suppressed:
            return

        from agent import skill_usage_tracker

        if skill_usage_tracker.is_known_cli(head, window_days=self.cli_window_days):
            return

        if success is True or head in self._failed_clis:
            self.fired_signals.add("S2")
        if success is False:
            self._failed_clis.add(head)
        skill_usage_tracker.record_cli_seen(head)

    def observe_tool_result(self, tool_name: str, *, error_text: str | None) -> None:
        if error_text:
            h = _hash_error(error_text)
            self._error_counts[h] = self._error_counts.get(h, 0) + 1
            return

        for h, count in list(self._error_counts.items()):
            if count >= self.error_threshold:
                self.fired_signals.add("S4")
                self._error_counts.pop(h, None)

    def clear(self) -> None:
        self.fired_signals.clear()
        self._tool_calls.clear()
        self._error_counts.clear()
        self._failed_clis.clear()
