from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "/tmp/.hermes_test")
    for k in list(os.environ):
        if k.startswith("HINDSIGHT_"):
            monkeypatch.delenv(k, raising=False)
    return monkeypatch


@pytest.fixture(autouse=True)
def _mock_hermes_constants():
    if "hermes_constants" in sys.modules:
        _orig = sys.modules["hermes_constants"]
    else:
        _orig = None
    fake = MagicMock()
    fake.get_hermes_home.return_value = MagicMock(
        __truediv__=MagicMock(
            return_value=MagicMock(exists=MagicMock(return_value=False))
        )
    )
    sys.modules["hermes_constants"] = fake
    yield
    if _orig is not None:
        sys.modules["hermes_constants"] = _orig
    else:
        sys.modules.pop("hermes_constants", None)
    if "plugins.memory.hindsight" in sys.modules:
        del sys.modules["plugins.memory.hindsight"]


@pytest.fixture
def hindsight(env):
    from plugins.memory.hindsight import (
        HindsightMemoryProvider,
        _DEFAULT_API_URL,
        _load_config,
    )

    return HindsightMemoryProvider, _DEFAULT_API_URL, _load_config


class TestMakeClient:
    def test_make_client_passes_base_url(self, hindsight):
        Provider, _, _ = hindsight
        provider = Provider()
        provider._mode = "cloud"
        provider._api_key = "test-key"
        provider._config = {"api_url": "https://custom.example.com"}

        mock_hindsight_cls = MagicMock()
        with patch.dict(
            "sys.modules", {"hindsight_client": MagicMock(Hindsight=mock_hindsight_cls)}
        ):
            provider._make_client()

        mock_hindsight_cls.assert_called_once_with(
            base_url="https://custom.example.com", api_key="test-key", timeout=120.0
        )

    def test_make_client_uses_default_url_when_no_config(self, hindsight):
        Provider, DEFAULT_URL, _ = hindsight
        provider = Provider()
        provider._mode = "cloud"
        provider._api_key = "test-key"
        provider._config = {}

        mock_hindsight_cls = MagicMock()
        with patch.dict(
            "sys.modules", {"hindsight_client": MagicMock(Hindsight=mock_hindsight_cls)}
        ):
            provider._make_client()

        mock_hindsight_cls.assert_called_once_with(
            base_url=DEFAULT_URL, api_key="test-key", timeout=120.0
        )

    def test_make_client_timeout_is_120(self, hindsight):
        Provider, _, _ = hindsight
        provider = Provider()
        provider._mode = "cloud"
        provider._api_key = "key"
        provider._config = {}

        mock_hindsight_cls = MagicMock()
        with patch.dict(
            "sys.modules", {"hindsight_client": MagicMock(Hindsight=mock_hindsight_cls)}
        ):
            provider._make_client()

        _, kwargs = mock_hindsight_cls.call_args
        assert kwargs["timeout"] == 120.0

    def test_make_client_cloud_mode(self, hindsight):
        Provider, _, _ = hindsight
        provider = Provider()
        provider._mode = "cloud"
        provider._api_key = "key"
        provider._config = {}

        mock_module = MagicMock()
        with patch.dict("sys.modules", {"hindsight_client": mock_module}):
            provider._make_client()

        mock_module.Hindsight.assert_called_once()


class TestLoadConfig:
    def test_load_config_includes_api_url_from_env(self, hindsight):
        _, _, load_config = hindsight
        os.environ["HINDSIGHT_API_URL"] = "https://env.example.com"
        cfg = load_config()
        assert cfg["api_url"] == "https://env.example.com"

    def test_load_config_env_fallback_has_api_url(self, hindsight):
        _, _, load_config = hindsight
        cfg = load_config()
        assert "api_url" in cfg
        assert cfg["api_url"] == ""


class TestConfigSchema:
    def test_config_schema_includes_api_url(self, hindsight):
        Provider, _, _ = hindsight
        provider = Provider()
        schema = provider.get_config_schema()
        keys = [entry["key"] for entry in schema]
        assert "api_url" in keys

        api_url_entry = next(e for e in schema if e["key"] == "api_url")
        assert api_url_entry["env_var"] == "HINDSIGHT_API_URL"
        assert api_url_entry["default"] == "https://api.hindsight.vectorize.io"


class TestIsAvailable:
    def test_is_available_with_api_key(self, hindsight):
        Provider, _, _ = hindsight
        os.environ["HINDSIGHT_API_KEY"] = "sk-test"
        provider = Provider()
        assert provider.is_available() is True
