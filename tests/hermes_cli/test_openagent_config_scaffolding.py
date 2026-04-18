"""Focused tests for OpenAgent-style config bucket scaffolding."""

import os
from unittest.mock import patch

import yaml

from hermes_cli.config import (
    _normalize_model_capabilities_config,
    _normalize_openagent_config_buckets,
    _normalize_openagent_named_bucket,
    _normalize_runtime_fallback_config,
    load_config,
    save_config,
    validate_config_structure,
)


class TestOpenAgentBucketHelpers:
    def test_named_bucket_normalizes_string_shorthand(self):
        normalized = _normalize_openagent_named_bucket({
            "oracle": "openai/gpt-5.4",
            "explore": {"model": "anthropic/claude-sonnet-4", "temperature": 0.2},
            "ignored": 7,
            "": {"model": "should-not-survive"},
        })

        assert normalized == {
            "oracle": {"model": "openai/gpt-5.4"},
            "explore": {"model": "anthropic/claude-sonnet-4", "temperature": 0.2},
        }

    def test_runtime_fallback_boolean_normalizes_to_enabled_dict(self):
        assert _normalize_runtime_fallback_config(True) == {"enabled": True}
        assert _normalize_runtime_fallback_config(False) == {"enabled": False}

    def test_model_capabilities_invalid_shape_resets_to_empty_mapping(self):
        assert _normalize_model_capabilities_config(["not", "a", "dict"]) == {}

    def test_openagent_bucket_normalizer_adds_default_scaffolds(self):
        normalized = _normalize_openagent_config_buckets({})

        assert normalized["agents"] == {}
        assert normalized["categories"] == {}
        assert normalized["runtime_fallback"] == {"enabled": False}
        assert normalized["model_capabilities"] == {}


class TestLoadConfigOpenAgentBuckets:
    def test_defaults_include_openagent_scaffolding(self, tmp_path):
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            config = load_config()

        assert config["agents"] == {}
        assert config["categories"] == {}
        assert config["runtime_fallback"] == {"enabled": False}
        assert config["model_capabilities"] == {}

    def test_load_config_normalizes_openagent_bucket_shapes(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join([
                "agents:",
                "  oracle: openai/gpt-5.4",
                "  explore:",
                "    model: anthropic/claude-sonnet-4",
                "    temperature: 0.2",
                "categories:",
                "  research: anthropic/claude-haiku-4-5",
                "runtime_fallback: true",
                "model_capabilities:",
                "  enabled: true",
                "  source_url: https://example.invalid/models.json",
                "",
            ]),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            config = load_config()

        assert config["agents"]["oracle"] == {"model": "openai/gpt-5.4"}
        assert config["agents"]["explore"] == {
            "model": "anthropic/claude-sonnet-4",
            "temperature": 0.2,
        }
        assert config["categories"]["research"] == {"model": "anthropic/claude-haiku-4-5"}
        assert config["runtime_fallback"] == {"enabled": True}
        assert config["model_capabilities"] == {
            "enabled": True,
            "source_url": "https://example.invalid/models.json",
        }

    def test_invalid_openagent_bucket_types_fall_back_without_breaking_existing_config(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join([
                "model: openai/gpt-5.4",
                "max_turns: 42",
                "agents:",
                "  - oracle",
                "categories: true",
                "runtime_fallback:",
                "  - 429",
                "model_capabilities: disabled",
                "",
            ]),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            config = load_config()

        assert config["model"] == "openai/gpt-5.4"
        assert config["agent"]["max_turns"] == 42
        assert config["agents"] == {}
        assert config["categories"] == {}
        assert config["runtime_fallback"] == {"enabled": False}
        assert config["model_capabilities"] == {}


class TestSaveConfigOpenAgentBuckets:
    def test_save_config_persists_normalized_openagent_buckets(self, tmp_path):
        with patch.dict(os.environ, {"HERMES_HOME": str(tmp_path)}):
            save_config({
                "agents": {"oracle": "openai/gpt-5.4"},
                "runtime_fallback": True,
                "model_capabilities": {"enabled": True},
            })

        saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
        assert saved["agents"] == {"oracle": {"model": "openai/gpt-5.4"}}
        assert saved["runtime_fallback"] == {"enabled": True}
        assert saved["model_capabilities"] == {"enabled": True}
        assert "categories" not in saved


class TestValidateConfigStructureOpenAgentBuckets:
    def test_warns_for_invalid_openagent_bucket_shapes(self):
        issues = validate_config_structure({
            "agents": ["oracle"],
            "categories": True,
            "runtime_fallback": [429],
            "model_capabilities": "enabled",
        })
        messages = [issue.message for issue in issues]

        assert any("agents should be a mapping" in message for message in messages)
        assert any("categories should be a mapping" in message for message in messages)
        assert any("runtime_fallback should be either a boolean or a config dict" in message for message in messages)
        assert any("model_capabilities should be a config dict" in message for message in messages)

    def test_accepts_runtime_fallback_boolean_without_warnings(self):
        issues = validate_config_structure({
            "agents": {"oracle": {"model": "openai/gpt-5.4"}},
            "categories": {"reasoning": {"model": "anthropic/claude-sonnet-4"}},
            "runtime_fallback": True,
            "model_capabilities": {"enabled": True},
        })

        assert not any("runtime_fallback" in issue.message for issue in issues)
