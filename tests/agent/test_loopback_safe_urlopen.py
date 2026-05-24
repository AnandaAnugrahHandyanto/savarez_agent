"""Tests for the loopback-safe urlopen helper added under #31421.

Verifies that ``loopback_safe_urlopen`` bypasses any configured
``HTTP_PROXY`` for loopback URLs while still honoring it for everything
else.
"""
from __future__ import annotations

import asyncio
import http.server
import socket
import threading
import time
from contextlib import closing
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from agent.process_bootstrap import is_loopback_url, loopback_safe_urlopen


# ----------------------------------------------------------------------
# is_loopback_url
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1/health",
        "http://localhost:8765/health",
        "http://localhost/health",
        "https://127.0.0.1:8765/health",
        "http://LocalHost/health",          # case-insensitive
        "http://[::1]:8765/health",         # IPv6 loopback
        "http://[::1]/health",
    ],
)
def test_is_loopback_url_detects_loopback(url):
    assert is_loopback_url(url), f"missed loopback URL: {url!r}"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/health",
        "https://github.com",
        "http://192.168.1.10/local-lan",    # private LAN, not loopback
        "http://10.0.0.1/",
        "http://0.0.0.0/",                  # wildcard bind, not loopback
        "",                                 # empty falls through to False
        "not-a-url",
    ],
)
def test_is_loopback_url_does_not_flag_remote(url):
    assert not is_loopback_url(url), f"false positive: {url!r}"


# ----------------------------------------------------------------------
# loopback_safe_urlopen — proxy bypass behavior (mocked HTTP_PROXY)
# ----------------------------------------------------------------------


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _OKHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib signature)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args, **_kwargs):
        # Silence the default stderr per-request log.
        return


@pytest.fixture
def local_http_server():
    """Start a tiny HTTP server on 127.0.0.1:<random-port> for the test."""
    port = _free_port()
    server = http.server.HTTPServer(("127.0.0.1", port), _OKHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Wait until the listener is actually accepting.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                with closing(socket.create_connection(("127.0.0.1", port), 0.2)):
                    break
            except OSError:
                time.sleep(0.02)
        yield port
    finally:
        server.shutdown()
        server.server_close()


def test_loopback_safe_urlopen_succeeds_even_with_bogus_http_proxy(
    local_http_server, monkeypatch
):
    """End-to-end: with HTTP_PROXY pointing at a definitely-dead address,
    ``urllib.request.urlopen`` raises (because it routes through the
    proxy that doesn't exist). ``loopback_safe_urlopen`` succeeds because
    it bypasses the proxy for loopback URLs.
    """
    # Set HTTP_PROXY to an address nothing is listening on. Any plain
    # urlopen call that honors HTTP_PROXY will fail with a connection
    # error — the bypass is the only way through.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")

    port = local_http_server
    url = f"http://127.0.0.1:{port}/anything"

    # Sanity: plain urlopen routes through the bogus proxy and fails.
    import urllib.request as _urlreq
    with pytest.raises((URLError, ConnectionRefusedError, HTTPError, OSError)):
        _urlreq.urlopen(url, timeout=1.0).close()

    # The helper bypasses the proxy and succeeds.
    with loopback_safe_urlopen(url, timeout=2.0) as r:
        assert r.status == 200
        assert r.read() == b"ok"


def test_loopback_safe_urlopen_uses_normal_path_for_remote_urls():
    """Non-loopback URLs go through the normal ``urlopen`` path, where
    HTTP_PROXY (if set) would still apply. Verified by patching
    ``urllib.request.urlopen`` and asserting it gets called with the
    remote URL.
    """
    remote_url = "http://example.com/anything"

    with patch("agent.process_bootstrap.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = "sentinel"
        result = loopback_safe_urlopen(remote_url, timeout=2.0)
        assert result == "sentinel"
        mock_urlopen.assert_called_once_with(remote_url, timeout=2.0)
