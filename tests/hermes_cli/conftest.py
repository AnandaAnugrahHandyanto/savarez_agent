"""conftest.py for tests/hermes_cli/

Stubs out POSIX-only C extensions (fcntl, termios) that are absent on
native Windows Python so that hermes_cli.pty_bridge (and thus
hermes_cli.web_server) can be imported without errors on the CI runner.
"""

from __future__ import annotations

import sys
import types


def _stub_posix_module(name: str, attrs: dict) -> None:
    """Insert a lightweight stub into sys.modules if the real module is absent."""
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    for attr, value in attrs.items():
        setattr(mod, attr, value)
    sys.modules[name] = mod


# fcntl stubs
_stub_posix_module("fcntl", {
    "fcntl": lambda fd, op, arg=0: 0,
    "ioctl": lambda fd, op, arg=0, mutate_flag=True: b"" if isinstance(arg, (bytes, bytearray)) else 0,
    "flock": lambda fd, op: None,
    "lockf": lambda fd, op, length=0, start=0, whence=0: None,
    "F_GETFL": 3,
    "F_SETFL": 4,
    "F_GETFD": 1,
    "F_SETFD": 2,
    "FD_CLOEXEC": 1,
    "LOCK_EX": 2,
    "LOCK_NB": 4,
    "LOCK_SH": 1,
    "LOCK_UN": 8,
    "TIOCSWINSZ": 0x5414,
})

# termios stubs
_stub_posix_module("termios", {
    "tcgetattr": lambda fd: [0] * 7,
    "tcsetattr": lambda fd, when, attrs: None,
    "tcsendbreak": lambda fd, duration: None,
    "tcdrain": lambda fd: None,
    "tcflush": lambda fd, queue: None,
    "tcflow": lambda fd, action: None,
    "TCSANOW": 0,
    "TCSADRAIN": 1,
    "TCSAFLUSH": 2,
    "B9600": 13,
    "TIOCSWINSZ": 0x5414,
})
