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

* **``shlex.split()`` destroys Windows paths** — on POSIX ``\`` is an
  escape character, so ``shlex.split("cat C:\\Users\\Admin\\file.txt")``
  returns ``["cat", "C:UsersAdminfile.txt"]`` with all backslashes
  silently consumed.  This module provides ``safe_split_command()`` and
  ``safe_subprocess_run()`` which return the raw string on Windows
  (for use with ``subprocess.run(..., shell=True)``) and ``shlex.split()``
  on POSIX.  See PR #16212.

This module centralizes the platform-branching logic so the rest of the
codebase doesn't sprinkle ``if sys.platform == "win32":`` everywhere.

**All helpers are no-ops on non-Windows** — calling them in Linux/macOS
code paths is safe by design.  That's the "do no damage on POSIX"
guarantee.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
from typing import Optional, Sequence

__all__ = [
    "IS_WINDOWS",
    "resolve_node_command",
    "safe_split_command",
    "safe_subprocess_run",
    "secure_file_win32",
    "secure_file_chmod",
    "master_subprocess_run",
    "windows_detach_flags",
    "windows_hide_flags",
    "windows_detach_popen_kwargs",
]


IS_WINDOWS = sys.platform == "win32"


# -----------------------------------------------------------------------------
# Safe command-string splitting (Windows-safe shlex.split replacement)
# -----------------------------------------------------------------------------


def safe_split_command(command: str) -> list[str]:
    """Split a command string into an argv list platform-safely.

    On POSIX: uses ``shlex.split()`` (standard shell tokenization).

    On Windows: **does NOT use shlex.split()** because ``shlex`` treats
    ``\`` as an escape character and silently destroys backslash-separated
    paths.  Instead, returns the command as a single-element list — the
    caller MUST pass ``shell=True`` to ``subprocess.run()`` so that
    ``cmd.exe`` handles tokenization natively.

    Args:
        command: Raw command string (e.g. ``"python3 /path/to/script.py"``
            or, on Windows, ``"C:\\Users\\Admin\\script.py"``).

    Returns:
        A list suitable for ``subprocess.run()``:
        * On POSIX: ``["python3", "/path/to/script.py"]``
        * On Windows: ``["C:\\Users\\Admin\\script.py"]`` (intended for
          ``shell=True``).
    """
    if IS_WINDOWS:
        # shlex.split destroys backslashes — return whole command string.
        # Caller must use shell=True so cmd.exe handles parsing.
        return [command]
    return shlex.split(command)


def safe_subprocess_run(
    command: str,
    *args,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run a command string via subprocess, splitting platform-safely.

    Convenience wrapper around :func:`master_subprocess_run` for callers
    that pass a string command (not a list).

    On POSIX: splits with ``shlex.split()``, calls ``subprocess.run()``
    with ``shell=False`` (safe for POSIX argv).

    On Windows: passes the raw string with ``shell=True`` so ``cmd.exe``
    handles argument parsing — avoids ``shlex.split`` backslash destruction.

    All positional and keyword arguments after *command* are forwarded to
    ``subprocess.run()``.

    Args:
        command: Raw command string.
        *args: Extra positional args for ``subprocess.run()``.
        **kwargs: Extra keyword args for ``subprocess.run()``.

    Returns:
        ``subprocess.CompletedProcess`` from the underlying call.

    Raises:
        Same as ``subprocess.run()``.
    """
    return master_subprocess_run(command, *args, **kwargs)


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
# Windows file permission enforcement
# -----------------------------------------------------------------------------


def secure_file_win32(path: str, *, logger=None, raise_errors: bool = False) -> None:
    """Restrict file access to the current user on Windows.

    On POSIX this is a no-op; use ``os.chmod(path, 0o600)`` there instead.

    ``os.chmod()`` is ineffective on Windows — the permission bits
    (owner/group/other) are silently ignored.  Only the read-only flag
    (0o444) has any effect, which does NOT prevent other processes
    running as the same user from reading the file.

    This function uses ``ICACLS`` to:
    1. Remove all inherited permissions (``/inheritance:r``)
    2. Grant full control to the current user only (``/grant:r %USERNAME%:F``)

    This is the Windows-native equivalent of ``chmod 0o600`` / ``chmod 0o700``.

    Args:
        path: Absolute path to the file or directory to secure.
        logger: Logger for warnings.  Defaults to ``logging.getLogger(...)``
            which logs a warning but never raises.  Pass ``raise_errors=True``
            to propagate exceptions to the caller.
        raise_errors: When True, raises on failure instead of logging.
            Default False.

    Raises:
        ``subprocess.CalledProcessError`` if ICACLS fails and
        *raise_errors* is True.
    """
    if not IS_WINDOWS:
        return
    if not os.path.exists(path):
        if logger:
            logger.warning("secure_file_win32: path does not exist, skipping: %s", path)
        return
    try:
        username = os.getlogin()
    except OSError:
        username = os.environ.get("USERNAME", "Users")
    try:
        subprocess.run(
            ["icacls", path, "/inheritance:r", "/grant:r", f"{username}:F"],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError) as exc:
        if raise_errors:
            raise
        _log = logger or logging.getLogger(__name__)
        _log.warning(
            "secure_file_win32: ICACLS failed for %s: %s", path, exc,
        )


def secure_file_chmod(path: str, mode: int = 0o600, *, logger=None, raise_errors: bool = False) -> None:
    """Secure a file with the strongest permissions available.

    Windows: uses ``icacls /inheritance:r /grant:r %USERNAME%:F``
    (real ACL-based restriction).

    POSIX: uses ``os.chmod(path, mode)`` (default 0o600).

    Args:
        path: Absolute path to the file to secure.
        mode: POSIX permission bits (ignored on Windows).
        logger: Logger for warnings (default: ``logging.getLogger(...)``).
        raise_errors: When True, raises on failure (default False).

    Raises:
        ``OSError`` on POSIX if chmod fails.
        ``subprocess.CalledProcessError`` on Windows if ICACLS fails
        and *raise_errors* is True.
    """
    if IS_WINDOWS:
        secure_file_win32(path, logger=logger, raise_errors=raise_errors)
    else:
        os.chmod(path, mode)


# -----------------------------------------------------------------------------
# Master subprocess execution wrapper
# -----------------------------------------------------------------------------


def master_subprocess_run(
    command: str | list[str],
    *args,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run a subprocess with full Windows compatibility.

    This is the ONE function to use instead of raw ``subprocess.run()``.
    It handles all three Windows pitfalls automatically:

    * **``.cmd`` batch file resolution** — ``npm``, ``node``,
      ``npx``, etc. are resolved via ``shutil.which()`` so
      ``CreateProcessW`` doesn't fail with WinError 193.
    * **Path backslash safety** — when *command* is a string,
      it's passed with ``shell=True`` on Windows so ``cmd.exe`` handles
      argument tokenization (avoids ``shlex.split`` backslash destruction).
    * **``shell=True`` consolidation** — all ``shell=True``
      decisions are centralized here instead of sprinkled across 10+
      call sites.

    On POSIX the behavior is unchanged: string commands are split with
    ``shlex.split()`` and executed with ``shell=False``; list commands
    are passed as-is.

    Args:
        command: Command string (e.g. ``"npm install"``) or argv list
            (e.g. ``["npm", "install"]``).
        *args: Extra positional args forwarded to ``subprocess.run()``.
        **kwargs: Extra keyword args forwarded to ``subprocess.run()``.

    Returns:
        ``subprocess.CompletedProcess``.

    Raises:
        Same as ``subprocess.run()``.
    """
    if not IS_WINDOWS:
        if isinstance(command, str):
            import shlex
            argv = shlex.split(command)
        else:
            argv = list(command)
        return subprocess.run(argv, *args, **kwargs)

    # --- Windows path below ---
    if isinstance(command, str):
        known_cmd = command.split(None, 1)[0].lower()
        if known_cmd in ("npm", "node", "npx", "yarn", "pnpm", "playwright", "prettier"):
            rest = command.split(None, 1)[1] if " " in command else ""
            resolved_argv = resolve_node_command(known_cmd, [rest] if rest else [])
            kwargs.setdefault("shell", False)
            return subprocess.run(resolved_argv, *args, **kwargs)

        kwargs.setdefault("shell", True)
        return subprocess.run(command, *args, **kwargs)

    if command and command[0].lower() in ("npm", "node", "npx", "yarn", "pnpm"):
        resolved = resolve_node_command(command[0], command[1:])
        kwargs.setdefault("shell", False)
        return subprocess.run(resolved, *args, **kwargs)

    kwargs.setdefault("shell", False)
    return subprocess.run(list(command), *args, **kwargs)


def master_subprocess_popen(
    command: str | list[str],
    *args, **kwargs,
) -> subprocess.Popen:
    """Like :func:`master_subprocess_run` but returns ``subprocess.Popen``
    for long-lived / background processes.

    Same Windows compat (``.cmd`` shim resolution, path backslash safety,
    ``shell=True`` by default for string commands) but non-blocking.

    On POSIX the behavior is unchanged: string commands are split with
    ``shlex.split()`` and executed with ``shell=False``; list commands
    are passed as-is.

    Args:
        command: Command string (e.g. ``"npm install"``) or argv list
            (e.g. ``["npm", "install"]``).
        *args: Extra positional args forwarded to ``subprocess.Popen()``.
        **kwargs: Extra keyword args forwarded to ``subprocess.Popen()``.

    Returns:
        ``subprocess.Popen`` instance.

    Raises:
        Same as ``subprocess.Popen()``.
    """
    if not IS_WINDOWS:
        if isinstance(command, str):
            import shlex
            argv = shlex.split(command)
        else:
            argv = list(command)
        return subprocess.Popen(argv, *args, **kwargs)

    # --- Windows path below ---
    if isinstance(command, str):
        known_cmd = command.split(None, 1)[0].lower()
        if known_cmd in ("npm", "node", "npx", "yarn", "pnpm", "playwright", "prettier"):
            rest = command.split(None, 1)[1] if " " in command else ""
            resolved_argv = resolve_node_command(known_cmd, [rest] if rest else [])
            kwargs.setdefault("shell", False)
            return subprocess.Popen(resolved_argv, *args, **kwargs)

        kwargs.setdefault("shell", True)
        return subprocess.Popen(command, *args, **kwargs)

    if command and command[0].lower() in ("npm", "node", "npx", "yarn", "pnpm"):
        resolved = resolve_node_command(command[0], command[1:])
        kwargs.setdefault("shell", False)
        return subprocess.Popen(resolved, *args, **kwargs)

    kwargs.setdefault("shell", False)
    return subprocess.Popen(list(command), *args, **kwargs)


# -----------------------------------------------------------------------------
# Detached / hidden process creation
# -----------------------------------------------------------------------------


_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000


def windows_detach_flags() -> int:
    """Return Win32 creationflags that detach a child from the parent
    console and process group.  0 on non-Windows.

    Pair with ``start_new_session=False`` (default) when calling
    subprocess.Popen.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS | _CREATE_NO_WINDOW


def windows_hide_flags() -> int:
    """Return Win32 creationflags that merely hide the child's console
    window without detaching the child.  0 on non-Windows.

    Use for short-lived console apps where we want no
    flash but also want to collect stdout/exit code synchronously.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NO_WINDOW


def windows_detach_popen_kwargs() -> dict:
    """Return a dict of Popen kwargs that detach a child on Windows and
    fall back to ``start_new_session=True`` on POSIX.

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

    This replaces the unsafe-on-Windows pattern ``start_new_session=True``
    which silently fails to detach on Windows.
    """
    if IS_WINDOWS:
        return {"creationflags": windows_detach_flags()}
    return {"start_new_session": True}
