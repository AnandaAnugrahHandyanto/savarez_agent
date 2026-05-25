"""Regression tests for #31599 — Telegram proxy-path connection-pool limits.

Behind a flaky local HTTP proxy the gateway's Telegram adapter accumulated
half-closed (``CLOSED`` in lsof) sockets in the httpx general pool because
PTB's ``HTTPXRequest`` leaves ``keepalive_expiry`` at httpx's 5s default. Over
a day or two the leaked fds walked into the macOS 256-fd limit and every send
failed with ``httpx.ConnectError: All connection attempts failed``.

``_proxy_request_limits`` bounds idle keepalive connections and expires idle
sockets aggressively (reusing the gateway-wide CLOSE_WAIT tuning from #18451)
while keeping ``max_connections`` at the adapter's configured ceiling so
concurrent sends are never throttled.
"""

from __future__ import annotations

import pytest

from gateway.platforms.telegram import _proxy_request_limits


def test_preserves_max_connections_but_bounds_keepalive() -> None:
    """The configured pool ceiling is preserved, but idle keepalive is bounded
    and idle sockets expire well before httpx's 5s default."""
    limits = _proxy_request_limits(512)

    assert limits is not None
    assert limits.max_connections == 512, "concurrent-send ceiling must be preserved"
    # Bounded idle pool + sub-5s expiry is what prevents the CLOSED-socket leak.
    assert limits.max_keepalive_connections == 10
    assert limits.keepalive_expiry == 2.0
    assert limits.keepalive_expiry < 5.0


def test_honours_shared_keepalive_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operators can retune via the same env vars the other gateway adapters
    use (#18451), without a Telegram-specific knob."""
    monkeypatch.setenv("HERMES_GATEWAY_HTTPX_MAX_KEEPALIVE", "3")
    monkeypatch.setenv("HERMES_GATEWAY_HTTPX_KEEPALIVE_EXPIRY", "0.5")

    limits = _proxy_request_limits(256)

    assert limits is not None
    assert limits.max_connections == 256
    assert limits.max_keepalive_connections == 3
    assert limits.keepalive_expiry == 0.5
