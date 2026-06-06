"""Windows gateway supervisor — poll-and-respawn for crash recovery.

Invoked once per minute by the ``Hermes_Gateway_Supervisor`` Scheduled Task
(see :func:`hermes_cli.gateway_windows._install_supervisor_task`). Checks
whether the per-profile gateway is alive and, if not, spawns a detached
replacement using the same ``_spawn_detached()`` helper that
``hermes gateway start`` uses.

This is the Windows analogue of systemd's ``Restart=always``. It runs as the
logged-in user (LIMITED rights), needs no admin context, and exits silently
when the gateway is already up.

CLI:
    pythonw -m hermes_cli.gateway_supervisor [--profile NAME]

Exit codes:
    0   always (the supervisor is best-effort; never crash the schtasks parent)

Logging:
    All actions are appended to ``$HERMES_HOME/logs/gateway-supervisor.log``.
    The file is truncated to the last 2000 lines on each invocation to keep
    it bounded.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import traceback
from pathlib import Path


_LOG_MAX_LINES = 2000


def _resolve_log_path() -> Path:
    """Return the supervisor log path under the current HERMES_HOME.

    Imported lazily so a missing/broken hermes_constants import doesn't
    crash the supervisor — we fall back to a sensible default.
    """
    try:
        from hermes_constants import get_hermes_home

        home = get_hermes_home()
    except Exception:
        # Best-effort fallback. The supervisor must never crash on import.
        home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    log_dir = Path(home) / "logs"
    return log_dir / "gateway-supervisor.log"


def _log(msg: str) -> None:
    """Append a timestamped line to the supervisor log.

    Best-effort: a logging failure must never crash the supervisor.
    """
    try:
        log_path = _resolve_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _truncate_log() -> None:
    """Keep the supervisor log bounded (last ``_LOG_MAX_LINES`` lines).

    Cheap to do once per invocation — file is small and reads sequentially.
    """
    try:
        log_path = _resolve_log_path()
        if not log_path.exists():
            return
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        if len(lines) <= _LOG_MAX_LINES:
            return
        tail = lines[-_LOG_MAX_LINES:]
        tmp = log_path.with_suffix(log_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(tail)
        tmp.replace(log_path)
    except Exception:
        pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hermes_cli.gateway_supervisor",
        description="Windows poll-and-respawn supervisor for the Hermes gateway.",
    )
    # ``--profile`` is accepted for parity with the main CLI but the
    # supervisor relies on HERMES_HOME being correctly set in the
    # scheduled-task environment; the .cmd wrapper sets it explicitly.
    parser.add_argument("--profile", default=None)
    return parser.parse_args(argv)


def _gateway_is_alive() -> tuple[bool, int | None]:
    """Probe whether a gateway is running for the current HERMES_HOME.

    Returns ``(alive, pid)``. ``pid`` is the running gateway PID when
    ``alive`` is True, else None.
    """
    try:
        from gateway.status import get_running_pid
    except Exception as exc:
        _log(f"probe import failure: {exc!r}")
        return (True, None)  # Conservative: don't try to respawn if we can't probe

    try:
        pid = get_running_pid(cleanup_stale=False)
    except Exception as exc:
        _log(f"get_running_pid raised: {exc!r}")
        return (True, None)
    return (pid is not None, pid)


def _respawn() -> int | None:
    """Spawn a fresh detached gateway. Return the PID, or None on failure."""
    try:
        from hermes_cli import gateway_windows
    except Exception as exc:
        _log(f"gateway_windows import failure: {exc!r}")
        return None
    try:
        return gateway_windows._spawn_detached()
    except Exception as exc:
        _log(f"_spawn_detached raised: {exc!r}\n{traceback.format_exc()}")
        return None


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``pythonw -m hermes_cli.gateway_supervisor``."""
    try:
        _parse_args(argv)
    except SystemExit:
        # argparse exits with 2 on --help / bad args. The schtasks parent
        # should still see 0 so the task doesn't get marked "last run failed".
        return 0
    except Exception as exc:
        _log(f"argparse raised: {exc!r}")
        return 0

    _truncate_log()

    try:
        alive, pid = _gateway_is_alive()
        if alive:
            # Stay quiet on healthy ticks to keep the log small.
            return 0
        _log("gateway is down; respawning")
        new_pid = _respawn()
        if new_pid is None:
            _log("respawn failed; will retry on next tick")
        else:
            _log(f"respawned gateway pid={new_pid}")
    except Exception as exc:
        _log(f"supervisor uncaught: {exc!r}\n{traceback.format_exc()}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
