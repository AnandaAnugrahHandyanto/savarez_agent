"""
Client-side fixed-window rate limiter for Hermes Agent.

Paces outgoing API calls to stay within a configurable requests-per-minute
ceiling, preventing 429 errors before they occur.

Core classes:
- FixedWindowRateLimiter: Fixed window with full 60s wait after limit reached
- ProviderRateLimiterRegistry: Case-insensitive, prefix-aware provider routing
- make_registry(): Factory reads config + env var

Lock safety: time.sleep() always runs outside the lock.
Default: rpm=0 (disabled). Zero behaviour change for existing users.
No external dependencies — pure stdlib.
"""

import collections
import os
import threading
import time
from typing import Dict


def _validate_rpm(rpm: any) -> int:
    """
    Validate and normalize RPM value.

    Handles invalid values gracefully:
    - Non-integer values → 0 (disabled)
    - Negative values → 0 (disabled)
    - Values > 3600 → 3600 (max allowed)
    - None/missing → 0 (disabled)

    Args:
        rpm: RPM value from config or env var

    Returns:
        Validated RPM value (0-3600)
    """
    try:
        rpm_int = int(rpm)
    except (TypeError, ValueError):
        return 0  # Invalid value → disabled

    if rpm_int < 0:
        return 0  # Negative → disabled
    if rpm_int > 3600:
        return 3600  # Cap at max

    return rpm_int


class _NoOpLimiter:
    """Zero-cost NOOP limiter for disabled state."""
    rpm = 0

    def acquire(self) -> float:
        """Returns 0.0 instantly — no limiting."""
        return 0.0


_NOOP = _NoOpLimiter()


class FixedWindowRateLimiter:
    """
    Fixed window rate limiter with full 60s wait after limit is reached.

    Once the RPM limit is reached, the next request must wait a full 60 seconds
    from when the window started, not just until the oldest request expires.

    Uses time.monotonic() for drift-free timing.
    Lock held only for window state operations.
    time.sleep() ALWAYS outside the lock.
    """

    def __init__(self, rpm: int):
        self._rpm = rpm
        self._window_start = 0.0  # When the current window started
        self._request_count = 0     # Requests made in current window
        self._lock = threading.Lock()

    @property
    def rpm(self) -> int:
        """Current RPM setting."""
        return self._rpm

    def acquire(self) -> float:
        """
        Block until a request slot is available.

        Returns:
            Seconds waited (0.0 if no wait needed).

        Fail-safe: Returns 0.0 on any exception (degrade to no limiting).
        """
        if self._rpm == 0:
            return 0.0

        wait_start = time.monotonic()

        while True:
            try:
                with self._lock:
                    now = time.monotonic()

                    # Check if we need to start a new window
                    if self._window_start == 0.0:
                        # First request - start the window
                        self._window_start = now
                        self._request_count = 1
                        return time.monotonic() - wait_start

                    # Check if current window has expired (60s from start)
                    window_age = now - self._window_start
                    if window_age >= 60.0:
                        # Start a new window
                        self._window_start = now
                        self._request_count = 1
                        return time.monotonic() - wait_start

                    # Check if we have room in the current window
                    if self._request_count < self._rpm:
                        # Allow the request
                        self._request_count += 1
                        return time.monotonic() - wait_start

                    # Limit reached - calculate wait time
                    # Wait until 60s from window start (full window)
                    sleep_for = 60.0 - window_age

            except Exception:
                # Fail-open: no limiting on errors (no state mutation)
                return 0.0

            # Sleep is ALWAYS outside the lock
            time.sleep(max(sleep_for, 0.01))


class ProviderRateLimiterRegistry:
    """
    Registry of per-provider rate limiters with thread-safe runtime updates.

    Lock separation:
    - FixedWindowRateLimiter._lock: protects window operations within individual limiters
    - ProviderRateLimiterRegistry._registry_lock: protects mutation + snapshot only

    Immutability rules:
    - Provider-specific limiters are immutable (created once, never replaced)
    - Only default limiter is replaced via set_default_rpm()
    """

    def __init__(self, default_rpm: int, providers: Dict[str, int]):
        self._default = _NOOP if default_rpm == 0 else FixedWindowRateLimiter(default_rpm)
        self._providers = {
            k.lower(): FixedWindowRateLimiter(_validate_rpm(v))
            for k, v in providers.items()
        }
        self._registry_lock = threading.Lock()

    def resolve(self, provider: str | None) -> FixedWindowRateLimiter:
        """
        Resolve the appropriate rate limiter for a provider.

        Uses zero-copy read pattern (providers are immutable).

        Args:
            provider: Provider name (case-insensitive, prefix-aware)

        Returns:
            Appropriate rate limiter (default if no match)
        """
        with self._registry_lock:
            default = self._default
            providers = self._providers  # no copy - providers are immutable

        # Do matching OUTSIDE lock to minimize contention
        if not provider:
            return default

        key = provider.lower()

        # Exact match
        if key in providers:
            return providers[key]

        # Prefix match (e.g., "nvidia-nim" → "nvidia")
        for name, limiter in providers.items():
            if key.startswith(name):
                return limiter

        return default

    def set_default_rpm(self, rpm: int) -> None:
        """
        Thread-safe runtime update of default RPM.

        Atomic replacement of default limiter instance.

        Args:
            rpm: New RPM setting (0 = disabled)
        """
        with self._registry_lock:
            self._default = _NOOP if rpm == 0 else FixedWindowRateLimiter(rpm)

    def reload_from_config(self, config: Dict) -> None:
        """
        Reload the entire registry from config.

        This is useful when the config is changed externally and you want
        to reload the rate limiter without restarting the agent.

        Args:
            config: Configuration dict with rate_limit section
        """
        rl_cfg = config.get("rate_limit", {})
        env_rpm = os.environ.get("HERMES_REQUESTS_PER_MINUTE")
        config_rpm = rl_cfg.get("requests_per_minute")

        # Use env var if set, otherwise use config, otherwise default to 0
        if env_rpm is not None:
            default_rpm = _validate_rpm(env_rpm)
        elif config_rpm is not None:
            default_rpm = _validate_rpm(config_rpm)
        else:
            default_rpm = 0

        providers = rl_cfg.get("providers", {})

        with self._registry_lock:
            self._default = _NOOP if default_rpm == 0 else FixedWindowRateLimiter(default_rpm)
            self._providers = {
                k.lower(): FixedWindowRateLimiter(_validate_rpm(v))
                for k, v in providers.items()
            }


def make_registry(config: Dict) -> ProviderRateLimiterRegistry:
    """
    Factory function to create a rate limiter registry from config.

    Reads from config dict and HERMES_REQUESTS_PER_MINUTE env var.

    Args:
        config: Configuration dict with rate_limit section

    Returns:
        Configured ProviderRateLimiterRegistry
    """
    rl_cfg = config.get("rate_limit", {})
    env_rpm = os.environ.get("HERMES_REQUESTS_PER_MINUTE")
    config_rpm = rl_cfg.get("requests_per_minute")

    # Use env var if set, otherwise use config, otherwise default to 0
    if env_rpm is not None:
        default_rpm = _validate_rpm(env_rpm)
    elif config_rpm is not None:
        default_rpm = _validate_rpm(config_rpm)
    else:
        default_rpm = 0

    providers = rl_cfg.get("providers", {})
    return ProviderRateLimiterRegistry(default_rpm, providers)


def make_rate_limiter(rpm: int) -> FixedWindowRateLimiter:
    """
    Simple factory to create a rate limiter.

    Args:
        rpm: Requests per minute (0 = disabled)

    Returns:
        FixedWindowRateLimiter instance
    """
    return FixedWindowRateLimiter(rpm)
