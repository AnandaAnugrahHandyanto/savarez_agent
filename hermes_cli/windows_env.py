"""Helpers for building Windows-safe subprocess environments."""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from typing import Optional


# Windows-only: a handful of variables are required by the OS/CRT itself.
# Without them, even stdlib calls like socket.socket() can fail with
# WinError 10106 because Winsock cannot locate its provider DLLs.
WINDOWS_ESSENTIAL_ENV_VARS = frozenset(
    {
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
        "PUBLIC",
        "ALLUSERSPROFILE",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
        "USERDOMAIN",
        "USERNAME",
        "HOMEDRIVE",
        "HOMEPATH",
        "COMPUTERNAME",
    }
)


def _get_case_insensitive(env: Mapping[str, str], name: str) -> Optional[tuple[str, str]]:
    """Return the original key/value for a Windows env var name."""
    target = name.upper()
    for key, value in env.items():
        if key.upper() == target:
            return key, value
    return None


def ensure_windows_subprocess_env(
    env: MutableMapping[str, str],
    *,
    source_env: Optional[Mapping[str, str]] = None,
    is_windows: Optional[bool] = None,
) -> MutableMapping[str, str]:
    """Backfill OS-essential Windows variables into a subprocess env.

    Tests often construct intentionally tiny env dicts to prove config values
    do not leak. On Windows, dropping SYSTEMROOT/WINDIR/COMSPEC goes too far:
    the child interpreter can fail during stdlib imports before the test reaches
    the code under test. This helper restores only OS infrastructure variables,
    preserving the caller's narrow env contract.
    """
    if is_windows is None:
        is_windows = os.name == "nt"
    if not is_windows:
        return env

    source_env = os.environ if source_env is None else source_env
    present = {key.upper() for key in env}
    for name in WINDOWS_ESSENTIAL_ENV_VARS:
        if name in present:
            continue
        found = _get_case_insensitive(source_env, name)
        if found is None:
            continue
        original_key, value = found
        env[original_key] = value
        present.add(name)
    return env
