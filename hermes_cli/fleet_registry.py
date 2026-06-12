"""
Hermes Fleet — v2 registry loader.

Reads the fleet registry YAML (``~/DreBrain/…/registry.yaml``) and returns
structured profile records.  The registry is the routing source of truth for
the v2 3-layer architecture (orchestrators → executors → specialists).

Two parsing strategies:
  1. ``yaml.safe_load`` (preferred — richer types, structured fields).
  2. Regex fallback (when PyYAML is unavailable — partial-dependency envs).

Exports ``REGISTRY_PATH`` so other modules (e.g. fleet_watchdog) can refer to
the same canonical path.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical path to the fleet registry (v2 architecture definition).
# ---------------------------------------------------------------------------

REGISTRY_PATH = Path(
    os.path.expanduser(
        "~/DreBrain/DreBrain/30 - PROCEDURAL/fleet/registry.yaml"
    )
)

# ---------------------------------------------------------------------------
# Regex fallback — parses a single profile block from a YAML-like listing.
# We avoid depending on PyYAML in constrained environments.
# ---------------------------------------------------------------------------

# Matches ``- id: some-name`` and captures the name.
_RE_PROFILE_START = re.compile(r"^\s*-\s+id:\s*(.+)$")
# Matches ``  field_name: value`` and captures field + value.
_RE_FIELD = re.compile(r"^\s{2,}(\w[\w_]*):\s*(.*)$")
# Matches list items: ``  - item`` (2+ spaces + dash + space + content).
_RE_LIST_ITEM = re.compile(r"^\s{4,}-\s+(.+)$")


def _parse_registry_yaml(text: str) -> List[Dict[str, Any]]:
    """Parse registry YAML with a regex fallback (no PyYAML required)."""
    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    current_list_key: Optional[str] = None
    current_list: List[str] = []

    for line in text.splitlines():
        # Profile start
        m = _RE_PROFILE_START.match(line)
        if m:
            if current is not None:
                if current_list_key and current_list:
                    current[current_list_key] = current_list
                records.append(current)
            current = {"id": m.group(1).strip()}
            current_list_key = None
            current_list = []
            continue

        # Field line
        m = _RE_FIELD.match(line)
        if m and current is not None:
            # Flush any in-flight list
            if current_list_key and current_list:
                current[current_list_key] = current_list
                current_list_key = None
                current_list = []

            key = m.group(1)
            raw = m.group(2).strip()

            # Multi-line ">-" folded scalars — we store the first line;
            # subsequent indented lines are concatenated in _FOLDED_RE below.
            if raw.startswith(">-"):
                current[key] = raw[2:].strip()
            else:
                current[key] = raw

            # Detect list-bearing keys
            if key in ("boundaries", "escalation", "toolsets", "skills"):
                current[key] = []
                current_list_key = key
                current_list = current[key]  # type: ignore[assignment]
            continue

        # Continuation of a folded scalar (>-) — append to the last string field
        if current is not None and current_list_key is None:
            stripped = line.rstrip()
            if stripped and stripped.startswith("    "):
                # Find the last non-list key that got a string value
                for k in reversed(list(current.keys())):
                    if isinstance(current[k], str):
                        current[k] = current[k] + " " + stripped.strip()
                        break

        # List item
        m = _RE_LIST_ITEM.match(line)
        if m and current_list_key is not None and current is not None:
            current_list.append(m.group(1).strip())
            continue

    # Flush last profile
    if current is not None:
        if current_list_key and current_list:
            current[current_list_key] = current_list
        records.append(current)

    return records


def load_registry_records() -> List[Dict[str, Any]]:
    """Return all registry profile records as a list of dicts.

    Each record contains every field declared in the registry for that
    profile (``id``, ``layer``, ``domain``, ``purpose``, ``daemon``,
    ``parent``, ``toolsets``, ``skills``, ``models``, ``boundaries``,
    ``escalation``, ``schedule``, …).

    If the registry file is missing or unparseable, returns an empty list
    and logs the error.  Callers should check ``registry_parse_error()``
    to distinguish "empty registry" from "parse error".
    """
    global _parse_error_message
    _parse_error_message = None

    if not REGISTRY_PATH.is_file():
        _log.warning("Fleet registry not found at %s", REGISTRY_PATH)
        return []

    raw = REGISTRY_PATH.read_text(encoding="utf-8")

    # Strategy 1: PyYAML (preferred).
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        yaml = None  # type: ignore[assignment]

    if yaml is not None:
        try:
            data = yaml.safe_load(raw)
        except Exception as exc:
            _log.exception("Failed to parse fleet registry with YAML: %s", exc)
            _parse_error_message = str(exc)
            return []

        if not isinstance(data, dict):
            msg = "Fleet registry root is not a mapping"
            _log.warning(msg)
            _parse_error_message = msg
            return []

        profiles = data.get("profiles", [])
        if not isinstance(profiles, list):
            msg = "Fleet registry 'profiles' key is not a list"
            _log.warning(msg)
            _parse_error_message = msg
            return []

        records: List[Dict[str, Any]] = []
        for entry in profiles:
            if not isinstance(entry, dict):
                continue
            record = dict(entry)
            # Normalise ``id`` to ``name`` for downstream consumers.
            if "id" in record:
                record["name"] = record.pop("id")
            records.append(record)
        return records

    # Strategy 2: regex fallback.
    try:
        records = _parse_registry_yaml(raw)
        # Normalise ``id`` → ``name``.
        for r in records:
            if "id" in r:
                r["name"] = r.pop("id")
        return records
    except Exception as exc:
        _log.exception("Failed to parse fleet registry with regex: %s", exc)
        _parse_error_message = str(exc)
        return []


# Module-level parse error — set by load_registry_records() when YAML parsing
# fails (as opposed to the file simply not existing or being empty).
_parse_error_message: Optional[str] = None


def registry_parse_error() -> Optional[str]:
    """Return the last parse error message, or None if the last load was
    successful (even if the registry was empty)."""
    return _parse_error_message
