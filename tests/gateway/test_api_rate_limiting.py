"""Tests for API server rate limiting."""
import time

import pytest


class TestRateLimiter:
    """Rate limiter should restrict requests per API key."""

    def test_allows_requests_within_limit(self):
        """Requests within the rate limit should be allowed."""
        from gateway.platforms.api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=5, window_seconds=60)
        key = "test_key_1"

        for _ in range(5):
            assert limiter.is_allowed(key) is True

    def test_blocks_requests_exceeding_limit(self):
        """Requests exceeding the rate limit should be blocked."""
        from gateway.platforms.api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=3, window_seconds=60)
        key = "test_key_1"

        for _ in range(3):
            assert limiter.is_allowed(key) is True

        # 4th request should be blocked
        assert limiter.is_allowed(key) is False

    def test_different_keys_independent(self):
        """Different API keys should have independent rate limits."""
        from gateway.platforms.api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=2, window_seconds=60)

        # Exhaust key_1
        assert limiter.is_allowed("key_1") is True
        assert limiter.is_allowed("key_1") is True
        assert limiter.is_allowed("key_1") is False

        # key_2 should still be allowed
        assert limiter.is_allowed("key_2") is True

    def test_window_expiry_resets_limit(self):
        """After the window expires, the rate limit should reset."""
        from gateway.platforms.api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=2, window_seconds=1)
        key = "test_key_1"

        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is False

        # Wait for window to expire
        time.sleep(1.1)

        assert limiter.is_allowed(key) is True

    def test_no_rate_limit_when_disabled(self):
        """When max_requests is 0, no rate limiting should be applied."""
        from gateway.platforms.api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=0, window_seconds=60)
        key = "test_key_1"

        # Should allow unlimited requests
        for _ in range(100):
            assert limiter.is_allowed(key) is True
