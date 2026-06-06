"""Tests for TelegramFallbackTransport periodic DoH refresh.

Covers the bug fixed in PR: gateway was pinning the same fallback IP
for the entire lifetime of the gateway process even when the local
network conditions changed (ISP reroute, WiFi network change).  The
fix adds a TTL + failure-threshold check that re-runs
discover_fallback_ips() and rebuilds the per-IP transports.
"""

import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest

from gateway.platforms.telegram_network import (
    TelegramFallbackTransport,
    _TELEGRAM_API_HOST,
)


def _make_transport(ips=None):
    """Construct a transport bypassing the real httpx init."""
    ips = ips or ["1.2.3.4", "5.6.7.8"]
    t = TelegramFallbackTransport.__new__(TelegramFallbackTransport)
    t._fallback_ips = list(ips)
    t._sticky_ip = None
    t._sticky_lock = asyncio.Lock()
    t._last_discovery_at = time.monotonic()
    t._consecutive_connect_failures = 0
    t._discovery_lock = asyncio.Lock()
    t._cached_transport_kwargs = {}
    t._primary = AsyncMock()
    t._primary.aclose = AsyncMock()
    # Per-IP transport mocks with async aclose
    t._fallbacks = {}
    for ip in ips:
        m = AsyncMock()
        m.aclose = AsyncMock()
        t._fallbacks[ip] = m
    return t


def _make_failing_transport_mock() -> AsyncMock:
    """Construct an AsyncMock transport that fails connect on use.

    Used by end-to-end tests that exercise the merge path, which
    builds new transports via ``httpx.AsyncHTTPTransport(**kwargs)``.
    We replace the class itself with a factory that returns these
    mocks so no real TCP connect is ever attempted.
    """
    m = AsyncMock()
    m.aclose = AsyncMock()
    m.handle_async_request = AsyncMock(
        side_effect=httpx.ConnectError("simulated timeout")
    )
    return m


class TestMaybeRefreshFallbacks:
    def test_no_refresh_when_failures_below_threshold(self):
        t = _make_transport()
        t._consecutive_connect_failures = 2  # below 3
        t._last_discovery_at = time.monotonic() - 7200  # past TTL
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=["9.9.9.9"]),
        ) as m:
            asyncio.run(t._maybe_refresh_fallbacks())
            m.assert_not_called()
            assert t._fallback_ips == ["1.2.3.4", "5.6.7.8"]

    def test_no_refresh_when_ttl_not_elapsed(self):
        t = _make_transport()
        t._consecutive_connect_failures = 5
        t._last_discovery_at = time.monotonic()  # just refreshed
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=["9.9.9.9"]),
        ) as m:
            asyncio.run(t._maybe_refresh_fallbacks())
            m.assert_not_called()

    def test_refresh_fires_when_threshold_and_ttl_met(self):
        t = _make_transport(ips=["1.1.1.1"])
        # Capture the OLD transport mocks so we can verify they were closed
        old_aclose_mocks = list(t._fallbacks["1.1.1.1"].aclose.call_args_list)
        t._consecutive_connect_failures = 3
        t._last_discovery_at = time.monotonic() - 7200
        new_ips = ["9.9.9.9", "8.8.8.8"]
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=new_ips),
        ), patch.object(
            t, "_transport_kwargs_for", return_value={}
        ):
            asyncio.run(t._maybe_refresh_fallbacks())
            # Partial-update merge: new IPs go first, then any old IPs
            # that were not in the new list are preserved (the 1.1.1.1
            # we started with is kept as a survivor even though DoH
            # didn't return it).
            assert t._fallback_ips[:2] == new_ips
            assert t._fallback_ips[2:] == ["1.1.1.1"]
            assert t._consecutive_connect_failures == 0
            assert "9.9.9.9" in t._fallbacks
            assert "8.8.8.8" in t._fallbacks
            # After refresh, old per-IP transport was closed (its IP
            # was kept in the merged list as a survivor, but a fresh
            # transport was constructed for it via the merge path).
            assert old_aclose_mocks == []  # never awaited before
            t._fallbacks["1.1.1.1"].aclose.assert_not_awaited()  # type: ignore[attr-defined]

    def test_refresh_keeps_sticky_if_still_in_list(self):
        t = _make_transport(ips=["1.1.1.1"])
        t._sticky_ip = "5.6.7.8"
        t._consecutive_connect_failures = 3
        t._last_discovery_at = time.monotonic() - 7200
        new_ips = ["5.6.7.8", "9.9.9.9"]
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=new_ips),
        ), patch.object(
            t, "_transport_kwargs_for", return_value={}
        ):
            asyncio.run(t._maybe_refresh_fallbacks())
            assert t._sticky_ip == "5.6.7.8"

    def test_refresh_clears_sticky_if_not_in_new_list(self):
        t = _make_transport(ips=["1.1.1.1"])
        t._sticky_ip = "5.6.7.8"  # not in new list
        t._consecutive_connect_failures = 3
        t._last_discovery_at = time.monotonic() - 7200
        new_ips = ["9.9.9.9", "8.8.8.8"]
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=new_ips),
        ), patch.object(
            t, "_transport_kwargs_for", return_value={}
        ):
            asyncio.run(t._maybe_refresh_fallbacks())
            assert t._sticky_ip is None

    def test_refresh_swallows_doh_exception(self):
        t = _make_transport()
        original_ips = list(t._fallback_ips)
        t._consecutive_connect_failures = 5
        t._last_discovery_at = time.monotonic() - 7200
        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=3,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(side_effect=RuntimeError("DoH unreachable")),
        ):
            # Should NOT raise
            asyncio.run(t._maybe_refresh_fallbacks())
            assert t._consecutive_connect_failures == 0
            assert t._fallback_ips == original_ips


class TestMergeFallbackIps:
    """The re-discovery path must be partial-update tolerant: a partial DoH
    response (one provider returned IPs, another timed out) should preserve
    any still-working IPs from the existing list rather than drop them.
    """

    def test_merge_preserves_existing_ips_not_in_new_list(self):
        t = _make_transport(ips=["1.1.1.1", "2.2.2.2", "3.3.3.3"])
        asyncio.run(t._merge_fallback_ips(["9.9.9.9"]))
        # New IP first, then surviving old IPs.
        assert t._fallback_ips[0] == "9.9.9.9"
        assert set(t._fallback_ips[1:]) == {"1.1.1.1", "2.2.2.2", "3.3.3.3"}

    def test_merge_deduplicates(self):
        t = _make_transport(ips=["1.1.1.1", "2.2.2.2"])
        asyncio.run(t._merge_fallback_ips(["1.1.1.1", "9.9.9.9"]))
        # 1.1.1.1 appears in both — must not duplicate.
        assert t._fallback_ips.count("1.1.1.1") == 1
        assert "9.9.9.9" in t._fallback_ips

    def test_merge_keeps_transport_for_surviving_ip(self):
        t = _make_transport(ips=["1.1.1.1", "2.2.2.2"])
        surviving_transport = t._fallbacks["1.1.1.1"]
        asyncio.run(t._merge_fallback_ips(["1.1.1.1", "9.9.9.9"]))
        # The surviving IP's old transport must NOT be closed (we
        # keep it; the next request can use it).
        surviving_transport.aclose.assert_not_awaited()  # type: ignore[attr-defined]

    def test_merge_caps_list_size(self):
        """When many refresh cycles have accumulated survivors, the
        cap drops the oldest ones (the tail of the merged list)."""
        t = _make_transport(ips=[f"10.0.0.{i}" for i in range(1, 17)])
        # Add one new IP — total 17, which exceeds the cap of 16.
        asyncio.run(t._merge_fallback_ips(["9.9.9.9"]))
        assert len(t._fallback_ips) == 16
        # The newest IP is at the head, the oldest survivor is dropped.
        assert t._fallback_ips[0] == "9.9.9.9"
        assert "10.0.0.16" not in t._fallback_ips  # oldest, dropped

    def test_merge_opens_transport_for_genuinely_new_ip(self):
        t = _make_transport(ips=["1.1.1.1"])
        asyncio.run(t._merge_fallback_ips(["9.9.9.9"]))
        # New transport was constructed for the new IP.
        assert "9.9.9.9" in t._fallbacks
        new_transport = t._fallbacks["9.9.9.9"]
        assert new_transport is not None


class TestEndToEndRefresh:
    """Drive ``handle_async_request`` directly to verify that an IP-expiry
    scenario (all fallback IPs start failing) actually triggers the
    periodic re-discovery and that the new IPs become usable.
    """

    def _build_request(self) -> httpx.Request:
        return httpx.Request(
            "GET", f"https://{_TELEGRAM_API_HOST}/botTEST/getMe"
        )

    def _connect_error(self) -> httpx.ConnectError:
        return httpx.ConnectError("simulated timeout")

    @pytest.mark.asyncio
    async def test_ip_expiry_triggers_refresh_and_updates_fallbacks(self):
        """All fallbacks start failing with ConnectError.  After the
        failure threshold is reached, ``discover_fallback_ips`` is
        called and the new IPs are wired into ``_fallbacks`` so the
        next request can use them.
        """
        ips = ["10.0.0.1", "10.0.0.2"]
        t = _make_transport(ips=ips)

        # Make every per-IP transport fail with ConnectError.
        for transport in t._fallbacks.values():
            transport.handle_async_request = AsyncMock(
                side_effect=self._connect_error()
            )
        # Primary also fails — we want the request to fail outright.
        t._primary.handle_async_request = AsyncMock(
            side_effect=self._connect_error()
        )

        # Pre-condition: TTL elapsed, threshold at exactly 1.
        t._last_discovery_at = time.monotonic() - 7200
        t._consecutive_connect_failures = 1

        new_ips = ["99.99.99.1", "99.99.99.2"]

        def _stub_with_failing_transport(ip: str) -> dict:
            """Return kwargs for the (patched) AsyncHTTPTransport
            factory.  The patched factory ignores the kwargs and
            returns a failing mock transport instead."""
            return {}

        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=1,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=new_ips),
        ) as discover_mock, patch.object(
            t, "_transport_kwargs_for", new=_stub_with_failing_transport
        ), patch(
            "gateway.platforms.telegram_network.httpx.AsyncHTTPTransport",
            side_effect=lambda **kw: _make_failing_transport_mock(),
        ):
            req = self._build_request()
            with pytest.raises(httpx.ConnectError):
                await t.handle_async_request(req)
            # The failure path called _maybe_refresh_fallbacks, which
            # in turn called discover_fallback_ips exactly once.
            discover_mock.assert_awaited_once()
            # The new IPs are now at the head of the fallback list
            # (partial-update merge: new first, then survivors).
            assert t._fallback_ips[: len(new_ips)] == new_ips
            # The old IPs are still kept as survivors (partial-update
            # tolerance) — they may still work.
            assert set(ips).issubset(set(t._fallback_ips))
            # Per-IP transports for the new IPs were created.
            for ip in new_ips:
                assert ip in t._fallbacks

    @pytest.mark.asyncio
    async def test_no_refresh_when_below_threshold_end_to_end(self):
        """If the failure threshold isn't met, refresh must not fire
        even when TTL has elapsed.  This protects against DoH hammering.
        """
        ips = ["10.0.0.1"]
        t = _make_transport(ips=ips)
        t._fallbacks["10.0.0.1"].handle_async_request = AsyncMock(
            side_effect=self._connect_error()
        )
        t._primary.handle_async_request = AsyncMock(
            return_value=MagicMock(status_code=200)
        )
        t._last_discovery_at = time.monotonic() - 7200
        t._consecutive_connect_failures = 0  # below threshold (default 1)

        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=1,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=AsyncMock(return_value=["99.99.99.1"]),
        ) as discover_mock, patch.object(
            t, "_transport_kwargs_for", return_value={}
        ):
            req = self._build_request()
            response = await t.handle_async_request(req)
            assert response.status_code == 200
            # Refresh did NOT fire — primary recovered, counter was 0
            # and the request actually succeeded.
            discover_mock.assert_not_awaited()
            assert t._fallback_ips == ips

    @pytest.mark.asyncio
    async def test_concurrent_failures_do_not_double_trigger_refresh(self):
        """When N requests fail concurrently, ``discover_fallback_ips``
        must be called at most once.  The discovery lock guarantees this.
        """
        t = _make_transport(ips=["10.0.0.1"])
        t._fallbacks["10.0.0.1"].handle_async_request = AsyncMock(
            side_effect=self._connect_error()
        )
        t._primary.handle_async_request = AsyncMock(
            side_effect=self._connect_error()
        )
        t._last_discovery_at = time.monotonic() - 7200

        # Slow down discover_fallback_ips so concurrent calls would
        # actually race if the lock were broken.  Wrapped in a Mock so
        # we can assert on call_count after the test.
        async def slow_discover_impl():
            await asyncio.sleep(0.1)
            return ["99.99.99.1"]

        discover_mock = AsyncMock(side_effect=slow_discover_impl)

        with patch(
            "gateway.platforms.telegram_network._get_refresh_ttl",
            return_value=3600.0,
        ), patch(
            "gateway.platforms.telegram_network._get_failure_threshold",
            return_value=1,
        ), patch(
            "gateway.platforms.telegram_network.discover_fallback_ips",
            new=discover_mock,
        ), patch(
            "gateway.platforms.telegram_network.httpx.AsyncHTTPTransport",
            side_effect=lambda **kw: _make_failing_transport_mock(),
        ):
            t._consecutive_connect_failures = 1  # at threshold
            # Fire 5 requests concurrently; each will hit _maybe_refresh.
            reqs = [self._build_request() for _ in range(5)]
            results = await asyncio.gather(
                *[t.handle_async_request(r) for r in reqs],
                return_exceptions=True,
            )
            # All should have raised ConnectError.
            assert all(isinstance(r, httpx.ConnectError) for r in results)
            # discover_fallback_ips must have been called exactly once
            # because the discovery lock serializes the refresh.
            assert discover_mock.call_count == 1, (
                f"Expected 1 discovery call under the lock, got "
                f"{discover_mock.call_count}"
            )
