"""Shared file safety rules used by both tools and ACP shims."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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


def get_read_block_error(path: str) -> Optional[str]:
    """Return an error message when a read targets internal Hermes cache files."""
    resolved = Path(path).expanduser().resolve()
    hermes_home = _hermes_home_path().resolve()
    blocked_dirs = [
        hermes_home / "skills" / ".hub" / "index-cache",
        hermes_home / "skills" / ".hub",
    ]
    for blocked in blocked_dirs:
        try:
            resolved.relative_to(blocked)
        except ValueError:
            continue
        return (
            f"Access denied: {path} is an internal Hermes cache file "
            "and cannot be read directly to prevent prompt injection. "
            "Use the skills_list or skill_view tools instead."
        )
    return None


# Well-known system directories that must never be chmod'd.
_UNSAFE_PARENT_DIRS: frozenset[str] = frozenset({
    "/", "/etc", "/usr", "/var", "/sys", "/proc", "/boot",
    "/dev", "/bin", "/sbin", "/lib", "/lib64", "/opt", "/root",
})


def safe_chmod_parent(path: Path | str, mode: int = 0o700) -> None:
    """chmod ``path.parent`` only after verifying it is a sane directory.

    Prevents ``os.chmod(\"/\", 0o700)`` which strips traversal permission
    from the root inode and bricks the entire host (DNS, networking,
    journald, Docker, etc.).  See issue #25821.

    Checks (any failure → skip with warning, no exception raised):
      1. Resolved parent is not ``/`` or a well-known system directory.
      2. Parent exists and is a directory.
    """
    try:
        parent = Path(path).resolve().parent
    except Exception:
        logger.warning("safe_chmod_parent: cannot resolve parent of %r", path)
        return

    parent_str = str(parent)

    # Check 1: not root or a well-known system directory
    if parent_str in _UNSAFE_PARENT_DIRS:
        logger.warning(
            "safe_chmod_parent: refusing to chmod system directory %s "
            "(path=%r) — see #25821", parent_str, str(path),
        )
        return

    # Check 2: parent exists and is a directory
    if not parent.is_dir():
        logger.warning(
            "safe_chmod_parent: parent %s does not exist or is not a directory "
            "(path=%r) — skipping chmod", parent_str, str(path),
        )
        return

    try:
        os.chmod(parent, mode)
    except OSError:
        # Silently ignore — some filesystems (e.g. Windows mounts) don't support chmod
        pass
