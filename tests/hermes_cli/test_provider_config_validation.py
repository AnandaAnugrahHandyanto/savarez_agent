"""Tests for providers config entry validation and normalization.

Covers Issue #9332: camelCase keys silently ignored, non-URL strings
accepted as base_url, and unknown keys go unreported.
"""

import logging
from unittest.mock import patch

import pytest

from hermes_cli.config import _normalize_custom_provider_entry


class TestNormalizeCustomProviderEntry:
    """Tests for _normalize_custom_provider_entry validation."""

    def test_valid_entry_snake_case(self):
        """Standard snake_case entry should normalize correctly."""
        entry = {
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="myhost")
        assert result is not None
        assert result["name"] == "myhost"
        assert result["base_url"] == "https://api.example.com/v1"
        assert result["api_key"] == "sk-test-key"

    def test_camel_case_api_key_mapped(self):
        """camelCase apiKey should be auto-mapped to api_key."""
        entry = {
            "base_url": "https://api.example.com/v1",
            "apiKey": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="myhost")
        assert result is not None
        assert result["api_key"] == "sk-test-key"

    def test_camel_case_base_url_mapped(self):
        """camelCase baseUrl should be auto-mapped to base_url."""
        entry = {
            "baseUrl": "https://api.example.com/v1",
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="myhost")
        assert result is not None
        assert result["base_url"] == "https://api.example.com/v1"

    def test_non_url_api_field_rejected(self):
        """Non-URL string in 'api' field should be skipped with a warning."""
        entry = {
            "api": "openai-reverse-proxy",
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="nvidia")
        # Should return None because no valid URL was found
        assert result is None

    def test_valid_url_in_api_field_accepted(self):
        """Valid URL in 'api' field should still be accepted."""
        entry = {
            "api": "https://integrate.api.nvidia.com/v1",
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="nvidia")
        assert result is not None
        assert result["base_url"] == "https://integrate.api.nvidia.com/v1"

    def test_base_url_preferred_over_api(self):
        """base_url should be checked before api field."""
        entry = {
            "base_url": "https://correct.example.com/v1",
            "api": "https://wrong.example.com/v1",
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="test")
        assert result is not None
        assert result["base_url"] == "https://correct.example.com/v1"

    def test_unknown_keys_logged(self, caplog):
        """Unknown config keys should produce a warning."""
        entry = {
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-test-key",
            "unknownField": "value",
            "anotherBad": 42,
        }
        with caplog.at_level(logging.WARNING):
            result = _normalize_custom_provider_entry(entry, provider_key="test")
        assert result is not None
        assert any("unknown config keys" in r.message.lower() for r in caplog.records)

    def test_camel_case_warning_logged(self, caplog):
        """camelCase alias mapping should produce a warning."""
        entry = {
            "baseUrl": "https://api.example.com/v1",
            "apiKey": "sk-test-key",
        }
        with caplog.at_level(logging.WARNING):
            result = _normalize_custom_provider_entry(entry, provider_key="test")
        assert result is not None
        camel_warnings = [r for r in caplog.records if "camelcase" in r.message.lower() or "auto-mapped" in r.message.lower()]
        assert len(camel_warnings) >= 1

    def test_snake_case_takes_precedence_over_camel(self):
        """If both snake_case and camelCase exist, snake_case wins."""
        entry = {
            "api_key": "snake-key",
            "apiKey": "camel-key",
            "base_url": "https://api.example.com/v1",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="test")
        assert result is not None
        assert result["api_key"] == "snake-key"

    def test_non_dict_returns_none(self):
        """Non-dict entry should return None."""
        assert _normalize_custom_provider_entry("not-a-dict") is None
        assert _normalize_custom_provider_entry(42) is None
        assert _normalize_custom_provider_entry(None) is None

    def test_no_url_returns_none(self):
        """Entry with no valid URL in any field should return None."""
        entry = {
            "api_key": "sk-test-key",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="test")
        assert result is None

    def test_no_name_returns_none(self):
        """Entry with no name and no provider_key should return None."""
        entry = {
            "base_url": "https://api.example.com/v1",
        }
        result = _normalize_custom_provider_entry(entry, provider_key="")
        assert result is None

    def test_models_list_converted_to_dict(self):
        """List-format models should be preserved as an empty-value dict so
        /model picks them up instead of showing the provider with (0) models."""
        entry = {
            "name": "tencent-coding-plan",
            "base_url": "https://api.lkeap.cloud.tencent.com/coding/v3",
            "models": ["glm-5", "kimi-k2.5", "minimax-m2.5"],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {"glm-5": {}, "kimi-k2.5": {}, "minimax-m2.5": {}}

    def test_models_dict_preserved(self):
        """Dict-format models should pass through unchanged."""
        entry = {
            "name": "acme",
            "base_url": "https://api.example.com/v1",
            "models": {"gpt-foo": {"context_length": 32000}},
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {"gpt-foo": {"context_length": 32000}}

    def test_models_list_filters_empty_and_non_string(self):
        """List entries that are empty strings or non-strings are skipped."""
        entry = {
            "name": "acme",
            "base_url": "https://api.example.com/v1",
            "models": ["valid", "", None, 42, "  ", "also-valid"],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {"valid": {}, "also-valid": {}}

    def test_models_empty_list_omitted(self):
        """Empty list (falsy) should not produce a models key."""
        entry = {
            "name": "acme",
            "base_url": "https://api.example.com/v1",
            "models": [],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert "models" not in result

    def test_id_field_recognized_as_provider_name(self):
        """Entry using 'id' instead of 'name' should be accepted."""
        entry = {
            "id": "manifest",
            "base_url": "http://127.0.0.1:38238/v1",
            "api_key": "sk-test",
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["name"] == "manifest"
        assert result["base_url"] == "http://127.0.0.1:38238/v1"

    def test_id_field_does_not_warn_as_unknown_key(self, caplog):
        """'id' should not trigger the unknown-key warning."""
        entry = {
            "id": "my-provider",
            "base_url": "https://api.example.com/v1",
        }
        with caplog.at_level(logging.WARNING):
            result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert not any("unknown config keys" in r.message.lower() for r in caplog.records)

    def test_name_takes_precedence_over_id(self):
        """When both 'name' and 'id' are present, 'name' wins."""
        entry = {
            "name": "winner",
            "id": "loser",
            "base_url": "https://api.example.com/v1",
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["name"] == "winner"

    def test_models_list_of_dicts_parsed(self):
        """Models written as list-of-dicts with id+context_length should
        be normalized to dict shape with metadata preserved."""
        entry = {
            "name": "manifest",
            "base_url": "http://127.0.0.1:38238/v1",
            "models": [
                {"id": "auto", "context_length": 200000},
                {"id": "llama3", "context_length": 128000},
            ],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {
            "auto": {"context_length": 200000},
            "llama3": {"context_length": 128000},
        }

    def test_models_list_of_dicts_with_name_key(self):
        """Models dict entries using 'name' instead of 'id' should work."""
        entry = {
            "name": "test",
            "base_url": "https://api.example.com/v1",
            "models": [
                {"name": "gpt-4o", "context_length": 128000},
            ],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {"gpt-4o": {"context_length": 128000}}

    def test_models_mixed_list_of_strings_and_dicts(self):
        """Mixed list of plain strings and dict entries should all be parsed."""
        entry = {
            "name": "test",
            "base_url": "https://api.example.com/v1",
            "models": [
                "plain-model",
                {"id": "dict-model", "context_length": 64000},
            ],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {
            "plain-model": {},
            "dict-model": {"context_length": 64000},
        }

    def test_models_dict_entry_without_id_or_name_skipped(self):
        """Dict entries with no id/name/model key should be skipped."""
        entry = {
            "name": "test",
            "base_url": "https://api.example.com/v1",
            "models": [
                {"context_length": 64000},  # no id
                {"id": "valid", "context_length": 32000},
            ],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        assert result["models"] == {"valid": {"context_length": 32000}}

    def test_models_dict_entry_strips_id_and_name_from_metadata(self):
        """id/name/model keys should be stripped from the metadata dict."""
        entry = {
            "name": "test",
            "base_url": "https://api.example.com/v1",
            "models": [
                {"id": "m1", "name": "Model One", "model": "m1", "context_length": 100000},
            ],
        }
        result = _normalize_custom_provider_entry(entry)
        assert result is not None
        # Only context_length should remain; id/name/model stripped
        assert result["models"] == {"m1": {"context_length": 100000}}

