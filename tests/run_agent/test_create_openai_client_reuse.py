"""Regression guardrail: sequential _create_openai_client calls must not
share a closed transport across invocations.

This is the behavioral twin of test_create_openai_client_kwargs_isolation.py.
That test pins "don't mutate input kwargs" at the syntactic level — it catches
#10933 specifically because the bug mutated ``client_kwargs`` in place. This
test pins the user-visible invariant at the behavioral level: no matter HOW a
future keepalive / transport reimplementation plumbs sockets in, the Nth call
to ``_create_openai_client`` must not hand back a client wrapping a
now-closed httpx transport from an earlier call.

AlexKucera's Discord report (2026-04-16): after ``hermes update`` pulled
#10933, the first chat on a session worked, every subsequent chat failed
with ``APIConnectionError('Connection error.')`` whose cause was
``RuntimeError: Cannot send a request, as the client has been closed``.
That is the exact scenario this test reproduces at object level without a
network, so it runs in CI on every PR.
"""
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent():
    return AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="test/model",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )


def _make_fake_openai_factory(constructed):
    """Return a fake ``OpenAI`` class that records every constructed instance
    along with whatever ``http_client`` it was handed (or ``None`` if the
    caller did not inject one).

    The fake also forwards ``.close()`` calls down to the http_client if one
    is present, mirroring what the real OpenAI SDK does during teardown and
    what would expose the #10933 bug.
    """

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            self._kwargs = kwargs
            self._http_client = kwargs.get("http_client")
            self._closed = False
            constructed.append(self)

        def close(self):
            self._closed = True
            hc = self._http_client
            if hc is not None and hasattr(hc, "close"):
                try:
                    hc.close()
                except Exception:
                    pass

    return _FakeOpenAI


def test_second_create_does_not_wrap_closed_transport_from_first():
    """Back-to-back _create_openai_client calls on the same _client_kwargs
    must not hand call N a closed http_client from call N-1.

    The bug class: call 1 injects an httpx.Client into self._client_kwargs,
    client 1 closes (SDK teardown), its http_client closes with it, call 2
    reads the SAME now-closed http_client from self._client_kwargs and wraps
    it. Every request through client 2 then fails.
    """
    agent = _make_agent()
    constructed: list = []
    fake_openai = _make_fake_openai_factory(constructed)

    # Seed a baseline kwargs dict resembling real runtime state.
    agent._client_kwargs = {
        "api_key": "test-key-value",
        "base_url": "https://api.example.com/v1",
    }

    with patch("run_agent.OpenAI", fake_openai):
        # Call 1 — what _replace_primary_openai_client does at init/rebuild.
        client_a = agent._create_openai_client(
            agent._client_kwargs, reason="initial", shared=True
        )
        # Simulate the SDK teardown that follows a rebuild: the old client's
        # close() is invoked, which closes its underlying http_client if one
        # was injected. This is exactly what _replace_primary_openai_client
        # does via _close_openai_client after a successful rebuild.
        client_a.close()

        # Call 2 — the rebuild path. This is where #10933 crashed on the
        # next real request.
        client_b = agent._create_openai_client(
            agent._client_kwargs, reason="rebuild", shared=True
        )

    assert len(constructed) == 2, f"expected 2 OpenAI constructions, got {len(constructed)}"
    assert constructed[0] is client_a
    assert constructed[1] is client_b

    hc_a = constructed[0]._http_client
    hc_b = constructed[1]._http_client

    # If the implementation does not inject http_client at all, we're safely
    # past the bug class — nothing to share, nothing to close. That's fine.
    if hc_a is None and hc_b is None:
        return

    # If ANY http_client is injected, the two calls MUST NOT share the same
    # object, because call 1's object was closed between calls.
    if hc_a is not None and hc_b is not None:
        assert hc_a is not hc_b, (
            "Regression of #10933: _create_openai_client handed the same "
            "http_client to two sequential constructions. After the first "
            "client is closed (normal SDK teardown on rebuild), the second "
            "wraps a closed transport and every subsequent chat raises "
            "'Cannot send a request, as the client has been closed'."
        )

    # And whatever http_client the LATEST call handed out must not be closed
    # already. This catches implementations that cache the injected client on
    # ``self`` (under any attribute name) and rebuild the SDK client around
    # it even after the previous SDK close closed the cached transport.
    if hc_b is not None:
        is_closed_attr = getattr(hc_b, "is_closed", None)
        if is_closed_attr is not None:
            assert not is_closed_attr, (
                "Regression of #10933: second _create_openai_client returned "
                "a client whose http_client is already closed. New chats on "
                "this session will fail with 'Cannot send a request, as the "
                "client has been closed'."
            )


def test_replace_primary_openai_client_survives_repeated_rebuilds():
    """Full rebuild path: exercise _replace_primary_openai_client three times
    back-to-back and confirm every resulting ``self.client`` is a fresh,
    usable construction rather than a wrapper around a previously-closed
    transport.

    _replace_primary_openai_client is the real rebuild entrypoint — it is
    what runs on 401 credential refresh, pool rotation, and model switch.
    If a future keepalive tweak stores state on ``self`` between calls,
    this test is what notices.
    """
    agent = _make_agent()
    constructed: list = []
    fake_openai = _make_fake_openai_factory(constructed)

    agent._client_kwargs = {
        "api_key": "test-key-value",
        "base_url": "https://api.example.com/v1",
    }

    with patch("run_agent.OpenAI", fake_openai):
        # Seed the initial client so _replace has something to tear down.
        agent.client = agent._create_openai_client(
            agent._client_kwargs, reason="seed", shared=True
        )
        # Three rebuilds in a row. Each one must install a fresh live client.
        for label in ("rebuild_1", "rebuild_2", "rebuild_3"):
            ok = agent._replace_primary_openai_client(reason=label)
            assert ok, f"rebuild {label} returned False"
            cur = agent.client
            assert not cur._closed, (
                f"after rebuild {label}, self.client is already closed — "
                "this breaks the very next chat turn"
            )
            hc = cur._http_client
            if hc is not None:
                is_closed_attr = getattr(hc, "is_closed", None)
                if is_closed_attr is not None:
                    assert not is_closed_attr, (
                        f"after rebuild {label}, self.client.http_client is "
                        "closed — reproduces #10933 (AlexKucera report, "
                        "Discord 2026-04-16)"
                    )

    # All four constructions (seed + 3 rebuilds) should be distinct objects.
    # If two are the same, the rebuild is cacheing the SDK client across
    # teardown, which also reproduces the bug class.
    assert len({id(c) for c in constructed}) == len(constructed), (
        "Some _create_openai_client calls returned the same object across "
        "a teardown — rebuild is not producing fresh clients"
    )


def _stub_proxies(monkeypatch, proxies):
    """Force ``urllib.request.getproxies`` to return ``proxies``.

    This is the ONLY source of proxy configuration for _has_proxy_configured
    and for httpx's trust_env path.  Stubbing it directly (rather than
    mucking with env vars) makes tests independent of the developer's
    actual shell and macOS SystemConfiguration — both of which can inject
    proxies into ``getproxies()`` that the test never intended.
    """
    import urllib.request

    monkeypatch.setattr(urllib.request, "getproxies", lambda: dict(proxies))
    # Also scrub env so an env-var-reading codepath elsewhere cannot fight
    # with the stub.  (_has_proxy_configured routes through getproxies,
    # so this is belt-and-suspenders.)
    for _var in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    ):
        monkeypatch.delenv(_var, raising=False)


def _has_keepalive(transport):
    """Return True when the transport's pool carries ``socket_options``."""
    if transport is None:
        return False
    pool = getattr(transport, "_pool", None)
    return bool(getattr(pool, "_socket_options", None))


def test_create_openai_client_skips_injection_when_https_proxy_set(monkeypatch):
    """With HTTPS_PROXY configured, _create_openai_client must NOT inject
    its own http_client.  Letting the OpenAI SDK build a default
    ``httpx.Client`` (``trust_env=True``) is the only way to honor
    HTTPS_PROXY / HTTP_PROXY / ALL_PROXY together with NO_PROXY, IPv6
    literals, and other edge cases that #11609 exposed in the hand-rolled
    mount rebuild.

    The tradeoff — no keepalive on the proxy path — is accepted: the httpx
    socket in proxy mode is a loopback/LAN connection to the local proxy
    process, and httpx's read timeout still fires if that side stalls.
    """
    agent = _make_agent()
    constructed: list = []
    fake_openai = _make_fake_openai_factory(constructed)
    _stub_proxies(monkeypatch, {"https": "http://127.0.0.1:7897"})

    with patch("run_agent.OpenAI", fake_openai):
        agent._create_openai_client(
            {
                "api_key": "test-key-value",
                "base_url": "https://api.example.com/v1",
            },
            reason="proxy_env_https",
            shared=False,
        )

    assert len(constructed) == 1
    # Pin the design decision explicitly: when a proxy is configured,
    # ``http_client`` is deliberately absent from the kwargs so the SDK
    # builds its own httpx.Client with trust_env=True.  If you see this
    # test failing because http_client became non-None, DO NOT "fix" it by
    # restoring an injected transport — that re-opens #11609.
    assert "http_client" not in constructed[0]._kwargs, (
        "Proxy configured, but http_client was passed to OpenAI().  "
        "Delegation contract broken — the SDK's trust_env path can only "
        "wire up proxy mounts when it owns the httpx.Client."
    )
    assert constructed[0]._http_client is None, (
        "HTTPS_PROXY was set but _create_openai_client still injected an "
        "http_client.  That hands httpx an explicit transport, which makes "
        "it skip env-proxy mount construction and silently direct-connect "
        "— the #11609 bug class."
    )


def test_create_openai_client_skips_injection_for_each_proxy_key(monkeypatch):
    """Any of the three proxy keys (http / https / all) must trigger
    delegation — none of them should leave the keepalive transport in
    place."""
    agent = _make_agent()

    for key in ("http", "https", "all"):
        constructed: list = []
        fake_openai = _make_fake_openai_factory(constructed)
        _stub_proxies(monkeypatch, {key: "http://127.0.0.1:7897"})

        with patch("run_agent.OpenAI", fake_openai):
            agent._create_openai_client(
                {
                    "api_key": "test-key-value",
                    "base_url": "https://api.example.com/v1",
                },
                reason=f"proxy_{key}",
                shared=False,
            )

        assert constructed[0]._http_client is None, (
            f"proxy key {key!r} did not suppress http_client injection"
        )


def test_create_openai_client_keepalive_direct_path_when_no_proxy(monkeypatch):
    """Without any proxy configured, the default transport must still carry
    keepalive.  This is the original #10324 invariant — ensure the
    detect-and-delegate split doesn't accidentally drop keepalive on direct
    connections.
    """
    agent = _make_agent()
    constructed: list = []
    fake_openai = _make_fake_openai_factory(constructed)
    _stub_proxies(monkeypatch, {})

    with patch("run_agent.OpenAI", fake_openai):
        agent._create_openai_client(
            {
                "api_key": "test-key-value",
                "base_url": "https://api.example.com/v1",
            },
            reason="no_proxy_keepalive",
            shared=False,
        )

    hc = constructed[0]._http_client
    assert hc is not None, "no http_client injected on direct-connect path"
    assert _has_keepalive(hc._transport), (
        "direct-connect transport has no socket_options — #10324 regresses"
    )


def test_has_proxy_configured_matches_urllib_getproxies(monkeypatch):
    """_has_proxy_configured must follow urllib.request.getproxies() — the
    same function httpx's trust_env path calls internally.  Using the same
    source means our detection tracks exactly what httpx will honor,
    including macOS SystemConfiguration and Windows registry entries that
    env-only detection would miss.
    """
    _stub_proxies(monkeypatch, {})
    assert AIAgent._has_proxy_configured() is False

    _stub_proxies(monkeypatch, {"https": "http://10.0.0.1:8080"})
    assert AIAgent._has_proxy_configured() is True

    _stub_proxies(monkeypatch, {})
    assert AIAgent._has_proxy_configured() is False

    # NO_PROXY alone should not trigger — that's a refinement, not a proxy.
    _stub_proxies(monkeypatch, {"no": "localhost"})
    assert AIAgent._has_proxy_configured() is False


def test_create_openai_client_skips_injection_for_system_proxy(monkeypatch):
    """When only a system-level proxy is configured (macOS SystemConfig /
    Windows registry, no env var), we must still delegate to httpx.  This
    mirrors how httpx's trust_env path resolves proxies and avoids the
    "detect env only but httpx reads system too" mismatch.
    """
    agent = _make_agent()
    constructed: list = []
    fake_openai = _make_fake_openai_factory(constructed)
    # A "system-only" config is indistinguishable from env at the
    # getproxies() layer — both surface through the same dict.  We stub
    # getproxies so the test doesn't depend on the host's System Settings.
    _stub_proxies(monkeypatch, {"https": "http://10.0.0.1:8080"})

    with patch("run_agent.OpenAI", fake_openai):
        agent._create_openai_client(
            {
                "api_key": "test-key-value",
                "base_url": "https://api.example.com/v1",
            },
            reason="system_proxy",
            shared=False,
        )

    assert constructed[0]._http_client is None, (
        "System-level proxy was configured but _create_openai_client still "
        "injected http_client, which would make httpx skip system-proxy "
        "mount construction (#11609 regression via the system-proxy path)."
    )


# ─── Socket cleanup must cover proxy mounts (#11609 follow-up) ────────────


def _fake_httpx_client_with_mock_sockets(default_sock, mount_sock):
    """Build an object that shape-matches httpx.Client enough for
    _iter_client_sockets to walk it.  Both the default transport's pool
    and a proxy mount's pool expose one fake socket via the connection
    chain: pool._connections[*]._network_stream._sock.
    """
    from types import SimpleNamespace

    def _conn(sock):
        stream = SimpleNamespace(_sock=sock)
        return SimpleNamespace(_network_stream=stream)

    def _transport(sock):
        pool = SimpleNamespace(_connections=[_conn(sock)])
        return SimpleNamespace(_pool=pool)

    class _URLPattern:
        def __init__(self, pattern):
            self._pattern = pattern

    mounts = {_URLPattern("https://"): _transport(mount_sock)}
    return SimpleNamespace(
        _transport=_transport(default_sock),
        _mounts=mounts,
    )


def test_iter_client_sockets_covers_mounts():
    """#11609 introduced proxy mounts; socket enumeration must walk both
    the default transport and every mount, else force-close and dead-check
    sweep the wrong pool on proxied setups.
    """
    from unittest.mock import MagicMock

    from run_agent import AIAgent

    default_sock = MagicMock(name="default_sock")
    mount_sock = MagicMock(name="mount_sock")
    http_client = _fake_httpx_client_with_mock_sockets(default_sock, mount_sock)

    seen = list(AIAgent._iter_client_sockets(http_client))
    assert default_sock in seen, "default transport's socket was not yielded"
    assert mount_sock in seen, (
        "mount transport's socket was not yielded — #11609 proxy connections "
        "would leak CLOSE-WAIT past force_close and evade dead-connection "
        "detection"
    )


def test_force_close_tcp_sockets_closes_mount_sockets():
    """_force_close_tcp_sockets must force-RST sockets in proxy mounts too.
    Otherwise proxied deployments accumulate CLOSE-WAIT on the httpx-to-proxy
    loopback socket whenever the proxy-to-provider side drops.
    """
    from unittest.mock import MagicMock

    from run_agent import AIAgent

    default_sock = MagicMock(name="default_sock")
    mount_sock = MagicMock(name="mount_sock")
    http_client = _fake_httpx_client_with_mock_sockets(default_sock, mount_sock)
    fake_openai = MagicMock(_client=http_client)

    closed = AIAgent._force_close_tcp_sockets(fake_openai)

    assert closed == 2, f"expected 2 closed sockets, got {closed}"
    default_sock.shutdown.assert_called_once()
    default_sock.close.assert_called_once()
    mount_sock.shutdown.assert_called_once()
    mount_sock.close.assert_called_once()
