"""SSL CA certificate diagnostic guard.

Pre-flight check that runs before any HTTP client (OpenAI, Anthropic,
etc.) is constructed.  If the system's CA bundle — managed by ``certifi``
— is missing or empty, the agent fails fast with an actionable error
instead of entering a crash-loop for every incoming message.
"""

from __future__ import annotations

import logging
import os
import ssl
import sys

logger = logging.getLogger(__name__)


def _ssl_err(message: str) -> "SSLConfigurationError":
    """Build an :class:`agent.errors.SSLConfigurationError`."""
    from agent.errors import SSLConfigurationError

    return SSLConfigurationError(message)


def check_ssl_ca_bundle() -> None:
    """Verify the CA certificate bundle is loadable.

    Raises :class:`~agent.errors.SSLConfigurationError` when the bundle
    is missing, empty, or corrupt, so the caller can surface a clear
    remediation message instead of an opaque ``RuntimeError``.
    """
    try:
        import certifi  # noqa: SC100
    except ImportError:
        raise _ssl_err(
            "The 'certifi' package is not installed. This usually means the "
            "virtual environment is stale after a git pull."
        )

    ca_bundle = certifi.where()
    if not ca_bundle or not os.path.isfile(ca_bundle) or os.path.getsize(ca_bundle) == 0:
        raise _ssl_err(
            f"CA certificate bundle is missing or empty: {ca_bundle}."
        )

    # Try to load the bundle into an SSL context — this is the operation
    # that actually fails when certifi is stale or the venv is broken.
    try:
        ctx = ssl.create_default_context(cafile=ca_bundle)
    except Exception as exc:
        raise _ssl_err(
            f"CA certificate bundle at {ca_bundle} cannot be loaded: {exc}."
        )

    # Paranoid check: ensure at least one certificate was parsed.
    # On macOS the system trust store may still work even without
    # certifi, so if this check fails we fall back to a system-only
    # context before declaring the environment broken.
    if not ctx.get_ca_certs():
        try:
            fallback = ssl.create_default_context()
            if not fallback.get_ca_certs():
                raise _ssl_err(
                    f"CA certificate bundle at {ca_bundle} is empty and "
                    "no system CA certificates are available."
                )
            logger.debug(
                "certifi bundle at %s is empty but system CA store is ok", ca_bundle
            )
        except Exception:
            raise  # re-raise whatever _ssl_err produced


# Re-export so tests can patch
try:
    from agent.errors import SSLConfigurationError
except ImportError:
    SSLConfigurationError = Exception  # type: ignore[misc,assignment]
