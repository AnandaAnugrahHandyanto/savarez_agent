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
import os
from unittest.mock import patch

import httpx

from run_agent import AIAgent, _get_proxy_from_env, _get_proxy_for_base_url
from utils import configure_extra_ca_bundle


def _clear_ca_env(monkeypatch):
    for key in (
        "HERMES_EXTRA_CA_CERTS",
        "NODE_EXTRA_CA_CERTS",
        "HERMES_CA_BUNDLE",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "_HERMES_CA_BASE_BUNDLE",
    ):
        if key in os.environ:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, "")


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
    _clear_ca_env(monkeypatch)
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
    _clear_ca_env(monkeypatch)
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


def test_get_proxy_for_base_url_returns_none_when_host_bypassed(monkeypatch):
    """NO_PROXY must suppress the proxy for matching base_urls.

    Regression for #14966: users running a local inference endpoint
    (Ollama, LM Studio, llama.cpp) with a global HTTPS_PROXY would see
    the keepalive client route loopback traffic through the proxy, which
    typically answers 502 for local hosts. NO_PROXY should opt those
    hosts out via stdlib ``urllib.request.proxy_bypass_environment``.
    """
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy",
                "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,192.168.0.0/16")

    # Local endpoint — must bypass the proxy.
    assert _get_proxy_for_base_url("http://127.0.0.1:11434/v1") is None
    assert _get_proxy_for_base_url("http://localhost:1234/v1") is None

    # Non-local endpoint — proxy still applies.
    assert _get_proxy_for_base_url("https://api.openai.com/v1") == "http://127.0.0.1:7897"


def test_get_proxy_for_base_url_returns_proxy_when_no_proxy_unset(monkeypatch):
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy",
                "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://corp:8080")
    assert _get_proxy_for_base_url("http://127.0.0.1:11434/v1") == "http://corp:8080"


def test_get_proxy_for_base_url_returns_none_when_proxy_unset(monkeypatch):
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy",
                "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    assert _get_proxy_for_base_url("http://127.0.0.1:11434/v1") is None
    assert _get_proxy_for_base_url("https://api.openai.com/v1") is None


@patch("run_agent.OpenAI")
def test_create_openai_client_bypasses_proxy_for_no_proxy_host(mock_openai, monkeypatch):
    """E2E: with HTTPS_PROXY + NO_PROXY=localhost, a local base_url gets a
    keepalive client with NO HTTPProxy mount."""
    _clear_ca_env(monkeypatch)
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy",
                "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")

    agent = _make_agent()
    kwargs = {
        "api_key": "***",
        "base_url": "http://127.0.0.1:11434/v1",
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
        "NO_PROXY host must not route through HTTPProxy; pools were %r" % (pool_types,)
    )
    http_client.close()


def test_extra_ca_bundle_merges_even_when_ssl_cert_file_preconfigured(monkeypatch, tmp_path):
    """Gateway startup order: SSL_CERT_FILE pre-set, HERMES_EXTRA_CA_CERTS loaded later.

    Hermes must merge the extra CA instead of treating an existing SSL_CERT_FILE
    as final. The generated bundle must contain both base and extra certs.
    """
    _clear_ca_env(monkeypatch)
    base_ca = tmp_path / "base-ca.pem"
    base_ca.write_text("BASE-CA-CONTENT")
    extra_ca = tmp_path / "extra-ca.pem"
    extra_ca.write_text("EXTRA-CA-CONTENT")
    bundle_path = tmp_path / "merged-bundle.pem"

    monkeypatch.setenv("SSL_CERT_FILE", str(base_ca))
    monkeypatch.setenv("HERMES_EXTRA_CA_CERTS", str(extra_ca))
    monkeypatch.setenv("HERMES_CA_BUNDLE", str(bundle_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = configure_extra_ca_bundle()

    assert result == str(bundle_path)
    merged = bundle_path.read_text()
    assert "BASE-CA-CONTENT" in merged
    assert "EXTRA-CA-CONTENT" in merged
    assert os.environ["SSL_CERT_FILE"] == str(bundle_path)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(bundle_path)


def test_extra_ca_bundle_is_idempotent_when_ssl_cert_file_is_generated_bundle(monkeypatch, tmp_path):
    """Repeated calls must not duplicate extra CA contents."""
    _clear_ca_env(monkeypatch)
    base_ca = tmp_path / "base-ca.pem"
    base_ca.write_text("BASE-CA-CONTENT")
    extra_ca = tmp_path / "extra-ca.pem"
    extra_ca.write_text("EXTRA-CA-CONTENT")
    bundle_path = tmp_path / "merged-bundle.pem"

    monkeypatch.setenv("SSL_CERT_FILE", str(base_ca))
    monkeypatch.setenv("HERMES_EXTRA_CA_CERTS", str(extra_ca))
    monkeypatch.setenv("HERMES_CA_BUNDLE", str(bundle_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    first_result = configure_extra_ca_bundle()
    first_content = bundle_path.read_text()

    second_result = configure_extra_ca_bundle()
    second_content = bundle_path.read_text()

    assert first_result == str(bundle_path)
    assert second_result == str(bundle_path)
    assert first_content == second_content
    assert first_content.count("EXTRA-CA-CONTENT") == 1, (
        "Extra CA content must not be duplicated on repeated calls"
    )
