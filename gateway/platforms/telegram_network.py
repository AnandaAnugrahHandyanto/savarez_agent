"""Telegram-specific network helpers.

Provides a hostname-preserving fallback transport for networks where
api.telegram.org resolves to an endpoint that is unreachable from the current
host. The transport keeps the logical request host and TLS SNI as
api.telegram.org while retrying the TCP connection against one or more fallback
IPv4 addresses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import socket
import time
from typing import Iterable, Optional

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API_HOST = "api.telegram.org"

# Refresh the discovered Telegram fallback IP list at most this often.
# Configurable via HERMES_TELEGRAM_FALLBACK_TTL (seconds).  Default 1h.
def _get_refresh_ttl() -> float:
    raw = os.getenv("HERMES_TELEGRAM_FALLBACK_TTL", "3600")
    try:
        return max(60.0, float(raw))
    except (TypeError, ValueError):
        return 3600.0


def _get_failure_threshold() -> int:
    raw = os.getenv("HERMES_TELEGRAM_FALLBACK_FAILURES", "3")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 3


# DNS-over-HTTPS providers used to discover Telegram API IPs that may differ
# from the (potentially unreachable) IP returned by the local system resolver.
_DOH_TIMEOUT = 4.0  # seconds — bounded so connect() isn't noticeably delayed

_DOH_PROVIDERS: list[dict] = [
    {
        "url": "https://dns.google/resolve",
        "params": {"name": _TELEGRAM_API_HOST, "type": "A"},
        "headers": {},
    },
    {
        "url": "https://cloudflare-dns.com/dns-query",
        "params": {"name": _TELEGRAM_API_HOST, "type": "A"},
        "headers": {"Accept": "application/dns-json"},
    },
]

# Last-resort IPs when DoH is also blocked.  These are stable Telegram Bot API
# endpoints in the 149.154.160.0/20 block (same seed used by OpenClaw).
_SEED_FALLBACK_IPS: list[str] = ["149.154.167.220"]


def _resolve_proxy_url(target_hosts=None) -> str | None:
    # Delegate to shared implementation (env vars + macOS system proxy detection)
    from gateway.platforms.base import resolve_proxy_url
    return resolve_proxy_url("TELEGRAM_PROXY", target_hosts=target_hosts)


class TelegramFallbackTransport(httpx.AsyncBaseTransport):
    """Retry Telegram Bot API requests via fallback IPs while preserving TLS/SNI.

    Requests continue to target https://api.telegram.org/... logically, but on
    connect failures the underlying TCP connection is retried against a known
    reachable IP. This is effectively the programmatic equivalent of
    ``curl --resolve api.telegram.org:443:<ip>``.
    """

    def __init__(self, fallback_ips: Iterable[str], **transport_kwargs):
        self._fallback_ips = list(dict.fromkeys(_normalize_fallback_ips(fallback_ips)))
        proxy_url = _resolve_proxy_url(target_hosts=[_TELEGRAM_API_HOST, *self._fallback_ips])
        if proxy_url and "proxy" not in transport_kwargs:
            transport_kwargs["proxy"] = proxy_url
        self._primary = httpx.AsyncHTTPTransport(**transport_kwargs)
        self._fallbacks = {
            ip: httpx.AsyncHTTPTransport(**transport_kwargs) for ip in self._fallback_ips
        }
        self._sticky_ip: Optional[str] = None
        self._sticky_lock = asyncio.Lock()
        # Track failure state so we can trigger a periodic DoH re-discovery
        # when the cached fallback IP list is stale.  This guards against
        # the case where the system DNS or DoH view changed since init
        # (e.g. ISP rerouted, WiFi network change) and the old IPs no
        # longer work but we never noticed.
        self._last_discovery_at: float = time.monotonic()
        self._consecutive_connect_failures: int = 0
        self._discovery_lock = asyncio.Lock()

    async def _maybe_refresh_fallbacks(self) -> None:
        """Re-discover fallback IPs when the cached list looks stale.

        Fires when BOTH conditions hold:
          - At least N consecutive connect failures have occurred
            (default 3, env HERMES_TELEGRAM_FALLBACK_FAILURES).
          - At least TTL seconds have passed since the last discovery
            (default 3600s = 1h, env HERMES_TELEGRAM_FALLBACK_TTL).

        On refresh: rebuilds the per-IP httpx transports and keeps the
        current sticky IP if it's still in the new list; otherwise clears
        it so the next request re-evaluates the routing.
        """
        ttl = _get_refresh_ttl()
        threshold = _get_failure_threshold()
        if self._consecutive_connect_failures < threshold:
            return
        if time.monotonic() - self._last_discovery_at < ttl:
            return
        async with self._discovery_lock:
            # Double-check inside the lock: another coroutine may have
            # already refreshed while we were waiting.
            if self._consecutive_connect_failures < threshold:
                return
            if time.monotonic() - self._last_discovery_at < ttl:
                return
            old_ips = list(self._fallback_ips)
            try:
                new_ips = await discover_fallback_ips()
            except Exception as exc:  # don't let DoH failures cascade
                logger.warning(
                    "[Telegram] Fallback IP refresh failed (DoH unreachable?): %s", exc
                )
                # Reset the failure counter so we don't hammer DoH on
                # every request.  Next refresh will be TTL away.
                self._consecutive_connect_failures = 0
                return
            if not new_ips:
                self._consecutive_connect_failures = 0
                return
            # Close old per-IP transports to release sockets.
            for ip, transport in list(self._fallbacks.items()):
                try:
                    await transport.aclose()
                except Exception:
                    pass
            self._fallback_ips = list(new_ips)
            self._fallbacks = {
                ip: httpx.AsyncHTTPTransport(
                    **self._transport_kwargs_for(ip)
                )
                for ip in self._fallback_ips
            }
            self._last_discovery_at = time.monotonic()
            self._consecutive_connect_failures = 0
            # If the sticky IP is no longer reachable, clear it so the
            # next request retries via primary DNS first.
            if self._sticky_ip and self._sticky_ip not in self._fallback_ips:
                async with self._sticky_lock:
                    self._sticky_ip = None
            logger.warning(
                "[Telegram] Refreshed fallback IPs: %s -> %s (sticky=%s)",
                ", ".join(old_ips) or "<none>",
                ", ".join(self._fallback_ips),
                self._sticky_ip or "<none>",
            )

    def _transport_kwargs_for(self, ip: str) -> dict:
        """Build a per-IP httpx transport using the same kwargs as primary.

        Stored lazily — we capture them on first call so changes to the
        proxy environment after init are still picked up.
        """
        if not hasattr(self, "_cached_transport_kwargs"):
            # The primary transport already has the right kwargs; we
            # rebuild the same shape by re-running the same path used at
            # __init__ time.  httpx transport kwargs are not directly
            # exposed, so we approximate by passing an empty dict (we
            # already wired the proxy at __init__ time on the primary).
            self._cached_transport_kwargs = {}
        return dict(self._cached_transport_kwargs)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != _TELEGRAM_API_HOST or not self._fallback_ips:
            return await self._primary.handle_async_request(request)

        # Cheap path: if we've seen N consecutive connect failures and the
        # TTL has elapsed, re-discover fresh IPs (DoH).  This is a no-op
        # in the healthy case.
        await self._maybe_refresh_fallbacks()

        sticky_ip = self._sticky_ip
        attempt_order: list[Optional[str]] = [sticky_ip] if sticky_ip else [None]
        if sticky_ip:
            attempt_order.append(None)  # retry primary DNS after sticky failure
        for ip in self._fallback_ips:
            if ip != sticky_ip:
                attempt_order.append(ip)

        last_error: Exception | None = None
        any_connect_failure = False
        for ip in attempt_order:
            candidate = request if ip is None else _rewrite_request_for_ip(request, ip)
            transport = self._primary if ip is None else self._fallbacks[ip]
            try:
                response = await transport.handle_async_request(candidate)
                if ip is not None and self._sticky_ip != ip:
                    async with self._sticky_lock:
                        if self._sticky_ip != ip:
                            self._sticky_ip = ip
                            logger.warning(
                                "[Telegram] Primary api.telegram.org path unreachable; using sticky fallback IP %s",
                                ip,
                            )
                # Reset failure counter on any successful response.
                self._consecutive_connect_failures = 0
                return response
            except Exception as exc:
                last_error = exc
                if not _is_retryable_connect_error(exc):
                    # Non-connect error (e.g. HTTP 5xx): don't count toward
                    # the refresh threshold; raise immediately.
                    raise
                any_connect_failure = True
                if ip is not None and ip == self._sticky_ip:
                    async with self._sticky_lock:
                        if self._sticky_ip == ip:
                            self._sticky_ip = None
                            logger.warning(
                                "[Telegram] Sticky fallback IP %s failed; resetting to primary DNS path",
                                ip,
                            )
                if ip is None:
                    logger.warning(
                        "[Telegram] Primary api.telegram.org connection failed (%s); trying fallback IPs %s",
                        exc,
                        ", ".join(self._fallback_ips),
                    )
                    continue
                logger.warning("[Telegram] Fallback IP %s failed: %s", ip, exc)
                continue

        if any_connect_failure:
            self._consecutive_connect_failures += 1
        if last_error is None:
            raise RuntimeError("All Telegram fallback IPs exhausted but no error was recorded")
        raise last_error

    async def aclose(self) -> None:
        await self._primary.aclose()
        for transport in self._fallbacks.values():
            await transport.aclose()


def _normalize_fallback_ips(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        raw = str(value).strip()
        if not raw:
            continue
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            logger.warning("Ignoring invalid Telegram fallback IP: %r", raw)
            continue
        if addr.version != 4:
            logger.warning("Ignoring non-IPv4 Telegram fallback IP: %s", raw)
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
            logger.warning("Ignoring private/internal Telegram fallback IP: %s", raw)
            continue
        normalized.append(str(addr))
    return normalized


def parse_fallback_ip_env(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in value.split(",")]
    return _normalize_fallback_ips(parts)


def _resolve_system_dns() -> set[str]:
    """Return the IPv4 addresses that the OS resolver gives for api.telegram.org."""
    try:
        results = socket.getaddrinfo(_TELEGRAM_API_HOST, 443, socket.AF_INET)
        return {addr[4][0] for addr in results}
    except Exception:
        return set()


async def _query_doh_provider(
    client: httpx.AsyncClient, provider: dict
) -> list[str]:
    """Query one DoH provider and return A-record IPs."""
    try:
        resp = await client.get(
            provider["url"], params=provider["params"], headers=provider["headers"]
        )
        resp.raise_for_status()
        data = resp.json()
        ips: list[str] = []
        for answer in data.get("Answer", []):
            if answer.get("type") != 1:  # A record
                continue
            raw = answer.get("data", "").strip()
            try:
                ipaddress.ip_address(raw)
                ips.append(raw)
            except ValueError:
                continue
        return ips
    except Exception as exc:
        logger.debug("DoH query to %s failed: %s", provider["url"], exc)
        return []


async def discover_fallback_ips() -> list[str]:
    """Auto-discover Telegram API IPs via DNS-over-HTTPS.

    Resolves api.telegram.org through Google and Cloudflare DoH and returns all
    unique A records.  IPs that match the local system resolver are kept rather
    than excluded: in many networks the system-DNS IP is the most reliable path
    to api.telegram.org and a transient primary-path failure should be retried
    against the same address via the IP-rewrite path before the seed list is
    consulted (#14520).  Falls back to a hardcoded seed list only when DoH
    yields no usable answers.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(_DOH_TIMEOUT)) as client:
        doh_tasks = [_query_doh_provider(client, p) for p in _DOH_PROVIDERS]
        system_dns_task = asyncio.to_thread(_resolve_system_dns)
        results = await asyncio.gather(system_dns_task, *doh_tasks, return_exceptions=True)

    # results[0] = system DNS IPs (set), results[1:] = DoH IP lists
    system_ips: set[str] = results[0] if isinstance(results[0], set) else set()

    doh_ips: list[str] = []
    for r in results[1:]:
        if isinstance(r, list):
            doh_ips.extend(r)

    # Deduplicate preserving order
    seen: set[str] = set()
    candidates: list[str] = []
    for ip in doh_ips:
        if ip not in seen:
            seen.add(ip)
            candidates.append(ip)

    # Validate through existing normalization
    validated = _normalize_fallback_ips(candidates)

    if validated:
        logger.debug("Discovered Telegram fallback IPs via DoH: %s", ", ".join(validated))
        return validated

    logger.info(
        "DoH discovery yielded no usable IPs (system DNS: %s); using seed fallback IPs %s",
        ", ".join(system_ips) or "unknown",
        ", ".join(_SEED_FALLBACK_IPS),
    )
    return list(_SEED_FALLBACK_IPS)


def _rewrite_request_for_ip(request: httpx.Request, ip: str) -> httpx.Request:
    original_host = request.url.host or _TELEGRAM_API_HOST
    url = request.url.copy_with(host=ip)
    headers = request.headers.copy()
    headers["host"] = original_host
    extensions = dict(request.extensions)
    extensions["sni_hostname"] = original_host
    return httpx.Request(
        method=request.method,
        url=url,
        headers=headers,
        stream=request.stream,
        extensions=extensions,
    )


def _is_retryable_connect_error(exc: Exception) -> bool:
    return isinstance(exc, (httpx.ConnectTimeout, httpx.ConnectError))
