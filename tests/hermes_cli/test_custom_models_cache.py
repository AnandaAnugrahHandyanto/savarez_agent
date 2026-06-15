"""Tests for the custom provider model discovery cache (fix #44560).

Verifies that _cached_fetch_api_models() caches results with TTL and
uses a shorter timeout to avoid blocking the WebSocket handler.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest


class TestCacheKey:
    """_cache_key() normalises URLs and fingerprints API keys."""

    @staticmethod
    def test_trailing_slash_normalised():
        from hermes_cli.model_switch import _cache_key
        assert _cache_key("http://x/v1") == _cache_key("http://x/v1/")

    @staticmethod
    def test_case_insensitive():
        from hermes_cli.model_switch import _cache_key
        assert _cache_key("HTTP://X/V1") == _cache_key("http://x/v1")

    @staticmethod
    def test_different_keys_produce_different_cache():
        from hermes_cli.model_switch import _cache_key
        k1 = _cache_key("http://x/v1", "key-a")
        k2 = _cache_key("http://x/v1", "key-b")
        assert k1 != k2

    @staticmethod
    def test_empty_key_same_as_no_key():
        from hermes_cli.model_switch import _cache_key
        assert _cache_key("http://x/v1", "") == _cache_key("http://x/v1")


class TestCachedFetchApiModels:
    """_cached_fetch_api_models() wraps fetch_api_models with TTL caching."""

    def setup_method(self):
        from hermes_cli.model_switch import _custom_models_cache
        _custom_models_cache.clear()

    def test_cache_hit_avoids_network_call(self):
        """Second call within TTL must return cached data without calling
        fetch_api_models."""
        from hermes_cli.model_switch import _cached_fetch_api_models, _custom_models_cache

        with patch(
            "hermes_cli.models.fetch_api_models",
            return_value=["model-a", "model-b"],
        ) as mock_fetch:
            r1 = _cached_fetch_api_models("k", "http://p/v1")
            r2 = _cached_fetch_api_models("k", "http://p/v1")

        assert r1 == ["model-a", "model-b"]
        assert r2 == ["model-a", "model-b"]
        mock_fetch.assert_called_once()  # only one network call

    def test_cache_miss_after_ttl_expiry(self):
        """After TTL expires, a fresh fetch must occur."""
        from hermes_cli.model_switch import (
            _cached_fetch_api_models,
            _custom_models_cache,
            _CUSTOM_MODELS_TTL,
            _cache_key,
        )

        # Prime the cache with a stale entry
        key = _cache_key("http://p/v1", "k")
        _custom_models_cache[key] = (time.time() - _CUSTOM_MODELS_TTL - 1, ["old"])

        with patch(
            "hermes_cli.models.fetch_api_models",
            return_value=["new"],
        ) as mock_fetch:
            result = _cached_fetch_api_models("k", "http://p/v1")

        assert result == ["new"]
        mock_fetch.assert_called_once()

    def test_stale_fallback_on_network_error(self):
        """When the live fetch fails, stale cached data is returned."""
        from hermes_cli.model_switch import (
            _cached_fetch_api_models,
            _custom_models_cache,
            _CUSTOM_MODELS_TTL,
            _cache_key,
        )

        key = _cache_key("http://p/v1", "k")
        _custom_models_cache[key] = (time.time() - _CUSTOM_MODELS_TTL - 1, ["stale"])

        with patch(
            "hermes_cli.models.fetch_api_models",
            side_effect=TimeoutError("connection timed out"),
        ):
            result = _cached_fetch_api_models("k", "http://p/v1")

        assert result == ["stale"]

    def test_returns_none_when_no_cache_and_fetch_fails(self):
        """Without any cached data, a failed fetch returns None."""
        from hermes_cli.model_switch import _cached_fetch_api_models

        with patch(
            "hermes_cli.models.fetch_api_models",
            return_value=None,
        ):
            result = _cached_fetch_api_models("k", "http://p/v1")

        assert result is None

    def test_default_timeout_is_3_seconds(self):
        """The cached wrapper must use a 3s timeout (not the 5s default)."""
        from hermes_cli.model_switch import _cached_fetch_api_models

        with patch(
            "hermes_cli.models.fetch_api_models",
            return_value=["m"],
        ) as mock_fetch:
            _cached_fetch_api_models("k", "http://p/v1")

        _, kwargs = mock_fetch.call_args
        assert kwargs["timeout"] == 3.0

    def test_different_endpoints_cached_separately(self):
        """Two different endpoints must have independent cache entries."""
        from hermes_cli.model_switch import _cached_fetch_api_models, _custom_models_cache

        with patch(
            "hermes_cli.models.fetch_api_models",
            side_effect=lambda k, u, **kw: [u.split("//")[1]],
        ):
            r1 = _cached_fetch_api_models("k", "http://a/v1")
            r2 = _cached_fetch_api_models("k", "http://b/v1")

        assert r1 != r2
        assert len(_custom_models_cache) == 2
