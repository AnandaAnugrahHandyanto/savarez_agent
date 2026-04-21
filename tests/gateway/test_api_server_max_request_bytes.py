"""Tests for ``_resolve_max_request_bytes`` (API_SERVER_MAX_REQUEST_MB)
and the matching ``client_max_size`` on the aiohttp application.
"""

import importlib

import pytest
from aiohttp import web

from gateway.platforms import api_server as api_server_module
from gateway.platforms.api_server import _resolve_max_request_bytes


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("API_SERVER_MAX_REQUEST_MB", raising=False)
    return monkeypatch


class TestResolveMaxRequestBytes:
    def test_default_is_25_mb(self, env):
        assert _resolve_max_request_bytes() == 25 * 1024 * 1024

    def test_env_override_integer_mb(self, env):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "50")
        assert _resolve_max_request_bytes() == 50 * 1024 * 1024

    def test_env_override_fractional_mb(self, env):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "0.5")
        assert _resolve_max_request_bytes() == 524_288  # 0.5 MiB

    def test_empty_env_uses_default(self, env):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "")
        assert _resolve_max_request_bytes() == 25 * 1024 * 1024

    def test_whitespace_env_uses_default(self, env):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "   ")
        assert _resolve_max_request_bytes() == 25 * 1024 * 1024

    def test_invalid_env_falls_back_to_default(self, env, caplog):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "not-a-number")
        with caplog.at_level("WARNING"):
            assert _resolve_max_request_bytes() == 25 * 1024 * 1024
        assert any("API_SERVER_MAX_REQUEST_MB" in r.getMessage() for r in caplog.records)

    def test_non_positive_env_falls_back_to_default(self, env):
        env.setenv("API_SERVER_MAX_REQUEST_MB", "0")
        assert _resolve_max_request_bytes() == 25 * 1024 * 1024
        env.setenv("API_SERVER_MAX_REQUEST_MB", "-5")
        assert _resolve_max_request_bytes() == 25 * 1024 * 1024

    def test_module_constant_reflects_default(self):
        # Sanity: the module-level constant captures the default at import time.
        assert api_server_module.MAX_REQUEST_BYTES >= 1_000_000


class TestAiohttpClientMaxSize:
    """Regression: aiohttp ``web.Application`` defaults ``client_max_size``
    to 1 MiB.  Without explicitly raising it, request bodies larger than
    1 MiB (e.g. a multimodal chat with a base64-encoded image) fail at the
    framework level — ``request.json()`` raises and the handler collapses
    it into an opaque ``"Invalid JSON in request body"`` response.  The
    production adapter must pass ``client_max_size=MAX_REQUEST_BYTES`` so
    ``body_limit_middleware`` is the authoritative gate.
    """

    def test_aiohttp_default_is_1_mib(self):
        """Establish the baseline: without an explicit argument, aiohttp
        caps bodies at 1 MiB — small enough that a base64 image of any
        realistic size is truncated.  This is the behavior the fix avoids.
        """
        app = web.Application()
        assert app._client_max_size == 1024 * 1024

    def test_explicit_client_max_size_is_honored(self):
        """aiohttp stores the value we pass; smoke-test the mechanism."""
        big = 25 * 1024 * 1024
        app = web.Application(client_max_size=big)
        assert app._client_max_size == big

    def test_production_path_passes_matched_limit(self):
        """The adapter's ``connect()`` body must construct ``web.Application``
        with ``client_max_size=MAX_REQUEST_BYTES`` so ``body_limit_middleware``
        is the authoritative gate, not aiohttp silently truncating at 1 MiB.

        Source-level assertion — cheaper than spinning up the full TCP
        server, and pins the exact behavior the fix establishes.
        """
        import pathlib

        src = pathlib.Path(api_server_module.__file__).read_text()
        assert "client_max_size=MAX_REQUEST_BYTES" in src, (
            "web.Application() in api_server.py must pass "
            "client_max_size=MAX_REQUEST_BYTES to honor the body-limit cap"
        )
