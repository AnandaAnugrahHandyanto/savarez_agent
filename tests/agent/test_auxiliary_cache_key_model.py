"""Regression test: auxiliary client cache key includes model.

When multiple auxiliary tasks (vision, compression, title_generation) share
the same provider but specify different models, each task should receive its
own model — not whichever model warmed the cache first.

Refs #16387, #14249.
"""

from __future__ import annotations

from agent.auxiliary_client import _client_cache_key


class TestClientCacheKeyIncludesModel:
    """_client_cache_key() must include model so different models get
    distinct cache entries even when provider/base_url/api_key match."""

    def test_different_models_produce_different_keys(self) -> None:
        key_a = _client_cache_key(
            "myrelay",
            model="google/gemini-3.1-flash-image-preview",
            async_mode=False,
            base_url="https://example.test/v1",
            api_key="sk-test",
            api_mode="chat_completions",
        )
        key_b = _client_cache_key(
            "myrelay",
            model="google/gemini-3-flash-preview",
            async_mode=False,
            base_url="https://example.test/v1",
            api_key="sk-test",
            api_mode="chat_completions",
        )
        assert key_a != key_b, (
            "Different models must produce different cache keys"
        )

    def test_same_model_produces_same_key(self) -> None:
        kwargs = dict(
            provider="myrelay",
            model="google/gemini-3.1-flash-image-preview",
            async_mode=False,
            base_url="https://example.test/v1",
            api_key="sk-test",
            api_mode="chat_completions",
        )
        assert _client_cache_key(**kwargs) == _client_cache_key(**kwargs)

    def test_none_model_equals_empty_string(self) -> None:
        key_none = _client_cache_key(
            "p", model=None, async_mode=False,
        )
        key_empty = _client_cache_key(
            "p", model="", async_mode=False,
        )
        assert key_none == key_empty

    def test_model_independent_of_provider(self) -> None:
        """Same model on different providers still yields different keys."""
        key_a = _client_cache_key(
            "provider-a", model="mymodel", async_mode=False,
        )
        key_b = _client_cache_key(
            "provider-b", model="mymodel", async_mode=False,
        )
        assert key_a != key_b
