"""No-op replacements for gateway.status (standalone bridge)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def write_runtime_status(
    *,
    platform: str,
    platform_state: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Hermes gateway writes PID/runtime files; standalone build skips this."""
    return None


def acquire_scoped_lock(
    scope: str,
    identity: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Always succeed — no multi-process token arbitration in standalone mode."""
    return True, None


def release_scoped_lock(scope: str, identity: str) -> None:
    return None
