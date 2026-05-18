"""Resolve OpenClaw config/state paths for Hermes-native tooling."""

from __future__ import annotations

import os
from pathlib import Path

from hermes_constants import get_hermes_home


def default_openclaw_config_path() -> Path:
    """OpenClaw main config (openclaw.json), with env/profile overrides."""
    override = os.environ.get("OPENCLAW_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()

    home = Path.home()
    candidates = [
        home / ".openclaw" / "openclaw.json",
        get_hermes_home() / "openclaw" / "openclaw.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def default_openclaw_state_root() -> Path:
    """Directory containing credentials/ and agents/ session stores."""
    override = os.environ.get("OPENCLAW_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return default_openclaw_config_path().parent
