"""Session Notes — Automatic tracking of important observations per session.

Creates a human-readable .txt file alongside each session that logs:
- User prompts (summarized)
- Key decisions made
- Tools used and outcomes
- Errors encountered
- Files modified
- Important findings

The notes file is written incrementally after each turn, so you can
monitor progress in real-time by tailing the file.

Usage:
    from agent.session_notes import SessionNotesTracker
    tracker = SessionNotesTracker(session_id, logs_dir)
    tracker.log_turn(user_message, assistant_response, tool_calls, errors)
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionNotesTracker:
    """Tracks important observations for a session in a human-readable txt file."""

    def __init__(self, session_id: str, logs_dir: Path, model: str = ""):
        self.session_id = session_id
        self.logs_dir = Path(logs_dir)
        self.model = model
        self.notes_file = self.logs_dir / f"notes_{session_id}.txt"
        self.turn_count = 0
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Write the session header on first use."""
        if self._initialized:
            return
        self._initialized = True
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        header = [
            "=" * 72,
            f"SESSION NOTES: {self.session_id}",
            f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Model: {self.model}" if self.model else "",
            "=" * 72,
            "",
        ]
        self._write_lines([line for line in header if line or line == ""])

    def _write_lines(self, lines: List[str]) -> None:
        """Append lines to the notes file."""
        try:
            with open(self.notes_file, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
        except Exception as e:
            logger.debug("Failed to write session notes: %s", e)

    def _summarize_message(self, text: str, max_len: int = 100) -> str:
        """Create a brief summary of a message."""
        if not text:
            return "(empty)"
        # Remove code blocks for summary
        text = re.sub(r'```[\s\S]*?```', '[code]', text)
        # Collapse whitespace
        text = ' '.join(text.split())
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text

    def _extract_tool_summary(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """Extract a summary of tool calls."""
        if not tool_calls:
            return []
        
        summaries = []
        for tc in tool_calls:
            name = tc.get("name", tc.get("function", {}).get("name", "unknown"))
            args = tc.get("args", tc.get("function", {}).get("arguments", {}))
            
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            
            # Extract key info based on tool type
            if name == "terminal":
                cmd = args.get("command", "")[:60]
                summaries.append(f"  → terminal: {cmd}")
            elif name in ("read_file", "write_file", "patch"):
                path = args.get("path", "")
                summaries.append(f"  → {name}: {path}")
            elif name == "web_search":
                query = args.get("query", "")[:40]
                summaries.append(f"  → search: {query}")
            elif name == "delegate_task":
                goal = args.get("goal", "")[:50]
                summaries.append(f"  → delegate: {goal}")
            else:
                summaries.append(f"  → {name}")
        
        return summaries

    def _extract_files_modified(self, tool_calls: List[Dict[str, Any]], results: List[str] = None) -> List[str]:
        """Extract list of files that were modified."""
        files = set()
        for tc in tool_calls:
            name = tc.get("name", tc.get("function", {}).get("name", ""))
            args = tc.get("args", tc.get("function", {}).get("arguments", {}))
            
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            
            if name in ("write_file", "patch") and args.get("path"):
                files.add(args["path"])
        
        return sorted(files)

    def _extract_errors(self, results: List[str]) -> List[str]:
        """Extract any errors from tool results."""
        errors = []
        for result in (results or []):
            if not result:
                continue
            try:
                data = json.loads(result) if isinstance(result, str) else result
                if isinstance(data, dict):
                    if data.get("error"):
                        errors.append(f"  ⚠ {data['error'][:80]}")
                    elif data.get("exit_code") and data["exit_code"] != 0:
                        errors.append(f"  ⚠ Command failed (exit {data['exit_code']})")
            except Exception:
                if "error" in str(result).lower()[:100]:
                    errors.append(f"  ⚠ {str(result)[:80]}")
        return errors

    def _extract_key_findings(self, assistant_response: str) -> List[str]:
        """Extract key findings/decisions from the assistant response."""
        findings = []
        
        # Look for decision patterns
        patterns = [
            (r"(?:I'll|I will|Going to|Decided to|Choosing to)\s+(.{20,80}?)(?:\.|$)", "Decision"),
            (r"(?:Found|Discovered|Noticed|Identified)\s+(.{20,80}?)(?:\.|$)", "Finding"),
            (r"(?:Fixed|Resolved|Corrected|Updated)\s+(.{20,80}?)(?:\.|$)", "Fixed"),
            (r"(?:Error|Bug|Issue|Problem):\s*(.{20,80}?)(?:\.|$)", "Issue"),
            (r"(?:Created|Added|Implemented)\s+(.{20,80}?)(?:\.|$)", "Created"),
        ]
        
        for pattern, label in patterns:
            matches = re.findall(pattern, assistant_response, re.IGNORECASE)
            for match in matches[:2]:  # Max 2 per category
                clean = ' '.join(match.split())
                if len(clean) > 15:  # Skip very short matches
                    findings.append(f"  • [{label}] {clean}")
        
        return findings[:5]  # Max 5 findings per turn

    def log_turn(
        self,
        user_message: str,
        assistant_response: str,
        tool_calls: List[Dict[str, Any]] = None,
        tool_results: List[str] = None,
        duration_seconds: float = None,
        tokens_used: int = None,
    ) -> None:
        """Log a conversation turn to the notes file."""
        self._ensure_initialized()
        self.turn_count += 1
        
        lines = [
            "-" * 72,
            f"TURN {self.turn_count} | {datetime.now().strftime('%H:%M:%S')}",
            "-" * 72,
            "",
        ]
        
        # User prompt (summarized)
        user_summary = self._summarize_message(user_message, 120)
        lines.append(f"USER: {user_summary}")
        lines.append("")
        
        # Tools used
        tool_summaries = self._extract_tool_summary(tool_calls or [])
        if tool_summaries:
            lines.append("TOOLS:")
            lines.extend(tool_summaries)
            lines.append("")
        
        # Files modified
        files = self._extract_files_modified(tool_calls or [])
        if files:
            lines.append("FILES MODIFIED:")
            for f in files[:10]:
                lines.append(f"  • {f}")
            lines.append("")
        
        # Errors
        errors = self._extract_errors(tool_results)
        if errors:
            lines.append("ERRORS:")
            lines.extend(errors)
            lines.append("")
        
        # Key findings from response
        findings = self._extract_key_findings(assistant_response or "")
        if findings:
            lines.append("KEY OBSERVATIONS:")
            lines.extend(findings)
            lines.append("")
        
        # Response summary
        response_summary = self._summarize_message(assistant_response, 200)
        lines.append(f"RESPONSE: {response_summary}")
        
        # Stats
        stats_parts = []
        if tool_calls:
            stats_parts.append(f"{len(tool_calls)} tools")
        if duration_seconds:
            stats_parts.append(f"{duration_seconds:.1f}s")
        if tokens_used:
            stats_parts.append(f"~{tokens_used} tokens")
        if stats_parts:
            lines.append(f"STATS: {' | '.join(stats_parts)}")
        
        lines.append("")
        self._write_lines(lines)

    def log_event(self, event_type: str, message: str) -> None:
        """Log a standalone event (compression, error, etc.)."""
        self._ensure_initialized()
        lines = [
            f"[{datetime.now().strftime('%H:%M:%S')}] {event_type.upper()}: {message}",
            "",
        ]
        self._write_lines(lines)

    def log_session_end(self, reason: str = "completed", total_turns: int = None) -> None:
        """Log session end summary."""
        self._ensure_initialized()
        lines = [
            "=" * 72,
            f"SESSION ENDED: {reason.upper()}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total turns: {total_turns or self.turn_count}",
            "=" * 72,
        ]
        self._write_lines(lines)


# Module-level convenience for getting tracker from session
_active_trackers: Dict[str, SessionNotesTracker] = {}


def get_session_tracker(session_id: str, logs_dir: Path = None, model: str = "") -> SessionNotesTracker:
    """Get or create a session notes tracker."""
    if session_id not in _active_trackers:
        if logs_dir is None:
            from hermes_constants import get_hermes_home
            logs_dir = get_hermes_home() / "sessions"
        _active_trackers[session_id] = SessionNotesTracker(session_id, logs_dir, model)
    return _active_trackers[session_id]


def cleanup_tracker(session_id: str) -> None:
    """Remove a tracker from the active set."""
    _active_trackers.pop(session_id, None)
