"""Helpers for persisting and restoring session workspace context."""

import os
from pathlib import Path
from typing import Any, Dict, Optional


def current_session_workspace_metadata() -> Dict[str, str]:
    """Return workspace metadata for a newly-created session row."""
    cwd = os.getenv("TERMINAL_CWD") or os.getcwd()
    return {
        "workspace_path": cwd,
        "last_cwd": cwd,
    }


def restore_terminal_cwd_from_session(session_meta: Optional[Dict[str, Any]]) -> Optional[str]:
    """Restore TERMINAL_CWD from session metadata.

    Local sessions only restore paths that still exist on disk. Non-local
    backends may use sandbox paths that the host cannot validate, so they are
    allowed through and left for terminal_tool's backend-specific guards.
    """
    if not session_meta:
        return None

    raw_cwd = session_meta.get("last_cwd") or session_meta.get("workspace_path")
    if not isinstance(raw_cwd, str) or not raw_cwd.strip():
        return None

    cwd = raw_cwd.strip()
    backend = os.getenv("TERMINAL_ENV", "local").strip().lower() or "local"
    if backend == "local":
        candidate = Path(cwd).expanduser()
        if not candidate.is_absolute() or not candidate.is_dir():
            return None
        cwd = str(candidate)

    os.environ["TERMINAL_CWD"] = cwd
    return cwd
