"""Tests for Kanban webhook notifications.

Covers: payload building, HMAC signature, retry logic, async firing,
and integration with task state transitions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_webhooks as kwh
from hermes_cli.kanban import run_slash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    # Allow localhost webhooks in tests (echo_server fixture binds to 127.0.0.1).
    monkeypatch.setenv("HERMES_KANBAN_WEBHOOK_ALLOW_LOCAL", "1")
    # Prevent the dispatcher-injected HERMES_KANBAN_DB from overriding the tmp_path.
    monkeypatch.delenv("HERMES_KANBAN_DB", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Clear any cached initialization so the new DB is truly fresh.
    kb._INITIALIZED_PATHS.clear()
    kb.init_db()
    return home


# ---------------------------------------------------------------------------
# Payload + signature unit tests
# ---------------------------------------------------------------------------

def test_build_payload_shape():
    payload = kwh.build_payload(
        event="done",
        board="default",
        task={
            "id": "t_abc123",
            "title": "Test task",
            "assignee": "fixer",
            "status": "done",
            "summary": "All tests pass",
        },
        run_id=7,
    )
    assert payload["event"] == "done"
    assert payload["board"] == "default"
    assert payload["task"]["id"] == "t_abc123"
    assert payload["task"]["url"] == "hermes://kanban/default/t_abc123"
    assert payload["task"]["run_id"] == 7
    assert "timestamp" in payload
    assert isinstance(payload["timestamp"], int)


def test_signature_without_secret():
    body = b'{"event":"done"}'
    sig = kwh._build_signature(body, None)
    assert sig == ""


def test_signature_with_secret():
    body = b'{"event":"done"}'
    secret = "shh"
    sig = kwh._build_signature(body, secret)
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sig == expected


# ---------------------------------------------------------------------------
# Retry logic (mocked urllib)
# ---------------------------------------------------------------------------

def test_send_webhook_notification_success():
    call_log: list[tuple[int, Any]] = []

    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def fake_urlopen(req, **kwargs):
        call_log.append((len(call_log), req))
        return FakeResponse()

    with patch("urllib.request.urlopen", fake_urlopen):
        ok = kwh.send_webhook_notification(
            "https://example.com/hook", "secret", {"event": "done"}
        )
    assert ok is True
    assert len(call_log) == 1
    req = call_log[0][1]
    sig_header = req.headers.get("X-kanban-signature", "")
    assert sig_header.startswith("sha256=")


def test_send_webhook_notification_retry_then_success():
    call_log: list[int] = []

    class FakeResponse:
        def __init__(self, status):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def fake_urlopen(req, **kwargs):
        call_log.append(len(call_log))
        if len(call_log) < 3:
            raise RuntimeError("network error")
        return FakeResponse(200)

    with patch("urllib.request.urlopen", fake_urlopen):
        with patch("time.sleep"):  # don't sleep in tests
            ok = kwh.send_webhook_notification(
                "https://example.com/hook", None, {"event": "done"}
            )
    assert ok is True
    assert len(call_log) == 3


def test_send_webhook_notification_all_fail():
    call_log: list[int] = []

    def fake_urlopen(req, **kwargs):
        call_log.append(len(call_log))
        raise RuntimeError("network error")

    with patch("urllib.request.urlopen", fake_urlopen):
        with patch("time.sleep"):
            ok = kwh.send_webhook_notification(
                "https://example.com/hook", None, {"event": "done"}
            )
    assert ok is False
    assert len(call_log) == 4  # initial + 3 retries


# ---------------------------------------------------------------------------
# DB CRUD
# ---------------------------------------------------------------------------

def test_webhook_crud(kanban_home):
    conn = kb.connect()
    try:
        wh_id = kb.add_webhook(
            conn, "https://a.example.com",
            events=["done", "blocked"], secret="s1",
        )
        assert wh_id > 0
        hooks = kb.list_webhooks(conn)
        assert len(hooks) == 1
        assert hooks[0]["id"] == wh_id
        assert hooks[0]["url"] == "https://a.example.com"
        assert hooks[0]["events"] == ["done", "blocked"]
        assert hooks[0]["secret"] is True  # masked

        # event filtering
        matched = kb.get_webhooks_for_event(conn, "done")
        assert len(matched) == 1
        assert matched[0]["secret"] == "s1"

        unmatched = kb.get_webhooks_for_event(conn, "timed_out")
        assert len(unmatched) == 0

        # remove
        assert kb.remove_webhook(conn, wh_id) is True
        assert kb.remove_webhook(conn, wh_id) is False
        assert kb.list_webhooks(conn) == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Integration: real HTTP server + transition hooks
# ---------------------------------------------------------------------------

@pytest.fixture
def echo_server():
    """Spin up a local HTTP server that records every POST body."""
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # quiet

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            received.append({
                "path": self.path,
                "headers": dict(self.headers),
                "body": json.loads(body.decode()),
            })
            self.send_response(200)
            self.end_headers()

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", received
    finally:
        srv.shutdown()


def test_webhook_fires_on_complete(kanban_home, echo_server):
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["done"], secret="sekrit")
        tid = kb.create_task(conn, title="webhook test", assignee="x")
        kb.complete_task(conn, tid, result="done!")
    finally:
        conn.close()

    # Give the daemon thread time to deliver
    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    req = received[0]
    assert req["body"]["event"] == "done"
    assert req["body"]["task"]["id"] == tid
    assert req["body"]["task"]["status"] == "done"

    # Verify signature
    sig_header = req["headers"].get("X-Kanban-Signature", "")
    assert sig_header.startswith("sha256=")
    body_bytes = json.dumps(req["body"], ensure_ascii=False, separators=(",", ":")).encode()
    expected_sig = hmac.new(b"sekrit", body_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_sig}"


def test_webhook_fires_on_block(kanban_home, echo_server):
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["blocked"])
        tid = kb.create_task(conn, title="block test", assignee="x")
        kb.block_task(conn, tid, reason="stuck")
    finally:
        conn.close()

    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    assert received[0]["body"]["event"] == "blocked"


def test_no_webhook_for_non_terminal_event(kanban_home, echo_server):
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["done"])
        tid = kb.create_task(conn, title="no-fire test", assignee="x")
        # unblock does nothing (task is todo, not blocked), but even if it
        # did transition, it's not a terminal state — no webhook should fire.
        kb.unblock_task(conn, tid)
    finally:
        conn.close()

    time.sleep(0.3)
    assert len(received) == 0


# ---------------------------------------------------------------------------
# CLI handler smoke tests via run_slash
# ---------------------------------------------------------------------------

def test_slash_webhook_list_empty(kanban_home):
    out = run_slash("webhook list")
    assert "no webhooks" in out.lower() or "(no webhooks" in out.lower()


def test_slash_webhook_add_and_list(kanban_home):
    add_out = run_slash("webhook add https://example.com/hook --events done,blocked")
    assert "registered" in add_out.lower() or "webhook" in add_out.lower()
    list_out = run_slash("webhook list")
    assert "https://example.com/hook" in list_out


def test_webhook_fires_on_gave_up(kanban_home, echo_server):
    """Circuit breaker (gave_up) must fire a webhook when the task trips."""
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["gave_up"], secret="sekrit")
        tid = kb.create_task(conn, title="breaker test", assignee="x")
        # Trip the breaker with failure_limit=1 (one failure = gave_up).
        kb._record_task_failure(
            conn, tid, error="spawn failed",
            outcome="spawn_failed", failure_limit=1,
            release_claim=True, end_run=True,
        )
    finally:
        conn.close()

    # Wait for async delivery
    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    req = received[0]
    assert req["body"]["event"] == "gave_up"
    assert req["body"]["task"]["id"] == tid
    assert req["body"]["task"]["status"] == "blocked"
    assert "delivery_id" in req["body"]
    # Verify signature
    sig_header = req["headers"].get("X-Kanban-Signature", "")
    assert sig_header.startswith("sha256=")
    body_bytes = json.dumps(req["body"], ensure_ascii=False, separators=(",", ":")).encode()
    expected_sig = hmac.new(b"sekrit", body_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_sig}"


# ---------------------------------------------------------------------------
# Required tests for upstream PR blockers
# ---------------------------------------------------------------------------

def test_slash_webhook_test_with_secret(kanban_home, echo_server):
    """CLI `webhook test` with a secret must compute a valid HMAC and not crash."""
    url, received = echo_server
    conn = kb.connect()
    try:
        wh_id = kb.add_webhook(conn, url, events=["done"], secret="test-secret")
    finally:
        conn.close()

    out = run_slash(f"webhook test {wh_id}")
    assert "delivered" in out.lower()

    assert len(received) == 1
    req = received[0]
    assert req["body"]["event"] == "test"
    assert req["body"]["task"]["id"] == "t_test"

    sig_header = req["headers"].get("X-Kanban-Signature", "")
    assert sig_header.startswith("sha256=")
    body_bytes = json.dumps(req["body"], ensure_ascii=False, separators=(",", ":")).encode()
    expected_sig = hmac.new(b"test-secret", body_bytes, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_sig}"


def test_webhook_fires_on_gave_up_via_record_spawn_failure(kanban_home, echo_server):
    """_record_spawn_failure wrapper must fire gave_up, not blocked."""
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["gave_up"], secret="sekrit")
        tid = kb.create_task(conn, title="spawn fail test", assignee="x")
        # Use the public backward-compat wrapper with failure_limit=1.
        kb._record_spawn_failure(
            conn, tid, error="spawn failed",
            failure_limit=1,
        )
    finally:
        conn.close()

    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    assert received[0]["body"]["event"] == "gave_up"
    assert received[0]["body"]["task"]["id"] == tid


def test_webhook_fires_on_timeout(kanban_home, echo_server):
    """enforce_max_runtime must fire a timed_out webhook."""
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["timed_out"])
        tid = kb.create_task(conn, title="timeout test", assignee="x")
        # Manually transition to running and inject a stale started_at.
        now = int(time.time())
        conn.execute(
            "UPDATE tasks SET status='running', worker_pid=12345, "
            "started_at=?, max_runtime_seconds=10, claim_lock=? "
            "WHERE id=?",
            (now - 20, kb._claimer_id(), tid),
        )
        conn.commit()

        with patch("time.time", return_value=now):
            kb.enforce_max_runtime(conn, signal_fn=lambda _pid, _sig: None)
    finally:
        conn.close()

    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    assert received[0]["body"]["event"] == "timed_out"
    assert received[0]["body"]["task"]["id"] == tid


def test_webhook_fires_on_crash(kanban_home, echo_server):
    """detect_crashed_workers must fire a crashed webhook."""
    url, received = echo_server
    conn = kb.connect()
    try:
        kb.add_webhook(conn, url, events=["crashed"])
        tid = kb.create_task(conn, title="crash test", assignee="x")
        # Manually transition to running with a fake dead PID.
        conn.execute(
            "UPDATE tasks SET status='running', worker_pid=99999, "
            "claim_lock=? WHERE id=?",
            (kb._claimer_id(), tid),
        )
        conn.commit()

        with patch.object(kb, "_pid_alive", return_value=False):
            kb.detect_crashed_workers(conn)
    finally:
        conn.close()

    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    assert received[0]["body"]["event"] == "crashed"
    assert received[0]["body"]["task"]["id"] == tid


def test_webhook_url_validation_rejects_bad_urls(kanban_home, monkeypatch):
    """add_webhook must reject dangerous or malformed URLs."""
    monkeypatch.delenv("HERMES_KANBAN_WEBHOOK_ALLOW_LOCAL", raising=False)
    conn = kb.connect()
    try:
        bad_urls = [
            "ftp://example.com/hook",
            "http://localhost:8080/hook",
            "http://127.0.0.1:8080/hook",
            "http://192.168.1.1/hook",
            "http://10.0.0.1/hook",
            "not-a-url",
        ]
        for bad in bad_urls:
            with pytest.raises(ValueError):
                kb.add_webhook(conn, bad)

        # Valid URLs should succeed
        assert kb.add_webhook(conn, "https://example.com/hook") > 0
        assert kb.add_webhook(conn, "http://example.com/hook") > 0
    finally:
        conn.close()


def test_subprocess_delivery_reliability(kanban_home, echo_server):
    """Short-lived subprocess must still deliver the webhook before exit."""
    url, received = echo_server
    home = str(kanban_home)

    script = f"""
import sys
sys.path.insert(0, "{sys.path[0]}")
from pathlib import Path
Path.home = lambda: Path("{home}").parent

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_webhooks as kwh

kb._INITIALIZED_PATHS.clear()
kb.init_db()
conn = kb.connect()
kb.add_webhook(conn, "{url}", events=["done"], secret="sub-secret")
tid = kb.create_task(conn, title="subprocess test", assignee="x")
kb.complete_task(conn, tid, result="done!")
conn.close()
"""

    env = {
        "HERMES_HOME": home,
        "HERMES_KANBAN_HOME": home,
        "HERMES_KANBAN_WEBHOOK_ALLOW_LOCAL": "1",
        "PYTHONPATH": ":".join(sys.path),
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    # Wait for async delivery
    for _ in range(50):
        if received:
            break
        time.sleep(0.05)

    assert len(received) == 1
    req = received[0]
    assert req["body"]["event"] == "done"
    assert req["body"]["task"]["id"].startswith("t_")
    sig_header = req["headers"].get("X-Kanban-Signature", "")
    assert sig_header.startswith("sha256=")
