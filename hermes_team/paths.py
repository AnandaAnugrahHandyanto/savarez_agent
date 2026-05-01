from __future__ import annotations

import os
from pathlib import Path


def get_hermes_home() -> Path:
    env = os.getenv("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home().joinpath(".hermes").resolve()


def get_team_state_dir() -> Path:
    """Return Hermes-native team state directory.

    All runtime team writes must live here under HERMES_HOME/state/team.
    """
    return get_hermes_home() / "state" / "team"


def ensure_team_state_dir() -> Path:
    path = get_team_state_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
