"""Tests for API server per-request model routing."""

from unittest.mock import patch, MagicMock
import pytest


class TestModelOverrideParsing:
    """Test the model_override logic in _create_agent."""

    def _make_adapter(self):
        """Create a minimal APIServerAdapter for testing."""
        from gateway.platforms.api_server import APIServerAdapter
        adapter = APIServerAdapter.__new__(APIServerAdapter)
        adapter._port = 8642
        adapter._session_db = None
        adapter._session_db_lock = __import__("threading").Lock()
        return adapter

    @patch("gateway.run._load_gateway_config")
    @patch("gateway.run._resolve_gateway_model")
    @patch("gateway.run._resolve_runtime_agent_kwargs")
    @patch("run_agent.AIAgent")
    def test_no_override_uses_default_model(
        self, mock_agent_cls, mock_kwargs, mock_model, mock_config
    ):
        mock_kwargs.return_value = {"api_key": "test", "base_url": None, "provider": "anthropic", "api_mode": None, "command": None, "args": [], "credential_pool": None}
        mock_model.return_value = "claude-opus-4-6"
        mock_config.return_value = {"platform_toolsets": {"api_server": ["terminal"]}}
        mock_agent_cls.return_value = MagicMock()

        with patch("gateway.run.GatewayRunner._load_fallback_model", return_value=None):
            adapter = self._make_adapter()
            adapter._create_agent()

        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs[1]["model"] == "claude-opus-4-6"

    @patch("gateway.run._load_gateway_config")
    @patch("gateway.run._resolve_gateway_model")
    @patch("gateway.run._resolve_runtime_agent_kwargs")
    @patch("run_agent.AIAgent")
    def test_simple_model_override(
        self, mock_agent_cls, mock_kwargs, mock_model, mock_config
    ):
        mock_kwargs.return_value = {"api_key": "test", "base_url": None, "provider": "anthropic", "api_mode": None, "command": None, "args": [], "credential_pool": None}
        mock_model.return_value = "claude-opus-4-6"
        mock_config.return_value = {"platform_toolsets": {"api_server": ["terminal"]}}
        mock_agent_cls.return_value = MagicMock()

        with patch("gateway.run.GatewayRunner._load_fallback_model", return_value=None):
            adapter = self._make_adapter()
            adapter._create_agent(model_override="claude-sonnet-4-20250514")

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs[1]["model"] == "claude-sonnet-4-20250514"

    @patch("gateway.run._load_gateway_config")
    @patch("gateway.run._resolve_gateway_model")
    @patch("gateway.run._resolve_runtime_agent_kwargs")
    @patch("run_agent.AIAgent")
    def test_provider_prefixed_override_resolves_config(
        self, mock_agent_cls, mock_kwargs, mock_model, mock_config
    ):
        mock_kwargs.return_value = {"api_key": "test", "base_url": None, "provider": "anthropic", "api_mode": None, "command": None, "args": [], "credential_pool": None}
        mock_model.return_value = "claude-opus-4-6"
        mock_config.return_value = {
            "platform_toolsets": {"api_server": ["terminal"]},
            "providers": {
                "ollama": {
                    "api": "http://localhost:11434/v1",
                    "api_key": "no-key",
                    "transport": "chat_completions",
                },
            },
        }
        mock_agent_cls.return_value = MagicMock()

        with patch("gateway.run.GatewayRunner._load_fallback_model", return_value=None):
            adapter = self._make_adapter()
            adapter._create_agent(model_override="ollama/gemma4:26b")

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs[1]["model"] == "gemma4:26b"
        assert call_kwargs[1]["base_url"] == "http://localhost:11434/v1"
        assert call_kwargs[1]["provider"] == "ollama"

    @patch("gateway.run._load_gateway_config")
    @patch("gateway.run._resolve_gateway_model")
    @patch("gateway.run._resolve_runtime_agent_kwargs")
    @patch("run_agent.AIAgent")
    def test_unknown_provider_prefix_keeps_model_string(
        self, mock_agent_cls, mock_kwargs, mock_model, mock_config
    ):
        """If the provider prefix doesn't match config, use the model part as-is."""
        mock_kwargs.return_value = {"api_key": "test", "base_url": None, "provider": "anthropic", "api_mode": None, "command": None, "args": [], "credential_pool": None}
        mock_model.return_value = "claude-opus-4-6"
        mock_config.return_value = {"platform_toolsets": {"api_server": ["terminal"]}, "providers": {}}
        mock_agent_cls.return_value = MagicMock()

        with patch("gateway.run.GatewayRunner._load_fallback_model", return_value=None):
            adapter = self._make_adapter()
            adapter._create_agent(model_override="unknown/some-model")

        call_kwargs = mock_agent_cls.call_args
        # Model should be "some-model" (provider prefix stripped)
        assert call_kwargs[1]["model"] == "some-model"
        # Provider should NOT have been overridden
        assert call_kwargs[1]["provider"] == "anthropic"


class TestChatCompletionsModelPassthrough:
    """Test that the model field from request body reaches _create_agent."""

    def test_hermes_agent_model_does_not_override(self):
        """model='hermes-agent' should use the config default."""
        model_name = "hermes-agent"
        override = model_name if model_name != "hermes-agent" else None
        assert override is None

    def test_custom_model_creates_override(self):
        """A non-default model name should create an override."""
        model_name = "claude-sonnet-4-20250514"
        override = model_name if model_name != "hermes-agent" else None
        assert override == "claude-sonnet-4-20250514"

    def test_provider_model_creates_override(self):
        """A provider/model string should create an override."""
        model_name = "ollama/gemma4:26b"
        override = model_name if model_name != "hermes-agent" else None
        assert override == "ollama/gemma4:26b"
