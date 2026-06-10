"""Tests for ``hermes_cli.provider_diagnose``.

All external HTTP calls and boto3 usage are mocked — no real network
or AWS credentials required.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestDiagnoseProviderNotFound:
    """When the provider is unknown and has no config."""

    def test_unknown_provider_reports_failure(self):
        from hermes_cli.provider_diagnose import diagnose_provider

        with patch("hermes_cli.providers.normalize_provider", return_value=None):
            result = diagnose_provider("nonexistent-provider-xyz")
        assert result == 1


class TestDiagnoseOpenAIProvider:
    """Happy path and failure modes for a canonical API-key provider."""

    def test_missing_key_env_var(self, monkeypatch):
        from hermes_cli.provider_diagnose import diagnose_provider

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("hermes_cli.providers.normalize_provider", return_value="openai"):
            result = diagnose_provider("openai")
        assert result == 1

    def test_full_happy_path(self, monkeypatch):
        from hermes_cli import provider_diagnose as _pd

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-1234567890")

        fake_canonical = MagicMock()
        fake_canonical.slug = "openai"
        fake_canonical.inference_base_url = "https://api.openai.com/v1"
        fake_canonical.api_key_env_var = "OPENAI_API_KEY"

        fake_registry = {"openai": MagicMock(inference_base_url="https://api.openai.com/v1", api_key_env_var="OPENAI_API_KEY")}

        fake_config = {
            "providers": {"openai": {"model": "gpt-4"}},
            "custom_providers": [],
        }

        with patch("hermes_cli.providers.normalize_provider", return_value="openai"):
            with patch("hermes_cli.models.CANONICAL_PROVIDERS", [fake_canonical]):
                with patch("hermes_cli.auth.PROVIDER_REGISTRY", fake_registry):
                    with patch("hermes_cli.config.load_config", return_value=fake_config):
                        with patch.object(_pd, "_check_url_reachable", return_value=(True, "reachable (200)", 45.0)):
                            with patch.object(_pd, "_try_list_models_openai", return_value=(True, "2 models available", 2)):
                                with patch.object(_pd, "_run_openai_test_completion", return_value=(True, '"Hello..." (120ms)', 120.0)):
                                    result = _pd.diagnose_provider("openai")

        assert result == 0


class TestDiagnoseOllamaProvider:
    """Local providers don't need API keys."""

    def test_ollama_no_key_required(self, monkeypatch):
        from hermes_cli import provider_diagnose as _pd

        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

        fake_canonical = MagicMock()
        fake_canonical.slug = "ollama"
        fake_canonical.inference_base_url = "http://localhost:11434"
        fake_canonical.api_key_env_var = ""

        fake_registry = {"ollama": MagicMock(inference_base_url="http://localhost:11434", api_key_env_var="")}

        fake_config = {
            "providers": {"ollama": {"model": "llama3"}},
            "custom_providers": [],
        }

        with patch("hermes_cli.providers.normalize_provider", return_value="ollama"):
            with patch("hermes_cli.models.CANONICAL_PROVIDERS", [fake_canonical]):
                with patch("hermes_cli.auth.PROVIDER_REGISTRY", fake_registry):
                    with patch("hermes_cli.config.load_config", return_value=fake_config):
                        with patch.object(_pd, "_check_url_reachable", return_value=(True, "reachable (200)", 12.0)):
                            with patch.object(_pd, "_try_ollama_models", return_value=(True, "3 models available", 3)):
                                result = _pd.diagnose_provider("ollama")

        assert result == 0


class TestDiagnoseAnthropicProvider:
    """Anthropic uses x-api-key header and its own /v1/models endpoint."""

    def test_anthropic_happy_path(self, monkeypatch):
        from hermes_cli import provider_diagnose as _pd

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        fake_canonical = MagicMock()
        fake_canonical.slug = "anthropic"
        fake_canonical.inference_base_url = "https://api.anthropic.com"
        fake_canonical.api_key_env_var = "ANTHROPIC_API_KEY"

        fake_registry = {"anthropic": MagicMock(inference_base_url="https://api.anthropic.com", api_key_env_var="ANTHROPIC_API_KEY")}

        fake_config = {
            "providers": {"anthropic": {"model": "claude-3-opus-20240229"}},
            "custom_providers": [],
        }

        with patch("hermes_cli.providers.normalize_provider", return_value="anthropic"):
            with patch("hermes_cli.models.CANONICAL_PROVIDERS", [fake_canonical]):
                with patch("hermes_cli.auth.PROVIDER_REGISTRY", fake_registry):
                    with patch("hermes_cli.config.load_config", return_value=fake_config):
                        with patch.object(_pd, "_check_url_reachable", return_value=(True, "reachable (200)", 30.0)):
                            with patch.object(_pd, "_try_anthropic_models", return_value=(True, "1 models available", 1)):
                                with patch.object(_pd, "_run_anthropic_test_completion", return_value=(True, '"Hi!" (90ms)', 90.0)):
                                    result = _pd.diagnose_provider("anthropic")

        assert result == 0


class TestDiagnoseBedrockProvider:
    """AWS Bedrock uses boto3 instead of urllib."""

    def test_bedrock_missing_aws_profile(self, monkeypatch):
        from hermes_cli.provider_diagnose import diagnose_provider

        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

        fake_canonical = MagicMock()
        fake_canonical.slug = "bedrock"
        fake_canonical.inference_base_url = ""
        fake_canonical.api_key_env_var = ""

        with patch("hermes_cli.providers.normalize_provider", return_value="bedrock"):
            with patch("hermes_cli.models.CANONICAL_PROVIDERS", [fake_canonical]):
                result = diagnose_provider("bedrock")

        assert result == 1

    def test_bedrock_with_boto3(self, monkeypatch):
        from hermes_cli import provider_diagnose as _pd

        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

        fake_canonical = MagicMock()
        fake_canonical.slug = "bedrock"
        fake_canonical.inference_base_url = ""
        fake_canonical.api_key_env_var = ""

        fake_registry = {"bedrock": MagicMock(inference_base_url="", api_key_env_var="")}

        fake_config = {
            "providers": {},
            "custom_providers": [],
            "bedrock": {"profile": ""},
        }

        with patch("hermes_cli.providers.normalize_provider", return_value="bedrock"):
            with patch("hermes_cli.models.CANONICAL_PROVIDERS", [fake_canonical]):
                with patch("hermes_cli.auth.PROVIDER_REGISTRY", fake_registry):
                    with patch("hermes_cli.config.load_config", return_value=fake_config):
                        with patch.object(_pd, "_check_url_reachable", return_value=(True, "reachable", 1.0)):
                            with patch.object(_pd, "_try_bedrock_list_models", return_value=(True, "5 models available", 5)):
                                result = _pd.diagnose_provider("bedrock")

        assert result == 0
