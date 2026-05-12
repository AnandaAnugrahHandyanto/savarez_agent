"""RED tests for ``agent.secure_file_io.write_secret_json``.

Background
==========
OAuth credential files (Google Workspace ``client_secret.json``,
``google_token.json``, the Google Chat per-user tokens, etc.) are
currently written with ``Path.write_text`` from a handful of scattered
sites. ``Path.write_text`` opens at the process umask — typically
``0o644`` — and never chmods the result, so the token files briefly
exist at world-readable mode while OAuth refresh tokens are inside.
Refresh tokens are long-lived secrets; on a shared host, any local user
can ``cat`` them before the writing process tightens the mode.

We're consolidating the fix behind a single helper that the matching
GREEN commit will introduce:

    from agent.secure_file_io import write_secret_json
    write_secret_json(path, payload)

The contract these tests pin:
  * The file ends at mode ``0o600`` (owner read+write, no group/other).
  * The parent directory ends at mode ``0o700``.
  * The write is atomic: a partial-write failure must leave either the
    previous contents or no file — never a half-written secret on disk.

The module ``agent/secure_file_io.py`` does NOT exist yet — these
tests are deliberately RED until the GREEN commit lands both the
helper and the call-site migrations. The failure mode is ``ImportError``
inside each test body (kept out of module scope so collection still
succeeds and readable diagnostics survive).

POSIX-only — Windows does not enforce POSIX mode bits.

Mirrors:
  * ``tests/cron/test_file_permissions.py``
  * ``tests/hermes_cli/test_auth_toctou_file_modes.py``
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX mode bits not enforced on Windows",
)


# ---------------------------------------------------------------------------
# File mode: 0o600
# ---------------------------------------------------------------------------


def test_write_secret_json_writes_file_at_0o600(tmp_path):
    """``write_secret_json`` must land the file at ``0o600`` under any umask."""
    # Force a permissive umask that would otherwise leave the file at 0o644.
    old_umask = os.umask(0o022)
    try:
        from agent.secure_file_io import write_secret_json

        target = tmp_path / "secrets" / "token.json"
        write_secret_json(target, {"refresh_token": "rt-xyz", "access_token": "at-xyz"})
    finally:
        os.umask(old_umask)

    assert target.exists(), "write_secret_json must create the target file"
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, (
        f"secret file mode 0o{mode:o} != 0o600 — umask would expose tokens"
    )

    # Content preserved.
    payload = json.loads(target.read_text())
    assert payload["refresh_token"] == "rt-xyz"
    assert payload["access_token"] == "at-xyz"


# ---------------------------------------------------------------------------
# Parent directory mode: 0o700
# ---------------------------------------------------------------------------


def test_write_secret_json_tightens_parent_dir_to_0o700(tmp_path):
    """The parent dir must end at ``0o700`` so siblings can't traverse to it."""
    old_umask = os.umask(0o022)
    try:
        from agent.secure_file_io import write_secret_json

        # Parent dir does not exist yet; helper must create it at 0o700.
        target = tmp_path / "creds_dir" / "token.json"
        write_secret_json(target, {"k": "v"})
    finally:
        os.umask(old_umask)

    parent_mode = stat.S_IMODE(target.parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"parent dir mode 0o{parent_mode:o} != 0o700 — other users can traverse"
    )


def test_write_secret_json_retightens_existing_parent_dir(tmp_path):
    """If parent dir already exists at a looser mode, the helper must tighten it."""
    parent = tmp_path / "loose_parent"
    parent.mkdir(mode=0o755)
    os.chmod(parent, 0o755)  # ensure 0o755 regardless of umask

    old_umask = os.umask(0o022)
    try:
        from agent.secure_file_io import write_secret_json

        target = parent / "token.json"
        write_secret_json(target, {"k": "v"})
    finally:
        os.umask(old_umask)

    parent_mode = stat.S_IMODE(parent.stat().st_mode)
    assert parent_mode == 0o700, (
        f"existing parent dir was not retightened: mode 0o{parent_mode:o} != 0o700"
    )


# ---------------------------------------------------------------------------
# Atomicity: partial-write must not corrupt the on-disk file
# ---------------------------------------------------------------------------


def test_write_secret_json_is_atomic_under_partial_write(tmp_path):
    """A failure mid-write must leave the previous contents intact.

    Atomic writers use ``os.open(O_EXCL, 0o600)`` + ``fsync`` + ``os.replace``
    so the target file is either the previous version or the complete new
    version — never a half-written secret. We simulate a partial-write
    crash by making ``os.fsync`` raise; the previous file contents must
    survive untouched.
    """
    target = tmp_path / "token.json"
    target.write_text(json.dumps({"refresh_token": "prior-secret"}))
    os.chmod(target, 0o600)

    real_fsync = os.fsync

    def exploding_fsync(fd):
        # Raise BEFORE the atomic replace lands so a non-atomic writer
        # would either truncate the target or leave a tmp file behind.
        raise OSError("simulated partial-write failure (disk full)")

    old_umask = os.umask(0o022)
    try:
        from agent.secure_file_io import write_secret_json

        with patch.object(os, "fsync", exploding_fsync):
            with pytest.raises(OSError):
                write_secret_json(target, {"refresh_token": "new-secret-NEVER-LANDED"})
    finally:
        os.umask(old_umask)
        # Restore in case the patch leaked.
        os.fsync = real_fsync

    # The previous content must survive — no corruption.
    surviving = json.loads(target.read_text())
    assert surviving["refresh_token"] == "prior-secret", (
        "partial-write failure clobbered the previously-written secret — "
        "the writer is not atomic"
    )

    # And no orphan tmp files should be left around the target.
    tmp_siblings = [
        p for p in target.parent.iterdir()
        if p != target and "token.json" in p.name
    ]
    assert tmp_siblings == [], (
        f"atomic writer left tmp files behind after a partial-write crash: "
        f"{tmp_siblings!r}"
    )


# ---------------------------------------------------------------------------
# os.open contract: O_EXCL + explicit 0o600 (closes TOCTOU window)
# ---------------------------------------------------------------------------


def test_write_secret_json_opens_with_o_excl_and_explicit_0o600(tmp_path):
    """The helper must call ``os.open`` with ``O_CREAT|O_EXCL`` and an
    explicit ``0o600`` mode so the file is created at 0o600 atomically —
    not at the umask-derived 0o644 with a post-write chmod (which leaves
    a TOCTOU window where other users can read the secret).
    """
    observed_opens: list[tuple[str, int, int]] = []
    real_os_open = os.open

    def spying_os_open(path, flags, mode=0o777, *args, **kwargs):
        observed_opens.append((str(path), flags, mode))
        return real_os_open(path, flags, mode, *args, **kwargs)

    target = tmp_path / "token.json"

    old_umask = os.umask(0o022)
    try:
        from agent.secure_file_io import write_secret_json

        with patch.object(os, "open", spying_os_open):
            write_secret_json(target, {"k": "v"})
    finally:
        os.umask(old_umask)

    # Look for an open() against either the target or a sibling tmp file
    # that includes the basename — atomic writers typically open
    # ``<target>.tmp.<pid>`` and rename onto the target.
    target_opens = [
        (p, fl, m) for (p, fl, m) in observed_opens
        if Path(p).name == target.name or target.name in Path(p).name
    ]
    assert target_opens, (
        f"os.open was never called for the secret file or its tmp sibling; "
        f"observed={observed_opens!r}"
    )
    for path, flags, mode in target_opens:
        assert flags & os.O_CREAT, (
            f"secret open missing O_CREAT: path={path}"
        )
        assert flags & os.O_EXCL, (
            f"secret open missing O_EXCL — TOCTOU-safe pattern not used: "
            f"path={path}, flags={flags}"
        )
        expected = stat.S_IRUSR | stat.S_IWUSR
        assert mode == expected, (
            f"secret open mode 0o{mode:o} != 0o{expected:o} (S_IRUSR|S_IWUSR) — "
            f"umask would briefly expose the secret"
        )
