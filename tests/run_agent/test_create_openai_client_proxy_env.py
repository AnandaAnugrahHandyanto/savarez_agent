"""Regression guard: _create_openai_client must honor HTTP(S)_PROXY env vars.

When #11277 re-landed TCP keepalives, ``_create_openai_client`` began passing
a custom ``transport=httpx.HTTPTransport(...)`` to ``httpx.Client``. httpx only
auto-reads ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``ALL_PROXY`` when
``transport is None`` (see ``Client.__init__``:
``allow_env_proxies = trust_env and transport is None``). As a result, proxy
env vars were silently ignored for the primary chat client, causing requests
to bypass local proxies (Clash, corporate egress, etc.) and hit upstream
directly from the raw interface.

For users on WSL2 + Clash TUN this surfaced as Cloudflare ``cf-mitigated:
challenge`` 403s against ``chatgpt.com/backend-api/codex`` once they upgraded
past #11277. The fix forwards the proxy URL explicitly to ``httpx.Client``
while keeping the keepalive-enabled transport in place.

This test pins that the constructed ``httpx.Client`` mounts an ``HTTPProxy``
pool when a proxy env var is set, AND that the socket-level keepalive
transport is still installed on the no-proxy default path.
"""
from unittest.mock import patch

import httpx

from run_agent import AIAgent, _get_proxy_from_env, _should_bypass_proxy


def _make_agent():
    return AIAgent(
        api_key="test-key",
        base_url="https://chatgpt.com/backend-api/codex",
        provider="openai-codex",
        model="gpt-5.4",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )


def _extract_http_client(client_kwargs: dict):
    """_create_openai_client calls ``OpenAI(**client_kwargs)``; grab the injected client."""
    return client_kwargs.get("http_client")


def test_get_proxy_from_env_prefers_https_then_http_then_all(monkeypatch):
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    assert _get_proxy_from_env() is None

    monkeypatch.setenv("ALL_PROXY", "http://all:1")
    assert _get_proxy_from_env() == "http://all:1"

    monkeypatch.setenv("HTTP_PROXY", "http://http:2")
    assert _get_proxy_from_env() == "http://http:2"

    monkeypatch.setenv("HTTPS_PROXY", "http://https:3")
    assert _get_proxy_from_env() == "http://https:3"


def test_get_proxy_from_env_ignores_blank_values(monkeypatch):
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "   ")
    monkeypatch.setenv("HTTP_PROXY", "http://real-proxy:8080")
    assert _get_proxy_from_env() == "http://real-proxy:8080"


def test_get_proxy_from_env_normalizes_socks_alias(monkeypatch):
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:1080/")
    assert _get_proxy_from_env() == "socks5://127.0.0.1:1080/"


@patch("run_agent.OpenAI")
def test_create_openai_client_routes_via_proxy_when_env_set(mock_openai, monkeypatch):
    """With HTTPS_PROXY set, the custom httpx.Client must mount an HTTPProxy pool.

    This is the WSL2 + Clash / corporate-egress case. Before the fix, the custom
    transport suppressed httpx's env-proxy auto-detection, so requests bypassed
    the proxy entirely.
    """
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")

    agent = _make_agent()
    kwargs = {
        "api_key": "test-key",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    agent._create_openai_client(kwargs, reason="test", shared=False)

    forwarded = mock_openai.call_args.kwargs
    http_client = _extract_http_client(forwarded)
    assert isinstance(http_client, httpx.Client), (
        "Expected _create_openai_client to inject a keepalive-enabled "
        "httpx.Client; got %r" % (http_client,)
    )
    # Verify a proxy mount exists. httpx Client(proxy=...) rewrites _mounts so
    # the proxied pool (HTTPProxy) sits alongside the base transport.
    proxied_pools = [
        type(mount._pool).__name__
        for mount in http_client._mounts.values()
        if mount is not None and hasattr(mount, "_pool")
    ]
    assert "HTTPProxy" in proxied_pools, (
        "Expected httpx.Client to route through HTTPProxy when HTTPS_PROXY is "
        "set; found pools: %r" % (proxied_pools,)
    )
    http_client.close()


@patch("run_agent.OpenAI")
def test_create_openai_client_no_proxy_when_env_unset(mock_openai, monkeypatch):
    """Without proxy env vars, the keepalive transport must still be installed
    and no HTTPProxy mount should exist."""
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)

    agent = _make_agent()
    kwargs = {
        "api_key": "test-key",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    agent._create_openai_client(kwargs, reason="test", shared=False)

    forwarded = mock_openai.call_args.kwargs
    http_client = _extract_http_client(forwarded)
    assert isinstance(http_client, httpx.Client)
    pool_types = [
        type(mount._pool).__name__
        for mount in http_client._mounts.values()
        if mount is not None and hasattr(mount, "_pool")
    ]
    assert "HTTPProxy" not in pool_types, (
        "No proxy env set but httpx.Client still mounted HTTPProxy; "
        "pools were %r" % (pool_types,)
    )
    http_client.close()


# ---------------------------------------------------------------------------
# _should_bypass_proxy unit tests (#14451)
# ---------------------------------------------------------------------------

def test_should_bypass_proxy_no_env(monkeypatch):
    """Without no_proxy set, nothing is bypassed."""
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    assert _should_bypass_proxy("http://localhost:11434") is False
    assert _should_bypass_proxy("https://api.openai.com") is False


def test_should_bypass_proxy_localhost_match(monkeypatch):
    """no_proxy=localhost should match localhost URLs."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", "localhost")
    assert _should_bypass_proxy("http://localhost:11434/v1") is True
    assert _should_bypass_proxy("https://api.openai.com/v1") is False


def test_should_bypass_proxy_remote_still_proxied(monkeypatch):
    """Remote hosts must not match a localhost-only no_proxy."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    assert _should_bypass_proxy("https://api.anthropic.com/v1") is False


def test_should_bypass_proxy_wildcard(monkeypatch):
    """no_proxy=* should bypass all hosts."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", "*")
    assert _should_bypass_proxy("https://api.openai.com/v1") is True
    assert _should_bypass_proxy("http://localhost:11434") is True


def test_should_bypass_proxy_domain_suffix(monkeypatch):
    """Domain suffixes (with or without leading dot) should match subdomains."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", ".example.com")
    assert _should_bypass_proxy("https://api.example.com/v1") is True
    assert _should_bypass_proxy("https://example.com/v1") is True
    assert _should_bypass_proxy("https://notexample.com/v1") is False


def test_should_bypass_proxy_case_insensitive(monkeypatch):
    """Pattern matching must be case-insensitive."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", "LOCALHOST")
    assert _should_bypass_proxy("http://Localhost:8080") is True


def test_should_bypass_proxy_reads_NO_PROXY_uppercase(monkeypatch):
    """NO_PROXY (uppercase) should be respected when no_proxy is absent."""
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setenv("NO_PROXY", "localhost")
    assert _should_bypass_proxy("http://localhost:11434") is True


def test_should_bypass_proxy_empty_string(monkeypatch):
    """Empty no_proxy should not bypass anything."""
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("no_proxy", "  ")
    assert _should_bypass_proxy("http://localhost:11434") is False


# ---------------------------------------------------------------------------
# Integration: _build_keepalive_http_client respects no_proxy (#14451)
# ---------------------------------------------------------------------------

@patch("run_agent.OpenAI")
def test_create_openai_client_no_proxy_bypasses_localhost(mock_openai, monkeypatch):
    """With HTTPS_PROXY set but no_proxy=localhost, a localhost base_url must
    NOT route through the proxy."""
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("no_proxy", "localhost")

    agent = _make_agent()
    kwargs = {
        "api_key": "test-key",
        "base_url": "http://localhost:11434/v1",
    }
    agent._create_openai_client(kwargs, reason="test", shared=False)

    forwarded = mock_openai.call_args.kwargs
    http_client = _extract_http_client(forwarded)
    assert isinstance(http_client, httpx.Client)
    pool_types = [
        type(mount._pool).__name__
        for mount in http_client._mounts.values()
        if mount is not None and hasattr(mount, "_pool")
    ]
    assert "HTTPProxy" not in pool_types, (
        "no_proxy=localhost should suppress proxy for localhost base_url; "
        "pools were %r" % (pool_types,)
    )
    http_client.close()


@patch("run_agent.OpenAI")
def test_create_openai_client_no_proxy_still_proxies_remote(mock_openai, monkeypatch):
    """With HTTPS_PROXY set and no_proxy=localhost, a remote base_url must
    still route through the proxy."""
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("no_proxy", "localhost")

    agent = _make_agent()
    kwargs = {
        "api_key": "test-key",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    agent._create_openai_client(kwargs, reason="test", shared=False)

    forwarded = mock_openai.call_args.kwargs
    http_client = _extract_http_client(forwarded)
    assert isinstance(http_client, httpx.Client)
    proxied_pools = [
        type(mount._pool).__name__
        for mount in http_client._mounts.values()
        if mount is not None and hasattr(mount, "_pool")
    ]
    assert "HTTPProxy" in proxied_pools, (
        "Remote base_url should still use proxy when no_proxy only lists "
        "localhost; pools were %r" % (proxied_pools,)
    )
    http_client.close()
