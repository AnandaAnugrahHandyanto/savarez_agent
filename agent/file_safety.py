"""Shared file safety rules used by both tools and ACP shims."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _hermes_home_path() -> Path:
    """Resolve the active HERMES_HOME (profile-aware) without circular imports."""
    try:
        from hermes_constants import get_hermes_home  # local import to avoid cycles
        return get_hermes_home()
    except Exception:
        return Path(os.path.expanduser("~/.hermes"))


def build_write_denied_paths(home: str) -> set[str]:
    """Return exact sensitive paths that must never be written."""
    hermes_home = _hermes_home_path()
    return {
        os.path.realpath(p)
        for p in [
            os.path.join(home, ".ssh", "authorized_keys"),
            os.path.join(home, ".ssh", "id_rsa"),
            os.path.join(home, ".ssh", "id_ed25519"),
            os.path.join(home, ".ssh", "config"),
            str(hermes_home / ".env"),
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".profile"),
            os.path.join(home, ".bash_profile"),
            os.path.join(home, ".zprofile"),
            os.path.join(home, ".netrc"),
            os.path.join(home, ".pgpass"),
            os.path.join(home, ".npmrc"),
            os.path.join(home, ".pypirc"),
            "/etc/sudoers",
            "/etc/passwd",
            "/etc/shadow",
        ]
    }


def build_write_denied_prefixes(home: str) -> list[str]:
    """Return sensitive directory prefixes that must never be written."""
    return [
        os.path.realpath(p) + os.sep
        for p in [
            os.path.join(home, ".ssh"),
            os.path.join(home, ".aws"),
            os.path.join(home, ".gnupg"),
            os.path.join(home, ".kube"),
            "/etc/sudoers.d",
            "/etc/systemd",
            os.path.join(home, ".docker"),
            os.path.join(home, ".azure"),
            os.path.join(home, ".config", "gh"),
        ]
    ]


def get_safe_write_root() -> Optional[str]:
    """Return the resolved HERMES_WRITE_SAFE_ROOT path, or None if unset."""
    root = os.getenv("HERMES_WRITE_SAFE_ROOT", "")
    if not root:
        return None
    try:
        return os.path.realpath(os.path.expanduser(root))
    except Exception:
        return None


def is_write_denied(path: str) -> bool:
    """Return True if path is blocked by the write denylist or safe root."""
    home = os.path.realpath(os.path.expanduser("~"))
    resolved = os.path.realpath(os.path.expanduser(str(path)))

    if resolved in build_write_denied_paths(home):
        return True
    for prefix in build_write_denied_prefixes(home):
        if resolved.startswith(prefix):
            return True

    safe_root = get_safe_write_root()
    if safe_root and not (resolved == safe_root or resolved.startswith(safe_root + os.sep)):
        return True

    return False


def get_read_safe_roots() -> list[str]:
    """Return resolved HERMES_READ_SAFE_ROOTS allowlist (colon-separated), or []."""
    raw = os.getenv("HERMES_READ_SAFE_ROOTS", "")
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split(":"):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(os.path.realpath(os.path.expanduser(part)))
        except Exception:
            continue
    return out


def get_read_allowed_files() -> set[str]:
    """Return resolved HERMES_READ_ALLOWED_FILES (colon-separated explicit paths).

    Use for individual files outside the safe-roots that must remain readable
    (e.g. ~/.hermes/AGENTS.md, ~/.hermes/SOUL.md).
    """
    raw = os.getenv("HERMES_READ_ALLOWED_FILES", "")
    if not raw:
        return set()
    out: set[str] = set()
    for part in raw.split(":"):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(os.path.realpath(os.path.expanduser(part)))
        except Exception:
            continue
    return out


def get_read_block_error(path: str) -> Optional[str]:
    """Return an error message when a read is denied.

    Two layers:
      1. Internal Hermes cache files (skills/.hub) — always blocked to
         prevent prompt-injection via catalog/hub metadata.
      2. HERMES_READ_SAFE_ROOTS allowlist (colon-separated). When set, any
         read outside those roots (and outside HERMES_READ_ALLOWED_FILES)
         is denied. Mirrors HERMES_WRITE_SAFE_ROOT for write-side scoping.
    """
    resolved_pathobj = Path(path).expanduser().resolve()
    resolved = str(resolved_pathobj)
    hermes_home = _hermes_home_path().resolve()
    blocked_dirs = [
        hermes_home / "skills" / ".hub" / "index-cache",
        hermes_home / "skills" / ".hub",
    ]
    for blocked in blocked_dirs:
        try:
            resolved_pathobj.relative_to(blocked)
        except ValueError:
            continue
        return (
            f"Access denied: {path} is an internal Hermes cache file "
            "and cannot be read directly to prevent prompt injection. "
            "Use the skills_list or skill_view tools instead."
        )

    safe_roots = get_read_safe_roots()
    if safe_roots:
        allowed_files = get_read_allowed_files()
        if resolved in allowed_files:
            return None
        for root in safe_roots:
            if resolved == root or resolved.startswith(root + os.sep):
                return None
        return (
            f"Access denied: {path} is outside the configured read allowlist "
            f"(HERMES_READ_SAFE_ROOTS). Allowed roots: {', '.join(safe_roots)}. "
            "Set HERMES_READ_ALLOWED_FILES to whitelist specific files."
        )

    return None
