"""Local Hermes session daemon MVP.

This module implements the first, deliberately small slice of the jcode-style
single-server / multi-client architecture: a profile-local Unix socket daemon
that can expose session registry operations without starting a full chat loop.

The daemon is intentionally conservative:
- local Unix-domain socket only
- one JSON request per line, one JSON response per line
- no model calls or tool execution in the MVP
- profile-aware paths via get_hermes_home()

It gives Mission Control / Agent Room and future thin clients a stable local
surface for discovering and creating Hermes sessions while preserving today's
standalone CLI behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from hermes_constants import get_hermes_home
from hermes_state import SessionDB


PROTOCOL_VERSION = 1
DEFAULT_SOURCE = "daemon"


class DaemonError(RuntimeError):
    """Expected daemon/client error that should be shown without a traceback."""


@dataclass(frozen=True)
class DaemonPaths:
    runtime_dir: Path
    socket_path: Path
    pid_path: Path
    log_path: Path


def daemon_paths() -> DaemonPaths:
    home = get_hermes_home()
    runtime_dir = home / "runtime"
    return DaemonPaths(
        runtime_dir=runtime_dir,
        socket_path=runtime_dir / "hermes-daemon.sock",
        pid_path=runtime_dir / "hermes-daemon.pid",
        log_path=runtime_dir / "hermes-daemon.log",
    )


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _read_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw) if raw else None
    except (FileNotFoundError, OSError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _json_error(message: str, *, code: str = "error") -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _session_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source": row.get("source"),
        "title": row.get("title"),
        "model": row.get("model"),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
        "message_count": row.get("message_count", 0),
        "preview": row.get("preview") or row.get("_preview_raw") or "",
        "last_active": row.get("last_active") or row.get("started_at"),
    }


class HermesDaemonServer:
    """Small blocking Unix-socket server for local session registry operations."""

    def __init__(self, paths: DaemonPaths | None = None, db_factory: Callable[[], SessionDB] | None = None):
        self.paths = paths or daemon_paths()
        self.db_factory = db_factory or SessionDB
        self.started_at = time.time()
        self._stop = threading.Event()
        self._sock: socket.socket | None = None

    def serve_forever(self) -> int:
        if os.name == "nt":
            raise DaemonError("Hermes daemon MVP currently requires Unix-domain sockets")

        self.paths.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.paths.socket_path.exists() and _client_ping(timeout=0.2, paths=self.paths):
            raise DaemonError(f"Hermes daemon already running at {self.paths.socket_path}")
        _safe_unlink(self.paths.socket_path)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock = sock
        try:
            sock.bind(str(self.paths.socket_path))
            try:
                os.chmod(self.paths.socket_path, 0o600)
            except OSError:
                pass
            sock.listen(32)
            self.paths.pid_path.write_text(str(os.getpid()), encoding="utf-8")

            while not self._stop.is_set():
                try:
                    conn, _ = sock.accept()
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                thread.start()
        finally:
            try:
                sock.close()
            except OSError:
                pass
            _safe_unlink(self.paths.socket_path)
            if _read_pid(self.paths.pid_path) == os.getpid():
                _safe_unlink(self.paths.pid_path)
        return 0

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            try:
                file = conn.makefile("rwb")
                for raw in file:
                    try:
                        req = json.loads(raw.decode("utf-8"))
                        resp = self.handle_request(req)
                    except Exception as exc:  # Keep daemon alive for bad client requests.
                        resp = _json_error(str(exc), code=type(exc).__name__)
                    file.write((json.dumps(resp, separators=(",", ":")) + "\n").encode("utf-8"))
                    file.flush()
            except OSError:
                return

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any]:
        method = req.get("method")
        params = req.get("params") or {}
        if not isinstance(params, dict):
            return _json_error("params must be an object", code="bad_request")

        if method == "ping":
            return {
                "ok": True,
                "result": {
                    "protocol_version": PROTOCOL_VERSION,
                    "pid": os.getpid(),
                    "started_at": self.started_at,
                    "uptime_seconds": max(0.0, time.time() - self.started_at),
                    "socket_path": str(self.paths.socket_path),
                },
            }
        if method == "session.list":
            return self._session_list(params)
        if method == "session.create":
            return self._session_create(params)
        if method == "session.get":
            return self._session_get(params)
        if method == "shutdown":
            self.stop()
            return {"ok": True, "result": {"stopping": True}}
        return _json_error(f"unknown method: {method}", code="unknown_method")

    def _session_list(self, params: dict[str, Any]) -> dict[str, Any]:
        limit = int(params.get("limit") or 20)
        limit = max(1, min(limit, 100))
        source = params.get("source")
        db = self.db_factory()
        try:
            rows = db.list_sessions_rich(
                source=source,
                limit=limit,
                include_children=bool(params.get("include_children", False)),
                order_by_last_active=True,
            )
        finally:
            db.close()
        return {"ok": True, "result": {"sessions": [_session_public(dict(row)) for row in rows]}}

    def _session_create(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = str(params.get("id") or uuid.uuid4().hex)
        source = str(params.get("source") or DEFAULT_SOURCE)
        title = params.get("title")
        model = params.get("model")
        parent_session_id = params.get("parent_session_id")
        db = self.db_factory()
        try:
            db.create_session(
                session_id,
                source,
                model=model,
                parent_session_id=parent_session_id,
            )
            if title:
                db.set_session_title(session_id, str(title))
            row = db.get_session(session_id) or {"id": session_id, "source": source}
        finally:
            db.close()
        return {"ok": True, "result": {"session": _session_public(dict(row))}}

    def _session_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("id")
        if not session_id:
            return _json_error("session.get requires params.id", code="bad_request")
        db = self.db_factory()
        try:
            resolved = db.resolve_session_id(str(session_id)) or str(session_id)
            row = db.get_session(resolved)
        finally:
            db.close()
        if not row:
            return _json_error(f"session not found: {session_id}", code="not_found")
        return {"ok": True, "result": {"session": _session_public(dict(row))}}


def request(method: str, params: dict[str, Any] | None = None, *, timeout: float = 2.0, paths: DaemonPaths | None = None) -> dict[str, Any]:
    paths = paths or daemon_paths()
    if os.name == "nt":
        raise DaemonError("Hermes daemon MVP currently requires Unix-domain sockets")
    payload = json.dumps({"method": method, "params": params or {}}, separators=(",", ":")) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(paths.socket_path))
        sock.sendall(payload.encode("utf-8"))
        file = sock.makefile("rb")
        line = file.readline()
        if not line:
            raise DaemonError("daemon closed connection without a response")
        return json.loads(line.decode("utf-8"))


def _client_ping(*, timeout: float = 0.5, paths: DaemonPaths | None = None) -> bool:
    try:
        resp = request("ping", timeout=timeout, paths=paths)
        return bool(resp.get("ok"))
    except Exception:
        return False


def start_daemon() -> int:
    paths = daemon_paths()
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    if _client_ping(paths=paths):
        resp = request("ping", paths=paths)
        print(f"Hermes daemon already running (pid {resp.get('result', {}).get('pid')})")
        print(f"Socket: {paths.socket_path}")
        return 0

    env = os.environ.copy()
    cmd = [sys.executable, "-m", "hermes_cli.main", "daemon", "serve"]
    log = paths.log_path.open("ab")
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
        )
    finally:
        log.close()

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if _client_ping(paths=paths):
            resp = request("ping", paths=paths)
            print(f"Hermes daemon started (pid {resp.get('result', {}).get('pid')})")
            print(f"Socket: {paths.socket_path}")
            return 0
        time.sleep(0.1)
    raise DaemonError(f"daemon did not become ready; see {paths.log_path}")


def stop_daemon() -> int:
    paths = daemon_paths()
    pid = _read_pid(paths.pid_path)
    stopped = False
    try:
        if paths.socket_path.exists():
            resp = request("shutdown", timeout=1.0, paths=paths)
            stopped = bool(resp.get("ok"))
    except Exception:
        stopped = False

    if pid and _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.time() + 3.0
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(0.1)

    _safe_unlink(paths.socket_path)
    if pid is None or not _pid_alive(pid):
        _safe_unlink(paths.pid_path)

    if stopped or (pid and not _pid_alive(pid)):
        print("Hermes daemon stopped")
        return 0
    print("Hermes daemon was not running")
    return 0


def status_daemon(*, json_output: bool = False) -> int:
    paths = daemon_paths()
    status: dict[str, Any] = {
        "socket_path": str(paths.socket_path),
        "pid_path": str(paths.pid_path),
        "log_path": str(paths.log_path),
        "running": False,
        "pid": _read_pid(paths.pid_path),
    }
    try:
        resp = request("ping", timeout=0.5, paths=paths)
        if resp.get("ok"):
            status.update(resp.get("result") or {})
            status["running"] = True
    except Exception as exc:
        status["error"] = str(exc)

    if json_output:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print("Hermes daemon: " + ("running" if status["running"] else "stopped"))
        if status.get("pid"):
            print(f"PID: {status['pid']}")
        print(f"Socket: {status['socket_path']}")
        print(f"Log: {status['log_path']}")
        if status.get("error") and paths.socket_path.exists():
            print(f"Last error: {status['error']}")
    return 0 if status["running"] else 1


def daemon_command(args: argparse.Namespace) -> int:
    action = getattr(args, "daemon_action", None) or "status"
    try:
        if action == "serve":
            server = HermesDaemonServer()
            return server.serve_forever()
        if action == "start":
            return start_daemon()
        if action == "stop":
            return stop_daemon()
        if action == "restart":
            stop_daemon()
            return start_daemon()
        if action == "status":
            return status_daemon(json_output=bool(getattr(args, "json", False)))
        if action == "sessions":
            resp = request("session.list", {"limit": getattr(args, "limit", 20)})
            if getattr(args, "json", False):
                print(json.dumps(resp, indent=2, sort_keys=True))
            elif resp.get("ok"):
                for row in resp.get("result", {}).get("sessions", []):
                    title = row.get("title") or row.get("preview") or "(untitled)"
                    print(f"{row.get('id')}  {row.get('source')}  {row.get('message_count')} msgs  {title}")
            else:
                print(json.dumps(resp, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            return 0
        if action == "create-session":
            resp = request(
                "session.create",
                {
                    "title": getattr(args, "title", None),
                    "source": getattr(args, "source", None) or DEFAULT_SOURCE,
                    "model": getattr(args, "model", None),
                },
            )
            print(json.dumps(resp, indent=2, sort_keys=True))
            return 0 if resp.get("ok") else 1
    except DaemonError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (ConnectionRefusedError, FileNotFoundError, socket.timeout) as exc:
        print(f"Error: Hermes daemon is not running ({exc})", file=sys.stderr)
        return 1
    raise DaemonError(f"unknown daemon action: {action}")
