"""Hardened JSON writer for OAuth credentials and similar local secrets.

OAuth credential files (Google Workspace ``client_secret.json``,
``google_token.json``, the Google Chat per-user tokens, etc.) must never
live at world-readable mode, even briefly. ``Path.write_text`` opens at
the process umask — typically ``0o644`` — and never chmods the result,
so token files briefly exist at world-readable mode while OAuth refresh
tokens are inside. Refresh tokens are long-lived secrets; on a shared
host any local user can ``cat`` them before the writing process tightens
the mode (TOCTOU window).

This module exposes a single helper that the matching call sites are
expected to migrate to:

    from agent.secure_file_io import write_secret_json
    write_secret_json(path, payload)

Contract pinned by ``tests/agent/test_secure_file_io.py``:
  * The final file lands at mode ``0o600`` (owner read+write, no
    group/other).
  * The parent directory ends at mode ``0o700``.
  * The write is atomic: ``O_EXCL`` tmp file + ``fsync`` + ``os.replace``.
    A partial-write crash leaves either the previous contents or no
    file at all — never a half-written secret.
  * On Windows (and exotic FUSE / Samba mounts that don't honor POSIX
    mode bits) the chmod operations are best-effort no-ops, suppressed
    via ``(OSError, NotImplementedError)``.

Mirrors the existing safe idiom around ``agent.google_oauth.save_credentials``;
that helper is updated to use the same ``(OSError, NotImplementedError)``
guard so the two share one Windows-no-op contract.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any, Mapping

__all__ = ["write_secret_json"]


# Wrapping permission-sensitive ops in ``(OSError, NotImplementedError)``
# keeps Windows (and FUSE / Samba mounts that don't honor POSIX mode bits)
# as a silent no-op rather than spuriously raising at the call site. Some
# Python stdlib paths (``os.fchmod`` on certain platforms) raise
# ``NotImplementedError`` rather than ``OSError``, so we catch both.
_PERM_ERRORS = (OSError, NotImplementedError)


def _silent_chmod(path: Path, mode: int) -> None:
    """Best-effort chmod — silently ignored on non-POSIX platforms."""
    try:
        os.chmod(path, mode)
    except _PERM_ERRORS:
        pass


def write_secret_json(path: Path, payload: Mapping[str, Any]) -> Path:
    """Atomically write *payload* as JSON to *path* with secret-safe perms.

    Order of operations:
      1. ``mkdir(parents=True, exist_ok=True)`` the parent dir.
      2. Tighten the parent dir to ``0o700`` (best-effort; no-op on Windows).
      3. ``os.open`` an ``O_EXCL`` sibling tmp file with mode ``0o600`` so
         the secret never exists at the umask-derived ``0o644``.
      4. Write the JSON payload, ``flush`` + ``fsync``.
      5. ``os.replace`` the tmp file onto *path* (atomic on POSIX/Windows).
      6. ``chmod`` the final path back to ``0o600`` in case ``os.replace``
         lost mode bits across an inode swap or a symlink target.

    On any failure mid-write the tmp sibling is unlinked, so a partial-
    write crash leaves either the previous contents or no file at all.
    """
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    _silent_chmod(parent, 0o700)

    body = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    tmp_path = path.with_suffix(
        f"{path.suffix}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    )

    try:
        fd = os.open(
            str(tmp_path),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            stat.S_IRUSR | stat.S_IWUSR,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(path))
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

    _silent_chmod(path, 0o600)
    return path
