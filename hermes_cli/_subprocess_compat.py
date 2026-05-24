"""Windows subprocess compatibility helpers.

Hermes is developed on Linux / macOS and tested natively on Windows too.
Several common subprocess patterns break silently-or-loudly on Windows:

* ``["npm", "install", ...]`` — on Windows ``npm`` is ``npm.cmd``, a batch
  shim.  ``subprocess.Popen(["npm", ...])`` fails with WinError 193
  ("not a valid Win32 application") because CreateProcessW can't run a
  ``.cmd`` file without ``shell=True`` or PATHEXT resolution.

* ``start_new_session=True`` — on POSIX, this maps to ``os.setsid()`` and
  actually detaches the child.  On Windows it's silently ignored; the
  Windows equivalent is ``CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS``
  creationflags, which Python only applies when you pass them explicitly.

* Console-window flashes — every ``subprocess.Popen`` of a ``.exe`` on
  Windows spawns a cmd window briefly unless ``CREATE_NO_WINDOW`` is
  passed.  Cosmetic but jarring for background daemons.

This module centralizes the platform-branching logic so the rest of the
codebase doesn't sprinkle ``if sys.platform == "win32":`` everywhere.

**All helpers are no-ops on non-Windows** — calling them in Linux/macOS
code paths is safe by design.  That's the "do no damage on POSIX"
guarantee.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional, Sequence

__all__ = [
    "IS_WINDOWS",
    "resolve_node_command",
    "windows_detach_flags",
    "windows_hide_flags",
    "windows_detach_popen_kwargs",
    "is_windows_shim_target",
    "arg_contains_cmd_metachars",
    "CMD_METACHARS",
]


IS_WINDOWS = sys.platform == "win32"


# -----------------------------------------------------------------------------
# Node ecosystem launcher resolution
# -----------------------------------------------------------------------------


def resolve_node_command(name: str, argv: Sequence[str]) -> list[str]:
    """Resolve a Node-ecosystem command name to an absolute-path argv.

    On Windows, commands like ``npm``, ``npx``, ``yarn``, ``pnpm``,
    ``playwright``, ``prettier`` ship as ``.cmd`` files (batch shims).
    ``subprocess.Popen(["npm", "install"])`` fails with WinError 193
    because CreateProcessW doesn't execute batch files directly.

    ``shutil.which(name)`` *does* resolve ``.cmd`` via PATHEXT and returns
    the fully-qualified path — which CreateProcessW accepts because the
    extension tells Windows to route through ``cmd.exe /c``.

    On POSIX ``shutil.which`` also returns a fully-qualified path when
    found.  That's a small change from bare-name resolution (the OS does
    its own PATH search) but functionally identical and has the side
    benefit of making the argv reproducible in logs.

    Behavior when the command is not on PATH:
    - On Windows: return the bare name — caller can still try with
      ``shell=True`` as a last resort, OR the subsequent Popen will
      raise FileNotFoundError with a readable error we want to surface.
    - On POSIX: same.  Bare ``npm`` on a Linux box without npm installed
      fails the same way it did before this function existed.

    Args:
        name: The command name to resolve (``npm``, ``npx``, ``node`` …).
        argv: The remaining arguments.  Must NOT include ``name`` itself —
            this function builds the full argv list.

    Returns:
        A list suitable for passing to subprocess.Popen/run/call.
    """
    resolved = shutil.which(name)
    if resolved:
        return [resolved, *argv]
    return [name, *argv]


# -----------------------------------------------------------------------------
# Detached / hidden process creation
# -----------------------------------------------------------------------------


# Win32 CreationFlags — defined here rather than imported from subprocess
# because CREATE_NO_WINDOW and DETACHED_PROCESS aren't guaranteed to be
# present on stdlib subprocess on older Pythons or non-Windows builds.
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000


def windows_detach_flags() -> int:
    """Return Win32 creationflags that detach a child from the parent
    console and process group.  0 on non-Windows.

    Pair with ``start_new_session=False`` (default) when calling
    subprocess.Popen — on POSIX use ``start_new_session=True`` instead,
    which maps to ``os.setsid()`` in the child.

    Rationale:
    - ``CREATE_NEW_PROCESS_GROUP`` — child has its own process group so
      Ctrl+C in the parent console doesn't propagate.
    - ``DETACHED_PROCESS`` — child has no console at all.  Necessary for
      background daemons (gateway watchers, update respawners) because
      without it, closing the console kills the child.
    - ``CREATE_NO_WINDOW`` — suppress the brief cmd flash that would
      otherwise appear when launching a console app.  Redundant with
      DETACHED_PROCESS but explicit for clarity.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS | _CREATE_NO_WINDOW


def windows_hide_flags() -> int:
    """Return Win32 creationflags that merely hide the child's console
    window without detaching the child.  0 on non-Windows.

    Use for short-lived console apps spawned as part of a larger
    operation (``taskkill``, ``where``, version probes) where we want no
    flash but also want to collect stdout/exit code synchronously.

    The key difference from :func:`windows_detach_flags`: NO
    ``DETACHED_PROCESS`` — the child still inherits stdio handles so
    ``capture_output=True`` works.  ``DETACHED_PROCESS`` would sever
    stdio and break stdout capture.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NO_WINDOW


# -----------------------------------------------------------------------------
# cmd.exe shim metacharacter detection (Windows .cmd / .bat re-parse hazard)
# -----------------------------------------------------------------------------


# Characters that cmd.exe treats specially when a .cmd / .bat shim
# re-parses its argv.  Even if Python's subprocess module passes argv
# correctly to ``CreateProcessW``, a ``.cmd`` / ``.bat`` target runs
# inside ``cmd.exe /c``, which re-tokenizes its arguments and interprets
# these as shell operators rather than literals:
#
#   |       pipe — splits the rest of the argv into a new command
#   &       command sequencer (``a & b``) or background (``&``)
#   <  >    file redirection (``> out.txt`` truncates a file)
#   ^       cmd.exe's escape character — strips the next char
#   "       quote — affects argv tokenization on the cmd.exe side
#
# Note: ``%`` is also a cmd.exe metacharacter (variable expansion) but
# only inside batch files, not on the command line; we leave it off the
# default set to keep the false-positive rate low.  Callers who care
# about it can extend the constant.
#
# See #31419 for the upstream context and the recommended fix pattern
# (route argument content via stdin or escape on the way in).
CMD_METACHARS = frozenset("|&<>^\"")


def is_windows_shim_target(target: Optional[str]) -> bool:
    """Return ``True`` if ``target`` is a Windows .cmd / .bat shim.

    Returns ``False`` on non-Windows.  Returns ``False`` if ``target``
    is ``None`` or empty.  Detection is purely extension-based — a
    correctly-named .cmd / .bat suffix.  The check is case-insensitive
    because Windows paths often round-trip through different cases.
    """
    if not IS_WINDOWS or not target:
        return False
    lowered = target.lower()
    return lowered.endswith(".cmd") or lowered.endswith(".bat")


def arg_contains_cmd_metachars(arg: str, *, extra: str = "") -> bool:
    """Return ``True`` if ``arg`` contains any cmd.exe metacharacter.

    Use this to detect when an argv value about to be passed to a
    ``.cmd`` / ``.bat`` shim would be re-parsed by ``cmd.exe`` and
    risk wrong behavior (or, with attacker-controlled content,
    command injection).

    The check is platform-agnostic on purpose: callers who already
    know they're targeting a .cmd shim (see
    :func:`is_windows_shim_target`) can call this without first
    branching on platform.  Returns ``False`` for an empty string.

    Args:
        arg: The argv value to inspect.
        extra: Optional extra characters to treat as metacharacters
            for this call (e.g. ``"%"`` if the caller is targeting
            a batch file rather than a shim).
    """
    if not arg:
        return False
    metachars = CMD_METACHARS | set(extra)
    return any(ch in metachars for ch in arg)


def windows_detach_popen_kwargs() -> dict:
    """Return a dict of Popen kwargs that detach a child on Windows and
    fall back to the POSIX equivalent (``start_new_session=True``) on
    Linux/macOS.

    Usage pattern:

    .. code-block:: python

        subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            **windows_detach_popen_kwargs(),
        )

    This replaces the unsafe-on-Windows pattern:

    .. code-block:: python

        subprocess.Popen(..., start_new_session=True)

    which silently fails to detach on Windows (the flag is accepted but
    has no effect — the child stays attached to the parent's console
    and dies when the console closes).
    """
    if IS_WINDOWS:
        return {"creationflags": windows_detach_flags()}
    return {"start_new_session": True}
