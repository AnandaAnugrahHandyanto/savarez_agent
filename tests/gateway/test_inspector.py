"""Tests for gateway.inspector — sensitive-key scrubbing and CORS policy.

Covers:
- _is_sensitive_key: regex path, allowlist path, case/hyphen normalisation
- _scrub_sensitive: flat, nested, list, depth guard
- InspectorServer._cors_headers: loopback vs non-loopback
- InspectorServer._handle_config_public: scrubbing + section allowlist
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from gateway.inspector import (
    InspectorServer,
    _is_sensitive_key,
    _scrub_sensitive,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_server(host: str = "127.0.0.1") -> InspectorServer:
    """Construct an InspectorServer without calling __init__ (avoids aiohttp check)."""
    server = InspectorServer.__new__(InspectorServer)
    server._host = host
    return server


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── _is_sensitive_key ─────────────────────────────────────────────────────────

class TestIsSensitiveKey:
    def test_regex_matched_keys(self):
        for key in ("api_key", "apikey", "token", "secret", "password",
                    "passwd", "auth", "credential", "bearer"):
            assert _is_sensitive_key(key), f"expected sensitive: {key!r}"

    def test_allowlist_only_keys(self):
        # Keys caught by the set but not reliably by the regex alone.
        for key in ("pass", "access_token", "refresh_token", "client_secret",
                    "signing_key", "webhook_secret", "session_token",
                    "hmac_key", "encryption_key"):
            assert _is_sensitive_key(key), f"expected sensitive: {key!r}"

    def test_hyphen_normalised(self):
        assert _is_sensitive_key("api-key")
        assert _is_sensitive_key("signing-key")

    def test_case_insensitive(self):
        for key in ("API_KEY", "ApiKey", "APIKEY", "TOKEN", "SECRET",
                    "Password", "BEARER"):
            assert _is_sensitive_key(key), f"expected sensitive: {key!r}"

    def test_safe_keys_not_scrubbed(self):
        for key in ("model", "provider", "toolsets", "compression",
                    "language", "locale", "ui", "name", "description",
                    "default", "region", "timeout"):
            assert not _is_sensitive_key(key), f"expected safe: {key!r}"


# ── _scrub_sensitive ──────────────────────────────────────────────────────────

class TestScrubSensitive:
    def test_removes_regex_matched_key(self):
        result = _scrub_sensitive({"model": "gpt-4", "api_key": "sk-abc"})
        assert "api_key" not in result
        assert result["model"] == "gpt-4"

    def test_removes_allowlist_key_pass(self):
        result = _scrub_sensitive({"provider": "openai", "pass": "hunter2"})
        assert "pass" not in result
        assert result["provider"] == "openai"

    def test_removes_allowlist_key_apikey_no_separator(self):
        result = _scrub_sensitive({"apikey": "sk-abc", "name": "foo"})
        assert "apikey" not in result
        assert result["name"] == "foo"

    def test_removes_hyphenated_key(self):
        result = _scrub_sensitive({"api-key": "sk-abc", "model": "x"})
        assert "api-key" not in result

    def test_removes_uppercase_key(self):
        result = _scrub_sensitive({"API_KEY": "sk-abc", "model": "x"})
        assert "API_KEY" not in result

    def test_removes_nested_sensitive_key(self):
        result = _scrub_sensitive({
            "model": {"default": "gpt-4", "api_key": "sk-nested"},
        })
        assert "api_key" not in result["model"]
        assert result["model"]["default"] == "gpt-4"

    def test_removes_deeply_nested_key(self):
        result = _scrub_sensitive(
            {"a": {"b": {"c": {"password": "s3cr3t", "ok": 1}}}}
        )
        assert "password" not in result["a"]["b"]["c"]
        assert result["a"]["b"]["c"]["ok"] == 1

    def test_scrubs_inside_list(self):
        result = _scrub_sensitive([{"api_key": "sk-x", "name": "foo"}])
        assert "api_key" not in result[0]
        assert result[0]["name"] == "foo"

    def test_safe_config_passes_through(self):
        config = {
            "model": "claude-3",
            "toolsets": ["web", "terminal"],
            "language": "en",
        }
        assert _scrub_sensitive(config) == config

    def test_depth_guard_returns_unchanged(self):
        # At depth > 20 the object is returned as-is (no infinite recursion).
        result = _scrub_sensitive({"api_key": "should-stay"}, _depth=21)
        assert result == {"api_key": "should-stay"}

    def test_empty_dict(self):
        assert _scrub_sensitive({}) == {}

    def test_non_dict_scalar_passthrough(self):
        assert _scrub_sensitive("plain string") == "plain string"
        assert _scrub_sensitive(42) == 42


# ── CORS headers ──────────────────────────────────────────────────────────────

class TestCorsHeaders:
    def test_loopback_ipv4_returns_cors(self):
        headers = _make_server("127.0.0.1")._cors_headers()
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert "Access-Control-Allow-Methods" in headers

    def test_loopback_ipv6_returns_cors(self):
        headers = _make_server("::1")._cors_headers()
        assert "Access-Control-Allow-Origin" in headers

    def test_loopback_localhost_returns_cors(self):
        headers = _make_server("localhost")._cors_headers()
        assert "Access-Control-Allow-Origin" in headers

    def test_all_interfaces_no_cors(self):
        assert _make_server("0.0.0.0")._cors_headers() == {}

    def test_public_ip_no_cors(self):
        for host in ("192.168.1.100", "10.0.0.1", "203.0.113.5"):
            assert _make_server(host)._cors_headers() == {}, \
                f"Expected no CORS headers for host={host}"


# ── _handle_config_public ─────────────────────────────────────────────────────

class TestHandleConfigPublic:
    """Test the /config/public handler logic without a running HTTP server."""

    def _make_server_with_config(self, config_data: dict):
        server = _make_server()
        server._read_config_yaml = MagicMock(return_value=config_data)

        captured: dict = {}

        def fake_json_response(data, status=200):
            captured["data"] = data
            captured["status"] = status
            return MagicMock()

        server._json_response = fake_json_response
        return server, captured

    def _call(self, server):
        _run(server._handle_config_public(MagicMock()))

    def test_sensitive_key_scrubbed_in_model_section(self):
        server, captured = self._make_server_with_config({
            "model": {"default": "gpt-4", "api_key": "sk-secret", "provider": "openai"},
        })
        self._call(server)
        assert "api_key" not in captured["data"]["model"]
        assert captured["data"]["model"]["provider"] == "openai"

    def test_allowlist_key_apikey_scrubbed(self):
        server, captured = self._make_server_with_config({
            "model": {"default": "gpt-4", "apikey": "sk-123"},
        })
        self._call(server)
        assert "apikey" not in captured["data"]["model"]

    def test_nested_token_scrubbed(self):
        # Use a non-sensitive parent key ("provider_config") so the sub-dict
        # survives and we can assert that only the nested "token" is removed.
        server, captured = self._make_server_with_config({
            "model": {
                "default": "claude",
                "provider_config": {"token": "tok-xyz", "region": "us-east-1"},
            },
        })
        self._call(server)
        pcfg = captured["data"]["model"].get("provider_config", {})
        assert "token" not in pcfg
        assert pcfg.get("region") == "us-east-1"

    def test_credentials_key_itself_is_scrubbed(self):
        # "credentials" is a sensitive key name; the entire sub-dict is removed.
        server, captured = self._make_server_with_config({
            "model": {"default": "gpt-4", "credentials": {"key": "abc"}},
        })
        self._call(server)
        assert "credentials" not in captured["data"]["model"]

    def test_unsafe_top_level_sections_excluded(self):
        server, captured = self._make_server_with_config({
            "model": {"default": "gpt-4"},
            "auth": {"token": "abc"},       # not in safe_keys
            "gateway": {"secret": "xyz"},   # not in safe_keys
            "sessions": {"db": "path"},     # not in safe_keys
            "toolsets": ["web"],
        })
        self._call(server)
        data = captured["data"]
        assert "auth" not in data
        assert "gateway" not in data
        assert "sessions" not in data
        assert data["toolsets"] == ["web"]

    def test_empty_config_returns_empty_dict(self):
        server, captured = self._make_server_with_config({})
        self._call(server)
        assert captured["data"] == {}

    def test_safe_sections_pass_through(self):
        server, captured = self._make_server_with_config({
            "model": {"default": "claude-3"},
            "agent": {"name": "hermes"},
            "toolsets": ["web", "terminal"],
            "compression": {"enabled": True},
            "language": "en",
            "locale": "ko",
            "ui": {"theme": "dark"},
        })
        self._call(server)
        data = captured["data"]
        assert data["model"]["default"] == "claude-3"
        assert data["agent"]["name"] == "hermes"
        assert data["toolsets"] == ["web", "terminal"]
        assert data["compression"]["enabled"] is True
        assert data["language"] == "en"

    def test_pass_key_scrubbed(self):
        server, captured = self._make_server_with_config({
            "model": {"default": "gpt-4", "pass": "hunter2"},
        })
        self._call(server)
        assert "pass" not in captured["data"]["model"]
