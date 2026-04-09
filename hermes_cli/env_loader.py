"""Helpers for loading Hermes .env files consistently across entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

import dotenv  # Resolve .load_dotenv at call time — NOT via `from dotenv import load_dotenv`.
# Rationale: a `from` import captures whatever `dotenv.load_dotenv` points to AT
# IMPORT TIME.  If this module is imported while a test has `patch("dotenv.load_dotenv")`
# active, our binding gets stuck on the MagicMock forever — long after the patch
# context exits.  Calling `dotenv.load_dotenv(...)` each time resolves against
# the current module attribute and is stable across patches.


def _load_dotenv_with_fallback(path: Path, *, override: bool) -> None:
    try:
        dotenv.load_dotenv(dotenv_path=path, override=override, encoding="utf-8")
    except UnicodeDecodeError:
        dotenv.load_dotenv(dotenv_path=path, override=override, encoding="latin-1")


def load_hermes_dotenv(
    *,
    hermes_home: str | os.PathLike | None = None,
    project_env: str | os.PathLike | None = None,
) -> list[Path]:
    """Load Hermes environment files with user config taking precedence.

    Behavior:
    - `~/.hermes/.env` overrides stale shell-exported values when present.
    - project `.env` acts as a dev fallback and only fills missing values when
      the user env exists.
    - if no user env exists, the project `.env` also overrides stale shell vars.
    """
    loaded: list[Path] = []

    home_path = Path(hermes_home or os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    user_env = home_path / ".env"
    project_env_path = Path(project_env) if project_env else None

    if user_env.exists():
        _load_dotenv_with_fallback(user_env, override=True)
        loaded.append(user_env)

    if project_env_path and project_env_path.exists():
        _load_dotenv_with_fallback(project_env_path, override=not loaded)
        loaded.append(project_env_path)

    return loaded
