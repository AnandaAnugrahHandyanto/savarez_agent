"""Tests for Kanban webhook notifications.

Covers: payload building, HMAC signature, retry logic, async firing,
and integration with task state transitions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
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
