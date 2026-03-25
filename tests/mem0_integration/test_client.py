"""Tests for mem0_integration/client.py — Mem0 client configuration."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mem0_integration.client import (
    Mem0ClientConfig,
    get_mem0_client,
    reset_mem0_client,
    resolve_config_path,
    GLOBAL_CONFIG_PATH,
    HOST,
)


class TestMem0ClientConfigDefaults:
    def test_default_values(self):
        config = Mem0ClientConfig()
        assert config.host == "hermes"
        assert config.api_key is None
        assert config.enabled is False
        assert config.user_id is None
        assert config.agent_id == "hermes"
        assert config.memory_mode == "hybrid"
        assert config.recall_mode == "hybrid"
        assert config.session_strategy == "per-directory"
        assert config.rerank is True
        assert config.keyword_search is True
        assert config.custom_instructions is None


class TestFromEnv:
    def test_reads_api_key_from_env(self):
        with patch.dict(os.environ, {"MEM0_API_KEY": "m0-test-key"}):
            config = Mem0ClientConfig.from_env()
        assert config.api_key == "m0-test-key"
        assert config.enabled is True

    def test_defaults_without_env(self):
        env = {k: v for k, v in os.environ.items() if k != "MEM0_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            config = Mem0ClientConfig.from_env()
        assert config.api_key is None
        assert config.enabled is False


class TestFromGlobalConfig:
    def test_reads_host_block(self, tmp_path):
        config_file = tmp_path / "mem0.json"
        config_file.write_text(json.dumps({
            "apiKey": "m0-from-file",
            "hosts": {
                "hermes": {
                    "enabled": True,
                    "userId": "kartik",
                    "agentId": "hermes",
                    "memoryMode": "mem0",
                    "recallMode": "context",
                    "rerank": False,
                    "keywordSearch": False,
                    "customInstructions": "Extract only technical preferences",
                    "sessionStrategy": "global",
                }
            }
        }))
        config = Mem0ClientConfig.from_global_config(config_path=config_file)
        assert config.api_key == "m0-from-file"
        assert config.enabled is True
        assert config.user_id == "kartik"
        assert config.agent_id == "hermes"
        assert config.memory_mode == "mem0"
        assert config.recall_mode == "context"
        assert config.rerank is False
        assert config.keyword_search is False
        assert config.custom_instructions == "Extract only technical preferences"
        assert config.session_strategy == "global"

    def test_falls_back_to_env_when_no_file(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with patch.dict(os.environ, {"MEM0_API_KEY": "m0-env-key"}):
            config = Mem0ClientConfig.from_global_config(config_path=missing)
        assert config.api_key == "m0-env-key"
        assert config.enabled is True

    def test_api_key_host_overrides_root(self, tmp_path):
        config_file = tmp_path / "mem0.json"
        config_file.write_text(json.dumps({
            "apiKey": "root-key",
            "hosts": {"hermes": {"apiKey": "host-key", "enabled": True}}
        }))
        config = Mem0ClientConfig.from_global_config(config_path=config_file)
        assert config.api_key == "host-key"

    def test_recall_mode_normalized(self, tmp_path):
        config_file = tmp_path / "mem0.json"
        config_file.write_text(json.dumps({
            "apiKey": "key",
            "hosts": {"hermes": {"enabled": True, "recallMode": "invalid"}}
        }))
        config = Mem0ClientConfig.from_global_config(config_path=config_file)
        assert config.recall_mode == "hybrid"  # Falls back to default


class TestResolveConfigPath:
    def test_prefers_hermes_home(self, tmp_path):
        local = tmp_path / "mem0.json"
        local.touch()
        with patch("mem0_integration.client._get_hermes_home", return_value=tmp_path):
            result = resolve_config_path()
        assert result == local

    def test_falls_back_to_global(self, tmp_path):
        with patch("mem0_integration.client._get_hermes_home", return_value=tmp_path / "empty"):
            with patch("mem0_integration.client.GLOBAL_CONFIG_PATH", tmp_path / "global.json"):
                result = resolve_config_path()
        assert result == tmp_path / "global.json"


class TestGetMem0Client:
    def test_raises_without_api_key(self):
        config = Mem0ClientConfig(enabled=True)
        with pytest.raises(ValueError, match="API key"):
            get_mem0_client(config)

    def test_creates_client_with_key(self):
        config = Mem0ClientConfig(api_key="m0-test", enabled=True)
        with patch("mem0.MemoryClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = get_mem0_client(config)
            mock_cls.assert_called_once_with(api_key="m0-test")
        reset_mem0_client()

    def test_singleton_returns_same_instance(self):
        config = Mem0ClientConfig(api_key="m0-test", enabled=True)
        with patch("mem0.MemoryClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            c1 = get_mem0_client(config)
            c2 = get_mem0_client(config)
            assert c1 is c2
            assert mock_cls.call_count == 1
        reset_mem0_client()
