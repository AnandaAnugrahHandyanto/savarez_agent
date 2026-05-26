"""WhatsApp directory lookup helpers for gateway routing and memory scoping.

The directory is an optional deployment-local JSON file at
``$HERMES_HOME/whatsapp_directory.json``.  It maps WhatsApp contact/group JIDs
onto stable names, access roles, and memory paths.  Core Hermes must continue to
work without it, so every helper degrades to safe defaults when the file is
missing or malformed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from hermes_constants import get_hermes_home

from .whatsapp_identity import canonical_whatsapp_identifier, normalize_whatsapp_identifier

logger = logging.getLogger(__name__)

_WHATSAPP_DIRECTORY = "whatsapp_directory.json"

# Hard fallback for the existing Dalonic deployment.  The JSON directory is the
# source of truth when present; these aliases keep the old behavior if the file
# is absent, unreadable, or temporarily incomplete.
_FALLBACK_ADMIN_ALIASES = {
    "264720745512969@lid",  # nrjdalal / Neeraj DM in this bridge
    "919999373188@s.whatsapp.net",
    "919999373188",
    "nrjdalal",
}


def whatsapp_directory_path() -> Path:
    """Return the profile-local WhatsApp directory path."""

    return get_hermes_home() / _WHATSAPP_DIRECTORY


def load_whatsapp_directory() -> Dict[str, Any]:
    """Load ``$HERMES_HOME/whatsapp_directory.json`` if available.

    Returns an empty dict on absence or parse/read errors.  The gateway uses the
    directory for access hints and memory paths, but it is not required for a
    healthy Hermes install.
    """

    path = whatsapp_directory_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read WhatsApp directory %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _raw_aliases(value: str) -> set[str]:
    raw = (value or "").strip().lower()
    if not raw:
        return set()
    aliases = {raw}
    normalized = normalize_whatsapp_identifier(raw)
    if normalized:
        aliases.add(normalized.lower())
    try:
        canonical = canonical_whatsapp_identifier(raw)
    except Exception:
        canonical = ""
    if canonical:
        aliases.add(canonical.lower())
    return aliases


def _entry_aliases(entry: Dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("jid", "id", "phone", "display_name", "real_name"):
        value = entry.get(key)
        if isinstance(value, str):
            aliases.update(_raw_aliases(value))
    for key in ("aliases", "jids", "phones"):
        values = entry.get(key)
        if isinstance(values, Iterable) and not isinstance(values, (str, bytes, dict)):
            for value in values:
                if isinstance(value, str):
                    aliases.update(_raw_aliases(value))
    return aliases


def _lookup(kind: str, identifier: str) -> Optional[Dict[str, Any]]:
    data = load_whatsapp_directory()
    candidates = data.get(kind, [])
    if not isinstance(candidates, list):
        return None
    wanted = _raw_aliases(identifier)
    if not wanted:
        return None
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        if wanted & _entry_aliases(entry):
            return entry
    return None


def lookup_whatsapp_contact(identifier: str) -> Optional[Dict[str, Any]]:
    """Return a contact directory entry matching a WhatsApp user identifier."""

    return _lookup("contacts", identifier)


def lookup_whatsapp_group(identifier: str) -> Optional[Dict[str, Any]]:
    """Return a group directory entry matching a WhatsApp group identifier."""

    return _lookup("groups", identifier)


def is_whatsapp_admin(identifier: str) -> bool:
    """Return True when the identifier maps to an admin contact."""

    aliases = _raw_aliases(identifier)
    fallback = {alias.lower() for alias in _FALLBACK_ADMIN_ALIASES}
    if aliases & fallback:
        return True
    entry = lookup_whatsapp_contact(identifier)
    if not entry:
        return False
    return str(entry.get("access_role", "")).strip().lower() == "admin"


def _memory_parent_from_entry(entry: Dict[str, Any]) -> Optional[Path]:
    memory_path = entry.get("memory_path")
    if isinstance(memory_path, str) and memory_path.strip():
        path = Path(memory_path).expanduser()
        return path.parent if path.name else path
    return None


def contact_memory_dir(identifier: str, base: Path) -> Optional[Path]:
    """Return a directory-defined per-contact memory dir if present.

    Admin contacts return ``None`` so they stay on the profile root memory.
    """

    if is_whatsapp_admin(identifier):
        return None
    entry = lookup_whatsapp_contact(identifier)
    if not entry:
        return None
    return _memory_parent_from_entry(entry)


def group_memory_dir(identifier: str) -> Optional[Path]:
    """Return a directory-defined group memory dir if present."""

    entry = lookup_whatsapp_group(identifier)
    if not entry:
        return None
    return _memory_parent_from_entry(entry)


def whatsapp_context_lines(
    *,
    chat_id: str,
    user_id: str = "",
    include_contact: bool = True,
    redact_pii: bool = False,
) -> list[str]:
    """Build prompt-safe lines describing current WhatsApp directory matches."""

    lines: list[str] = []
    group_entry = lookup_whatsapp_group(chat_id) if chat_id.lower().endswith("@g.us") else None
    contact_identifier = user_id or chat_id
    contact_entry = lookup_whatsapp_contact(contact_identifier) if include_contact and contact_identifier else None

    if not group_entry and not contact_entry:
        return lines

    lines.append("")
    lines.append("**WhatsApp directory routing:**")
    if group_entry:
        name = group_entry.get("display_name") or group_entry.get("jid") or "current group"
        purpose = group_entry.get("purpose")
        access = group_entry.get("access_role")
        group_bits = [f"group={name}"]
        if access:
            group_bits.append(f"access_role={access}")
        if purpose:
            group_bits.append(f"purpose={purpose}")
        if not redact_pii and group_entry.get("memory_path"):
            group_bits.append(f"group_memory={group_entry['memory_path']}")
        lines.append("  - " + "; ".join(group_bits))
    if contact_entry:
        name = contact_entry.get("real_name") or contact_entry.get("display_name") or contact_entry.get("jid") or "current user"
        access = contact_entry.get("access_role")
        role = contact_entry.get("role")
        memory_scope = contact_entry.get("memory_scope")
        contact_bits = [f"user={name}"]
        if role:
            contact_bits.append(f"role={role}")
        if access:
            contact_bits.append(f"access_role={access}")
        if memory_scope:
            contact_bits.append(f"memory_scope={memory_scope}")
        if not redact_pii and contact_entry.get("memory_path"):
            contact_bits.append(f"user_memory={contact_entry['memory_path']}")
        lines.append("  - " + "; ".join(contact_bits))
    return lines
