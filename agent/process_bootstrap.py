"""Process-level bootstrap helpers for ``run_agent``.

Three concerns, all tied to ``AIAgent`` boot-time / runtime IO setup:

1. **Lazy OpenAI SDK import** — ``_load_openai_cls`` + ``_OpenAIProxy``
   defer the 240ms-ish ``from openai import OpenAI`` cost until first use,
   while preserving ``isinstance(client, OpenAI)`` checks and
   ``patch("run_agent.OpenAI", ...)`` test patterns.

2. **Crash-resistant stdio** — ``_SafeWriter`` wraps stdout/stderr so
   ``OSError: Input/output error`` from broken pipes (systemd, Docker,
   thread teardown races) cannot crash the agent.  ``_install_safe_stdio``
   applies the wrapper.

3. **HTTP proxy resolution** — ``_get_proxy_from_env`` reads
   ``HTTPS_PROXY`` / ``HTTP_PROXY`` / ``ALL_PROXY``;
   ``_get_proxy_for_base_url`` respects ``NO_PROXY`` for the given base URL.

``run_agent`` re-exports every name so existing
``from run_agent import _get_proxy_from_env`` imports keep working
unchanged.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from typing import Optional

from utils import base_url_hostname, normalize_proxy_url


# Cached at module level so we only pay the OpenAI SDK import cost once
# per process (after the first lazy load).
_OPENAI_CLS_CACHE = None


def _load_openai_cls() -> type:
    """Import and cache ``openai.OpenAI``."""
    global _OPENAI_CLS_CACHE
    if _OPENAI_CLS_CACHE is None:
        from openai import OpenAI as _cls
        _OPENAI_CLS_CACHE = _cls
    return _OPENAI_CLS_CACHE


class _OpenAIProxy:
    """Module-level proxy that looks like ``openai.OpenAI`` but imports lazily."""

    __slots__ = ()

    def __call__(self, *args, **kwargs):
        return _load_openai_cls()(*args, **kwargs)

    def __instancecheck__(self, obj):
        return isinstance(obj, _load_openai_cls())

    def __repr__(self):
        return "<lazy openai.OpenAI proxy>"


class _SafeWriter:
    """Transparent stdio wrapper that catches OSError/ValueError from broken pipes.

    When hermes-agent runs as a systemd service, Docker container, or headless
    daemon, the stdout/stderr pipe can become unavailable (idle timeout, buffer
    exhaustion, socket reset). Any print() call then raises
    ``OSError: [Errno 5] Input/output error``, which can crash agent setup or
    run_conversation() — especially via double-fault when an except handler
    also tries to print.

    Additionally, when subagents run in ThreadPoolExecutor threads, the shared
    stdout handle can close between thread teardown and cleanup, raising
    ``ValueError: I/O operation on closed file`` instead of OSError.

    This wrapper delegates all writes to the underlying stream and silently
    catches both OSError and ValueError. It is transparent when the wrapped
    stream is healthy.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def write(self, data):
        try:
            return self._inner.write(data)
        except (OSError, ValueError):
            return len(data) if isinstance(data, str) else 0

    def flush(self):
        try:
            self._inner.flush()
        except (OSError, ValueError):
            pass

    def fileno(self):
        return self._inner.fileno()

    def isatty(self):
        try:
            return self._inner.isatty()
        except (OSError, ValueError):
            return False

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _get_proxy_from_env() -> Optional[str]:
    """Read proxy URL from environment variables.

    Checks HTTPS_PROXY, HTTP_PROXY, ALL_PROXY (and lowercase variants) in order.
    Returns the first valid proxy URL found, or None if no proxy is configured.
    """
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",
                "https_proxy", "http_proxy", "all_proxy"):
        value = os.environ.get(key, "").strip()
        if value:
            return normalize_proxy_url(value)
    return None


def _get_proxy_for_base_url(base_url: Optional[str]) -> Optional[str]:
    """Return an env-configured proxy unless NO_PROXY excludes this base URL."""
    proxy = _get_proxy_from_env()
    if not proxy or not base_url:
        return proxy

    host = base_url_hostname(base_url)
    if not host:
        return proxy

    try:
        if urllib.request.proxy_bypass_environment(host):
            return None
    except Exception:
        pass

    return proxy


# ----------------------------------------------------------------------
# Loopback-safe urlopen — bypasses HTTP_PROXY for 127.0.0.1 / localhost
# ----------------------------------------------------------------------


# Hostnames that should never be routed through HTTP_PROXY. ``::1`` covers
# IPv6 loopback whether or not the URL wraps it in brackets — urllib
# normalizes ``http://[::1]/`` to host ``::1``.
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_url(url: str) -> bool:
    """Return ``True`` if ``url`` targets a loopback address.

    Detection is conservative: only the three canonical loopback hosts
    (``127.0.0.1``, ``localhost``, ``::1``) are considered loopback. The
    full 127.0.0.0/8 range is technically loopback too, but in practice
    nothing in Hermes binds outside the canonical address; checking the
    exact set keeps the false-positive rate at zero.
    """
    try:
        host = urllib.parse.urlparse(url).hostname
    except Exception:
        return False
    if not host:
        return False
    return host.lower() in _LOOPBACK_HOSTS


def loopback_safe_urlopen(url, *args, **kwargs):
    """Drop-in replacement for ``urllib.request.urlopen`` that bypasses
    ``HTTP_PROXY`` / ``HTTPS_PROXY`` when the target is a loopback URL.

    When the user's environment configures a local outbound proxy
    (``HTTP_PROXY=http://127.0.0.1:10808`` is the standard setup for
    v2ray / clash / corporate egress on Windows in particular), urllib
    silently routes *loopback* requests through that proxy. The proxy
    has no way to relay back to a local service on the same host, so it
    returns 502 / 503 — leaving the user staring at a "service down"
    error while the local service is in fact running fine.

    Non-loopback URLs fall through to the normal ``urlopen`` path so
    they continue to honor ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``NO_PROXY``
    as configured.

    See #31421 for the upstream context; complementary defensive layers
    exist in :func:`_get_proxy_for_base_url` (for the OpenAI client) and
    in ``gateway/platforms/base.py`` (for chat platforms).
    """
    if is_loopback_url(url):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(url, *args, **kwargs)
    return urllib.request.urlopen(url, *args, **kwargs)


def _install_safe_stdio() -> None:
    """Wrap stdout/stderr so best-effort console output cannot crash the agent."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and not isinstance(stream, _SafeWriter):
            setattr(sys, stream_name, _SafeWriter(stream))


# Module-level proxy instance — drops in for ``openai.OpenAI``.  Imported as
# ``from agent.process_bootstrap import OpenAI`` (or re-exported via
# ``run_agent`` for legacy tests).
OpenAI = _OpenAIProxy()


__all__ = [
    "OpenAI",
    "_OpenAIProxy",
    "_load_openai_cls",
    "_SafeWriter",
    "_install_safe_stdio",
    "_get_proxy_from_env",
    "_get_proxy_for_base_url",
    "is_loopback_url",
    "loopback_safe_urlopen",
]
