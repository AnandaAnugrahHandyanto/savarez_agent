"""Historic model selections store for the /model picker recents section.

Tracks successful model switches so the picker can surface recently
used models above the full provider list.  Storage is a JSON file in
the Hermes home directory (profile-aware via ``get_hermes_home()``).

Schema (``model_recents.json``)::

    {
        "version": 1,
        "recents": [
            {
                "provider": "ollama-launch",
                "model": "qwen3.6:35b-a3b-mlx-bf16",
                "last_used": "2026-05-07T13:40:00Z",
                "count": 12
            },
            ...
        ]
    }

Entries are ordered by ``last_used`` descending (most recent first).
The dedup key is ``provider:model`` — re-selecting a model bumps its
timestamp and count rather than creating a duplicate.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STORE_FILENAME = "model_recents.json"
_MAX_STORED = 20  # hard cap on stored entries (never grows unboundedly)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _store_path() -> Path:
    """Resolve the full path to the recents store file (profile-aware)."""
    return get_hermes_home() / _STORE_FILENAME


def _time_iso() -> str:
    """Current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _read_store() -> dict[str, Any]:
    """Read the store file, returning a clean empty structure on any error.

    Tolerates: missing file, invalid JSON, wrong version number, wrong
    top-level type.  Returns ``{"version": 1, "recents": []}`` on failure
    so callers always get a sane structure.
    """
    path = _store_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"version": 1, "recents": []}
    except OSError as exc:
        logger.debug("model_recents: failed to read %s: %s", path, exc)
        return {"version": 1, "recents": []}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("model_recents: corrupt JSON in %s, resetting: %s", path, exc)
        return {"version": 1, "recents": []}

    if not isinstance(data, dict):
        logger.warning("model_recents: store is not a dict, resetting")
        return {"version": 1, "recents": []}

    version = data.get("version")
    if version != 1:
        logger.warning(
            "model_recents: unknown version %r, resetting", version
        )
        return {"version": 1, "recents": []}

    recents = data.get("recents", [])
    if not isinstance(recents, list):
        logger.warning("model_recents: recents is not a list, resetting")
        return {"version": 1, "recents": []}

    return data


def _write_store(data: dict[str, Any]) -> None:
    """Atomically write the store file (tempfile + rename)."""
    path = _store_path()
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        # Atomic: write to temp then rename
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=".model_recents_", suffix=".tmp"
        )
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except OSError as exc:
        logger.debug("model_recents: failed to write %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_model_selection(provider: str, model: str) -> None:
    """Record a successful model switch in the recents store.

    If the provider:model pair already exists, it is moved to the front
    and its ``last_used`` / ``count`` are updated.  The store is capped
    at ``_MAX_STORED`` entries (oldest entries beyond the cap are dropped).

    Args:
        provider: The Hermes provider slug (e.g. ``"ollama-launch"``,
            ``"openrouter"``, ``"custom:my-endpoint"``).
        model: The model identifier as stored/displayed (e.g.
            ``"qwen3.6:35b-a3b-mlx-bf16"``, ``"claude-sonnet-4"``).
    """
    data = _read_store()
    recents: list[dict[str, Any]] = data["recents"]
    # Dedup key is provider:model
    now = _time_iso()

    # Find existing entry
    existing_idx: int | None = None
    for i, entry in enumerate(recents):
        if isinstance(entry, dict) and entry.get("provider") == provider and entry.get("model") == model:
            existing_idx = i
            break

    if existing_idx is not None:
        # Bump: update timestamp + count, move to front
        entry = recents.pop(existing_idx)
        entry["last_used"] = now
        entry["count"] = entry.get("count", 1) + 1
        recents.insert(0, entry)
    else:
        # New entry at front
        recents.insert(
            0,
            {
                "provider": provider,
                "model": model,
                "last_used": now,
                "count": 1,
            },
        )

    # Cap to _MAX_STORED
    del recents[_MAX_STORED:]

    data["recents"] = recents
    _write_store(data)


def load_recent_models(limit: int = 8) -> list[dict[str, Any]]:
    """Load the N most recent model selections.

    Returns a list of ``{"provider": str, "model": str, "last_used": str,
    "count": int}`` dicts, ordered by ``last_used`` descending.  Always
    returns a list (empty on any error).

    Args:
        limit: Maximum number of entries to return (default 8).
    """
    data = _read_store()
    recents: list[dict[str, Any]] = data.get("recents", [])
    # Filter out any entries that aren't proper dicts (defensive)
    clean: list[dict[str, Any]] = []
    for entry in recents[:limit]:
        if isinstance(entry, dict) and "provider" in entry and "model" in entry:
            clean.append(entry)
        if len(clean) >= limit:
            break
    return clean


def clear_recent_models() -> None:
    """Delete the recents store file entirely (resets all history)."""
    path = _store_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
