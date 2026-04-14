"""Helpers for loading Hermes .env files consistently across entrypoints."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path, *, encoding: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding=encoding).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value
    return values


def _load_dotenv_with_fallback(path: Path, *, override: bool) -> None:
    """Load env vars from *path* even when ``PYTHON_DOTENV_DISABLED=1`` is set.

    ``load_dotenv()`` respects ``PYTHON_DOTENV_DISABLED`` and becomes a no-op.
    Hermes uses ``.env`` files as explicit user configuration, so this helper
    parses the file directly and applies precedence itself.
    """
    try:
        values = _parse_env_file(path, encoding="utf-8")
    except UnicodeDecodeError:
        values = _parse_env_file(path, encoding="latin-1")

    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value


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
