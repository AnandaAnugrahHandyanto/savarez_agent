"""Regression tests for custom_providers per-model max_tokens resolution.

Covers #28046 / #28782 — a per-model ``custom_providers[].models.<id>.max_tokens``
output cap must reach ``agent.max_tokens`` at startup AND be re-resolved on
mid-session /model switch and fallback, the same way context_length is.
"""

import pytest

from hermes_cli.config import get_custom_provider_max_tokens

URL = "https://example.invalid/v1"


def _cfg(max_tokens, *, base_url=URL, model="m"):
    return [{"base_url": base_url, "models": {model: {"max_tokens": max_tokens}}}]


class TestGetCustomProviderMaxTokens:
    def test_returns_override_for_matching_entry(self):
        assert get_custom_provider_max_tokens("m", URL, _cfg(131_072)) == 131_072

    @pytest.mark.parametrize("entry_url, query_url", [
        (URL + "/", URL),
        (URL, URL + "/"),
    ])
    def test_trailing_slash_insensitive(self, entry_url, query_url):
        assert get_custom_provider_max_tokens("m", query_url, _cfg(32_000, base_url=entry_url)) == 32_000

    def test_returns_none_when_url_does_not_match(self):
        assert get_custom_provider_max_tokens("m", URL, _cfg(32_000, base_url="https://other.invalid/v1")) is None

    def test_returns_none_when_model_missing(self):
        assert get_custom_provider_max_tokens("m", URL, _cfg(32_000, model="other")) is None

    def test_numeric_string_is_coerced(self):
        assert get_custom_provider_max_tokens("m", URL, _cfg("16000")) == 16_000

    @pytest.mark.parametrize("bad", [0, -1, "0", "-5"])
    def test_zero_and_negative_skipped(self, bad):
        assert get_custom_provider_max_tokens("m", URL, _cfg(bad)) is None

    def test_non_numeric_skipped(self):
        assert get_custom_provider_max_tokens("m", URL, _cfg("32K")) is None

    def test_bool_rejected(self):
        # bool is an int subclass — must be rejected, not coerced to 1.
        assert get_custom_provider_max_tokens("m", URL, _cfg(True)) is None

    @pytest.mark.parametrize("model, url, providers", [
        ("", URL, []),
        ("m", "", []),
        ("m", URL, None),
    ])
    def test_empty_inputs_guarded(self, model, url, providers):
        assert get_custom_provider_max_tokens(model, url, providers) is None
