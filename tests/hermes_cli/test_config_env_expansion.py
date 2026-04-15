"""Tests for ${ENV_VAR} substitution in config.yaml values."""

import os
import re
import pytest
from hermes_cli.config import _expand_env_vars, _restore_env_refs, load_config, save_config
from unittest.mock import patch as mock_patch


class TestExpandEnvVars:
    def test_simple_substitution(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MY_KEY", "secret123")
            assert _expand_env_vars("${MY_KEY}") == "secret123"

    def test_missing_var_kept_verbatim(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("UNDEFINED_VAR_XYZ", raising=False)
            assert _expand_env_vars("${UNDEFINED_VAR_XYZ}") == "${UNDEFINED_VAR_XYZ}"

    def test_no_placeholder_unchanged(self):
        assert _expand_env_vars("plain-value") == "plain-value"

    def test_dict_recursive(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("TOKEN", "tok-abc")
            result = _expand_env_vars({"key": "${TOKEN}", "other": "literal"})
            assert result == {"key": "tok-abc", "other": "literal"}

    def test_nested_dict(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("API_KEY", "sk-xyz")
            result = _expand_env_vars({"model": {"api_key": "${API_KEY}"}})
            assert result["model"]["api_key"] == "sk-xyz"

    def test_list_items(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("VAL", "hello")
            result = _expand_env_vars(["${VAL}", "literal", 42])
            assert result == ["hello", "literal", 42]

    def test_non_string_values_untouched(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(3.14) == 3.14
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None

    def test_multiple_placeholders_in_one_string(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("HOST", "localhost")
            mp.setenv("PORT", "5432")
            assert _expand_env_vars("${HOST}:${PORT}") == "localhost:5432"

    def test_dict_keys_not_expanded(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("KEY", "value")
            result = _expand_env_vars({"${KEY}": "no-expand-key"})
            assert "${KEY}" in result


class TestLoadConfigExpansion:
    def test_load_config_expands_env_vars(self, tmp_path, monkeypatch):
        config_yaml = (
            "model:\n"
            "  api_key: ${GOOGLE_API_KEY}\n"
            "platforms:\n"
            "  telegram:\n"
            "    token: ${TELEGRAM_BOT_TOKEN}\n"
            "plain: no-substitution\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        monkeypatch.setenv("GOOGLE_API_KEY", "gsk-test-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567:ABC-token")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: config_file)

        config = load_config()

        assert config["model"]["api_key"] == "gsk-test-key"
        assert config["platforms"]["telegram"]["token"] == "1234567:ABC-token"
        assert config["plain"] == "no-substitution"

    def test_load_config_unresolved_kept_verbatim(self, tmp_path, monkeypatch):
        config_yaml = "model:\n  api_key: ${NOT_SET_XYZ_123}\n"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        monkeypatch.delenv("NOT_SET_XYZ_123", raising=False)
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: config_file)

        config = load_config()

        assert config["model"]["api_key"] == "${NOT_SET_XYZ_123}"


class TestLoadCliConfigExpansion:
    """Verify that load_cli_config() also expands ${VAR} references."""

    def test_cli_config_expands_auxiliary_api_key(self, tmp_path, monkeypatch):
        config_yaml = (
            "auxiliary:\n"
            "  vision:\n"
            "    api_key: ${TEST_VISION_KEY_XYZ}\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        monkeypatch.setenv("TEST_VISION_KEY_XYZ", "vis-key-123")
        # Patch the hermes home so load_cli_config finds our test config
        monkeypatch.setattr("cli._hermes_home", tmp_path)

        from cli import load_cli_config
        config = load_cli_config()

        assert config["auxiliary"]["vision"]["api_key"] == "vis-key-123"

    def test_cli_config_unresolved_kept_verbatim(self, tmp_path, monkeypatch):
        config_yaml = (
            "auxiliary:\n"
            "  vision:\n"
            "    api_key: ${UNSET_CLI_VAR_ABC}\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_yaml)

        monkeypatch.delenv("UNSET_CLI_VAR_ABC", raising=False)
        monkeypatch.setattr("cli._hermes_home", tmp_path)

        from cli import load_cli_config
        config = load_cli_config()

        assert config["auxiliary"]["vision"]["api_key"] == "${UNSET_CLI_VAR_ABC}"


class TestRestoreEnvRefs:
    """Tests for _restore_env_refs — inverse of _expand_env_vars."""

    def test_restores_expanded_value_to_var_ref(self, tmp_path, monkeypatch):
        """When raw file has ${VAR} and target has the expanded value, restore it."""
        monkeypatch.setenv("TEST_API_KEY", "sk-secret-123")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        # Write a raw config with ${VAR}
        (tmp_path / "config.yaml").write_text("model:\n  api_key: ${TEST_API_KEY}\n")

        # Simulate what load_config produces (expanded)
        config = {"model": {"api_key": "sk-secret-123"}}
        restored = _restore_env_refs(config)

        assert restored["model"]["api_key"] == "${TEST_API_KEY}"

    def test_no_restore_when_value_changed(self, tmp_path, monkeypatch):
        """If target has a different value than what ${VAR} resolved to, keep target."""
        monkeypatch.setenv("MY_KEY", "old-value")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text("model:\n  api_key: ${MY_KEY}\n")

        config = {"model": {"api_key": "new-value"}}
        restored = _restore_env_refs(config)

        assert restored["model"]["api_key"] == "new-value"

    def test_no_restore_when_raw_has_literal(self, tmp_path, monkeypatch):
        """If raw file has a literal value (not ${VAR}), don't touch it."""
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text("model:\n  api_key: literal-value\n")

        config = {"model": {"api_key": "literal-value"}}
        restored = _restore_env_refs(config)

        assert restored["model"]["api_key"] == "literal-value"

    def test_no_restore_when_config_file_missing(self, tmp_path, monkeypatch):
        """If no config file exists, return config unchanged."""
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "nonexistent.yaml")

        config = {"model": {"api_key": "sk-expanded"}}
        restored = _restore_env_refs(config)

        assert restored["model"]["api_key"] == "sk-expanded"

    def test_restores_multiple_vars(self, tmp_path, monkeypatch):
        """Multiple ${VAR} refs across different sections are all restored."""
        monkeypatch.setenv("VENICE_KEY", "vk-abc")
        monkeypatch.setenv("TAVILY_KEY", "tk-xyz")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text(
            "auxiliary:\n"
            "  vision:\n"
            "    api_key: ${VENICE_KEY}\n"
            "  web_extract:\n"
            "    api_key: ${TAVILY_KEY}\n"
            "environment:\n"
            "  TAVILY_API_KEY: ${TAVILY_KEY}\n"
        )

        config = {
            "auxiliary": {
                "vision": {"api_key": "vk-abc"},
                "web_extract": {"api_key": "tk-xyz"},
            },
            "environment": {"TAVILY_API_KEY": "tk-xyz"},
        }
        restored = _restore_env_refs(config)

        assert restored["auxiliary"]["vision"]["api_key"] == "${VENICE_KEY}"
        assert restored["auxiliary"]["web_extract"]["api_key"] == "${TAVILY_KEY}"
        assert restored["environment"]["TAVILY_API_KEY"] == "${TAVILY_KEY}"

    def test_restores_refs_in_list_of_dicts(self, tmp_path, monkeypatch):
        """${VAR} inside list items (e.g. providers list) is restored."""
        monkeypatch.setenv("PROVIDER_KEY", "pk-123")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text(
            "providers:\n"
            "- name: venice\n"
            "  api_key: ${PROVIDER_KEY}\n"
            "- name: local\n"
            "  api_key: local\n"
        )

        config = {
            "providers": [
                {"name": "venice", "api_key": "pk-123"},
                {"name": "local", "api_key": "local"},
            ]
        }
        restored = _restore_env_refs(config)

        assert restored["providers"][0]["api_key"] == "${PROVIDER_KEY}"
        assert restored["providers"][1]["api_key"] == "local"

    def test_does_not_mutate_original_config(self, tmp_path, monkeypatch):
        """_restore_env_refs returns a new dict, doesn't mutate the input."""
        monkeypatch.setenv("KEY", "val")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")
        (tmp_path / "config.yaml").write_text("x: ${KEY}\n")

        original = {"x": "val"}
        restored = _restore_env_refs(original)

        assert original["x"] == "val"          # unchanged
        assert restored["x"] == "${KEY}"       # restored


class TestSaveConfigPreservesEnvRefs:
    """Round-trip: load_config() → save_config() keeps ${VAR} refs in YAML."""

    def test_roundtrip_preserves_env_refs(self, tmp_path, monkeypatch):
        """After load_config + save_config, the YAML file still has ${VAR}."""
        monkeypatch.setenv("ROUNDTRIP_KEY", "rt-secret-456")
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text(
            "model:\n"
            "  api_key: ${ROUNDTRIP_KEY}\n"
            "  default: test-model\n"
        )

        # Load (expands ${VAR}) then save
        config = load_config()
        config["model"]["default"] = "updated-model"
        save_config(config)

        # Read raw file back
        raw = (tmp_path / "config.yaml").read_text()

        assert "${ROUNDTRIP_KEY}" in raw
        assert "rt-secret-456" not in raw
        assert "updated-model" in raw

    def test_new_literal_value_written_when_set(self, tmp_path, monkeypatch):
        """Setting a new api_key value writes the literal (no ${VAR} invented)."""
        monkeypatch.delenv("BRAND_NEW_KEY", raising=False)
        monkeypatch.setattr("hermes_cli.config.get_config_path", lambda: tmp_path / "config.yaml")

        (tmp_path / "config.yaml").write_text("model:\n  default: test\n")

        config = load_config()
        config["model"]["api_key"] = "brand-new-key"
        save_config(config)

        raw = (tmp_path / "config.yaml").read_text()
        assert "brand-new-key" in raw
