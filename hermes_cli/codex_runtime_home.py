"""CODEX_HOME resolution for Hermes' Codex app-server runtime.

Hermes writes runtime-managed Codex config into an isolated directory by
default so enabling the runtime cannot corrupt the user's global ~/.codex
config. Users can still opt into a shared Codex home with CODEX_HOME or a
runtime-specific override with HERMES_CODEX_HOME.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union


PathLike = Union[str, os.PathLike[str], Path]


def default_codex_runtime_home() -> Path:
    """Return Hermes' isolated default Codex home."""
    hermes_home = os.getenv("HERMES_HOME", "").strip()
    base = Path(hermes_home).expanduser() if hermes_home else Path.home() / ".hermes"
    return base / "codex-runtime"


def resolve_codex_runtime_home(explicit: Optional[PathLike] = None) -> Path:
    """Resolve the Codex home used by Hermes' app-server runtime.

    Precedence:
      1. Explicit caller override.
      2. HERMES_CODEX_HOME, for runtime-specific isolation.
      3. CODEX_HOME, for users who intentionally share Codex CLI state.
      4. <HERMES_HOME or ~/.hermes>/codex-runtime.
    """
    if explicit is not None:
        return Path(explicit).expanduser()
    for env_name in ("HERMES_CODEX_HOME", "CODEX_HOME"):
        raw = os.getenv(env_name, "").strip()
        if raw:
            return Path(raw).expanduser()
    return default_codex_runtime_home()
