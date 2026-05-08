"""PTY bridge for the Hermes dashboard chat tab.

Wraps a child process behind a pseudo-terminal so its ANSI output can be
streamed to a browser-side terminal emulator (xterm.js) and typed
keystrokes can be fed back in.  The only caller today is the
api/pty WebSocket endpoint in hermes_cli.web_server.

Design constraints:

* **Backend-isolated.**  The public PtyBridge API stays stable while
  platform-specific PTY details live behind a backend seam.  The POSIX
  backend is the only enabled backend today; Windows support can be added by
  implementing the same byte-oriented contract.
* **Zero Node dependency on the server side.**  We use ptyprocess,
  which is a pure-Python wrapper around the OS calls.  The browser talks
  to the same hermes --tui binary it would launch from the CLI, so
  every TUI feature (slash popover, model picker, tool rows, markdown,
  skin engine, clarify/sudo/approval prompts) ships automatically.
* **Byte-safe I/O.**  Reads and writes go through a byte-oriented bridge
  interface, avoiding Unicode wrappers because
  streaming ANSI is inherently byte-oriented and UTF-8 boundaries may land
  mid-read.
"""

from __future__ import annotations

import errno
import os
import select
import signal
import struct
import sys
import time
from typing import Optional, Protocol, Sequence

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - native Windows
    fcntl = None  # type: ignore[assignment]

try:
    import termios  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - native Windows
    termios = None  # type: ignore[assignment]

try:
    import ptyprocess  # type: ignore
except ImportError:  # pragma: no cover - dev env without ptyprocess
    ptyprocess = None  # type: ignore[assignment]

try:
    from winpty import ptyprocess as winpty_ptyprocess  # type: ignore
except ImportError:  # pragma: no cover - non-Windows or missing pywinpty
    winpty_ptyprocess = None  # type: ignore[assignment]

_POSIX_PTY_AVAILABLE = (
    ptyprocess is not None
    and fcntl is not None
    and termios is not None
    and not sys.platform.startswith("win")
)
_WINDOWS_PTY_AVAILABLE = (
    winpty_ptyprocess is not None and sys.platform.startswith("win")
)
_PTY_AVAILABLE = _POSIX_PTY_AVAILABLE or _WINDOWS_PTY_AVAILABLE


def _pty_unavailable_message() -> str:
    """Return an actionable reason for spawn-time PTY unavailability."""
    if sys.platform.startswith("win"):
        return (
            "Pseudo-terminals are unavailable on native Windows for the "
            "dashboard chat/TUI path. Run Hermes Agent inside WSL to use "
            "the dashboard chat tab."
        )

    missing_modules = [
        name
        for name, module in (
            ("ptyprocess", ptyprocess),
            ("fcntl", fcntl),
            ("termios", termios),
        )
        if module is None
    ]
    if missing_modules:
        return (
            "Pseudo-terminals are unavailable because this Python environment "
            f"is missing Unix PTY module(s): {', '.join(missing_modules)}. "
            "On Windows, run Hermes Agent inside WSL for POSIX PTY support; "
            "otherwise install the PTY extra with: pip install -e '.[pty]'."
        )

    return "Pseudo-terminals are unavailable."


__all__ = ["PtyBridge", "PtyUnavailableError"]


class PtyUnavailableError(RuntimeError):
    """Raised when a PTY cannot be created on this platform.

    Today this means native Windows (no ConPTY bindings) or a dev
    environment missing the ptyprocess dependency.  The dashboard
    surfaces the message to the user as a chat-tab banner.
    """


class _PtyBackend(Protocol):
    """Byte-oriented backend contract used by PtyBridge."""

    @property
    def pid(self) -> int: ...

    def is_alive(self) -> bool: ...

    def read(self, timeout: float = 0.2) -> Optional[bytes]: ...

    def write(self, data: bytes) -> None: ...

    def resize(self, cols: int, rows: int) -> None: ...

    def close(self) -> None: ...


class _PosixPtyBackend:
    """POSIX implementation backed by ptyprocess plus raw fd I/O."""

    def __init__(self, proc: "ptyprocess.PtyProcess"):  # type: ignore[name-defined]
        self._proc = proc
        self._fd: int = proc.fd
        self._closed = False

    @classmethod
    def spawn(
        cls,
        argv: Sequence[str],
        *,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        cols: int = 80,
        rows: int = 24,
    ) -> "_PosixPtyBackend":
        # PTY-hosted programs expect TERM to describe the terminal type.
        # CI often runs without TERM in the parent process, which makes
        # simple terminal probes like tput cols fail before winsize reads.
        # Preserve explicit caller overrides, but backfill a sensible default
        # when TERM is missing or blank.
        spawn_env = (os.environ.copy() if env is None else env.copy())
        if not spawn_env.get("TERM"):
            spawn_env["TERM"] = "xterm-256color"
        proc = ptyprocess.PtyProcess.spawn(  # type: ignore[union-attr]
            list(argv),
            cwd=cwd,
            env=spawn_env,
            dimensions=(rows, cols),
        )
        return cls(proc)

    @property
    def pid(self) -> int:
        return int(self._proc.pid)

    def is_alive(self) -> bool:
        if self._closed:
            return False
        try:
            return bool(self._proc.isalive())
        except Exception:
            return False

    def read(self, timeout: float = 0.2) -> Optional[bytes]:
        """Read up to 64 KiB of raw bytes from the PTY master."""
        if self._closed:
            return None
        try:
            readable, _, _ = select.select([self._fd], [], [], timeout)
        except (OSError, ValueError):
            return None
        if not readable:
            return b""
        try:
            data = os.read(self._fd, 65536)
        except OSError as exc:
            # EIO on Linux = slave side closed.  EBADF = already closed.
            if exc.errno in (errno.EIO, errno.EBADF):
                return None
            raise
        if not data:
            return None
        return data

    def write(self, data: bytes) -> None:
        """Write raw bytes to the PTY master (i.e. the child's stdin)."""
        if self._closed or not data:
            return
        # os.write can return a short write under load; loop until drained.
        view = memoryview(data)
        while view:
            try:
                n = os.write(self._fd, view)
            except OSError as exc:
                if exc.errno in (errno.EIO, errno.EBADF, errno.EPIPE):
                    return
                raise
            if n <= 0:
                return
            view = view[n:]

    def resize(self, cols: int, rows: int) -> None:
        """Forward a terminal resize to the child via TIOCSWINSZ."""
        if self._closed:
            return
        # struct winsize: rows, cols, xpixel, ypixel (all unsigned short)
        winsize = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
        try:
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def close(self) -> None:
        """Terminate the child and close fds. Idempotent."""
        if self._closed:
            return
        self._closed = True

        # SIGHUP is the conventional "your terminal went away" signal.
        # We escalate if the child ignores it.
        for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):  # windows-footgun: ok — POSIX-only module (imports fcntl/termios/ptyprocess at top)
            if not self._proc.isalive():
                break
            try:
                self._proc.kill(sig)
            except Exception:
                pass
            deadline = time.monotonic() + 0.5
            while self._proc.isalive() and time.monotonic() < deadline:
                time.sleep(0.02)

        try:
            self._proc.close(force=True)
        except Exception:
            pass


class _WindowsPtyBackend:
    """Windows implementation backed by pywinpty winpty.ptyprocess."""

    def __init__(self, proc):
        self._proc = proc
        self._closed = False

    @classmethod
    def spawn(
        cls,
        argv: Sequence[str],
        *,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        cols: int = 80,
        rows: int = 24,
    ) -> "_WindowsPtyBackend":
        spawn_env = (os.environ.copy() if env is None else env.copy())
        if not spawn_env.get("TERM"):
            spawn_env["TERM"] = "xterm-256color"
        proc = winpty_ptyprocess.PtyProcess.spawn(  # type: ignore[union-attr]
            list(argv),
            cwd=cwd,
            env=spawn_env,
            dimensions=(rows, cols),
        )
        return cls(proc)

    @property
    def pid(self) -> int:
        return int(self._proc.pid)

    def is_alive(self) -> bool:
        if self._closed:
            return False
        try:
            return bool(self._proc.isalive())
        except Exception:
            return False

    def read(self, timeout: float = 0.2) -> Optional[bytes]:
        if self._closed:
            return None
        try:
            data = self._proc.read()
        except EOFError:
            return None
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF, errno.EPIPE):
                return None
            raise
        if data is None:
            return None
        if data == "" or data == b"":
            return b""
        if isinstance(data, bytes):
            return data
        return str(data).encode("utf-8")

    def write(self, data: bytes) -> None:
        if self._closed or not data:
            return
        if isinstance(data, bytes):
            text = data.decode("utf-8", "replace")
        else:
            text = str(data)
        try:
            self._proc.write(text)
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF, errno.EPIPE):
                return
            raise

    def resize(self, cols: int, rows: int) -> None:
        if self._closed:
            return
        try:
            self._proc.setwinsize(max(1, rows), max(1, cols))
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._proc.close(force=True)
            return
        except Exception:
            pass
        try:
            self._proc.terminate(force=True)
        except Exception:
            pass


class PtyBridge:
    """Thin, byte-oriented facade over a platform-specific PTY backend.

    Not thread-safe.  A single bridge is owned by the WebSocket handler
    that spawned it; the reader runs in an executor thread while writes
    happen on the event-loop thread.  Backend implementations must preserve
    the byte-oriented read/write contract used by /api/pty.
    """

    def __init__(self, backend: _PtyBackend):
        self._backend = backend

    # -- lifecycle --------------------------------------------------------

    @classmethod
    def is_available(cls) -> bool:
        """True if a PTY can be spawned on this platform."""
        return bool(_PTY_AVAILABLE)

    @classmethod
    def spawn(
        cls,
        argv: Sequence[str],
        *,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        cols: int = 80,
        rows: int = 24,
    ) -> "PtyBridge":
        """Spawn argv behind a new PTY and return a bridge.

        Raises PtyUnavailableError if the platform cannot host a
        PTY. Raises FileNotFoundError or OSError for ordinary exec failures
        such as a missing binary or bad cwd.
        """
        if not _PTY_AVAILABLE:
            raise PtyUnavailableError(_pty_unavailable_message())

        if _POSIX_PTY_AVAILABLE:
            backend = _PosixPtyBackend.spawn(
                argv,
                cwd=cwd,
                env=env,
                cols=cols,
                rows=rows,
            )
            return cls(backend)

        if _WINDOWS_PTY_AVAILABLE:
            backend = _WindowsPtyBackend.spawn(
                argv,
                cwd=cwd,
                env=env,
                cols=cols,
                rows=rows,
            )
            return cls(backend)

        raise PtyUnavailableError("Pseudo-terminals are unavailable.")

    @property
    def pid(self) -> int:
        return self._backend.pid

    def is_alive(self) -> bool:
        return self._backend.is_alive()

    # -- I/O --------------------------------------------------------------

    def read(self, timeout: float = 0.2) -> Optional[bytes]:
        """Read up to 64 KiB of raw bytes from the PTY master.

        Returns:
            * bytes — zero or more bytes of child output
            * empty bytes (b empty) — no data available within timeout
            * None — child has exited and the master fd is at EOF

        Never blocks longer than timeout seconds. Safe to call after close;
        returns None in that case.
        """
        return self._backend.read(timeout)

    def write(self, data: bytes) -> None:
        """Write raw bytes to the PTY master (i.e. the child's stdin)."""
        self._backend.write(data)

    def resize(self, cols: int, rows: int) -> None:
        """Forward a terminal resize to the child."""
        self._backend.resize(cols=cols, rows=rows)

    # -- teardown ---------------------------------------------------------

    def close(self) -> None:
        """Terminate the child and close fds. Idempotent."""
        self._backend.close()

    # Context-manager sugar — handy in tests and ad-hoc scripts.
    def __enter__(self) -> "PtyBridge":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
