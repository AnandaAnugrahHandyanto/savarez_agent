import json
import socket
import threading
import time
from pathlib import Path

from hermes_cli.daemon import DaemonPaths, HermesDaemonServer, request
from hermes_state import SessionDB


def _paths(tmp_path: Path) -> DaemonPaths:
    runtime = tmp_path / "runtime"
    return DaemonPaths(
        runtime_dir=runtime,
        socket_path=runtime / "hermes-daemon.sock",
        pid_path=runtime / "hermes-daemon.pid",
        log_path=runtime / "hermes-daemon.log",
    )


def test_daemon_handle_request_create_get_and_list_session(tmp_path):
    db_path = tmp_path / "state.db"
    server = HermesDaemonServer(
        paths=_paths(tmp_path),
        db_factory=lambda: SessionDB(db_path),
    )

    created = server.handle_request(
        {
            "method": "session.create",
            "params": {"id": "daemon-test-1", "title": "Daemon Test", "source": "daemon-test"},
        }
    )
    assert created["ok"] is True
    assert created["result"]["session"]["id"] == "daemon-test-1"
    assert created["result"]["session"]["title"] == "Daemon Test"

    got = server.handle_request({"method": "session.get", "params": {"id": "daemon-test-1"}})
    assert got["ok"] is True
    assert got["result"]["session"]["source"] == "daemon-test"

    listed = server.handle_request({"method": "session.list", "params": {"source": "daemon-test"}})
    assert listed["ok"] is True
    assert [s["id"] for s in listed["result"]["sessions"]] == ["daemon-test-1"]


def test_daemon_socket_ping_and_session_create(tmp_path):
    paths = _paths(tmp_path)
    db_path = tmp_path / "state.db"
    server = HermesDaemonServer(paths=paths, db_factory=lambda: SessionDB(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    deadline = time.time() + 3
    while time.time() < deadline:
        if paths.socket_path.exists():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.1)
                    sock.connect(str(paths.socket_path))
                break
            except OSError:
                pass
        time.sleep(0.05)
    else:
        raise AssertionError("daemon socket did not become ready")

    ping = request("ping", paths=paths)
    assert ping["ok"] is True
    assert ping["result"]["protocol_version"] == 1

    created = request(
        "session.create",
        {"id": "socket-test-1", "title": "Socket Test", "source": "daemon-test"},
        paths=paths,
    )
    assert created["ok"] is True
    assert created["result"]["session"]["id"] == "socket-test-1"

    shutdown = request("shutdown", paths=paths)
    assert shutdown["ok"] is True
    server.stop()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_daemon_bad_method_returns_structured_error(tmp_path):
    server = HermesDaemonServer(paths=_paths(tmp_path), db_factory=lambda: SessionDB(tmp_path / "state.db"))
    resp = server.handle_request({"method": "missing.method", "params": {}})
    assert resp["ok"] is False
    assert resp["error"]["code"] == "unknown_method"
