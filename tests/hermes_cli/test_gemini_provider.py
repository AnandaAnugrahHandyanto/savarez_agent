"""Tests for Google AI Studio (Gemini) provider integration."""

import os
import pytest
from unittest.mock import patch, MagicMock

from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider, resolve_api_key_provider_credentials
from hermes_cli.models import _PROVIDER_MODELS, _PROVIDER_LABELS, _PROVIDER_ALIASES, normalize_provider
from hermes_cli.model_normalize import normalize_model_for_provider, detect_vendor
from agent.model_metadata import get_model_context_length
from agent.models_dev import PROVIDER_TO_MODELS_DEV, list_agentic_models, _NOISE_PATTERNS


# ── Provider Registry ──

class TestGeminiProviderRegistry:
    def test_gemini_in_registry(self):
        assert "gemini" in PROVIDER_REGISTRY

    def test_gemini_config(self):
        pconfig = PROVIDER_REGISTRY["gemini"]
        assert pconfig.id == "gemini"
        assert pconfig.name == "Google AI Studio"
        assert pconfig.auth_type == "api_key"
        assert pconfig.inference_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"

    def test_gemini_env_vars(self):
        pconfig = PROVIDER_REGISTRY["gemini"]
        assert pconfig.api_key_env_vars == ("GOOGLE_API_KEY", "GEMINI_API_KEY")
        assert pconfig.base_url_env_var == "GEMINI_BASE_URL"

    def test_gemini_base_url(self):
        assert "generativelanguage.googleapis.com" in PROVIDER_REGISTRY["gemini"].inference_base_url


# ── Provider Aliases ──

PROVIDER_ENV_VARS = (
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_BASE_URL",
    "GLM_API_KEY", "ZAI_API_KEY", "KIMI_API_KEY",
    "MINIMAX_API_KEY", "DEEPSEEK_API_KEY",
)

@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    for var in PROVIDER_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestGeminiAliases:
    def test_explicit_gemini(self):
        assert resolve_provider("gemini") == "gemini"

    def test_alias_google(self):
        assert resolve_provider("google") == "gemini"

    def test_alias_google_gemini(self):
        assert resolve_provider("google-gemini") == "gemini"

    def test_alias_google_ai_studio(self):
        assert resolve_provider("google-ai-studio") == "gemini"

    def test_models_py_aliases(self):
        assert _PROVIDER_ALIASES.get("google") == "gemini"
        assert _PROVIDER_ALIASES.get("google-gemini") == "gemini"
        assert _PROVIDER_ALIASES.get("google-ai-studio") == "gemini"

    def test_normalize_provider(self):
        assert normalize_provider("google") == "gemini"
        assert normalize_provider("gemini") == "gemini"
        assert normalize_provider("google-ai-studio") == "gemini"


# ── Auto-detection ──

class TestGeminiAutoDetection:
    def test_auto_detects_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
        assert resolve_provider("auto") == "gemini"

    def test_auto_detects_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
        assert resolve_provider("auto") == "gemini"

    def test_google_api_key_priority_over_gemini(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "primary-key")
        monkeypatch.setenv("GEMINI_API_KEY", "alias-key")
        creds = resolve_api_key_provider_credentials("gemini")
        assert creds["api_key"] == "primary-key"
        assert creds["source"] == "GOOGLE_API_KEY"


# ── Credential Resolution ──

class TestGeminiCredentials:
    def test_resolve_with_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
        creds = resolve_api_key_provider_credentials("gemini")
        assert creds["provider"] == "gemini"
        assert creds["api_key"] == "google-secret"
        assert creds["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"

    def test_resolve_with_gemini_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
        creds = resolve_api_key_provider_credentials("gemini")
        assert creds["api_key"] == "gemini-secret"

    def test_resolve_with_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        monkeypatch.setenv("GEMINI_BASE_URL", "https://custom.endpoint/v1")
        creds = resolve_api_key_provider_credentials("gemini")
        assert creds["base_url"] == "https://custom.endpoint/v1"

    def test_runtime_gemini(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        from hermes_cli.runtime_provider import resolve_runtime_provider
        result = resolve_runtime_provider(requested="gemini")
        assert result["provider"] == "gemini"
        assert result["api_mode"] == "chat_completions"
        assert result["api_key"] == "google-key"
        assert result["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"


# ── Model Catalog ──

class TestGeminiModelCatalog:
    def test_provider_models_exist(self):
        assert "gemini" in _PROVIDER_MODELS
        models = _PROVIDER_MODELS["gemini"]
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "gemma-4-31b-it" in models

    def test_provider_models_has_3x(self):
        models = _PROVIDER_MODELS["gemini"]
        assert "gemini-3.1-pro-preview" in models
        assert "gemini-3-flash-preview" in models
        assert "gemini-3.1-flash-lite-preview" in models

    def test_provider_label(self):
        assert "gemini" in _PROVIDER_LABELS
        assert _PROVIDER_LABELS["gemini"] == "Google AI Studio"


# ── Model Normalization ──

class TestGeminiModelNormalization:
    def test_passthrough_bare_name(self):
        assert normalize_model_for_provider("gemini-2.5-flash", "gemini") == "gemini-2.5-flash"

    def test_strip_vendor_prefix(self):
        assert normalize_model_for_provider("google/gemini-2.5-flash", "gemini") == "google/gemini-2.5-flash"

    def test_gemma_vendor_detection(self):
        assert detect_vendor("gemma-4-31b-it") == "google"

    def test_gemini_vendor_detection(self):
        assert detect_vendor("gemini-2.5-flash") == "google"

    def test_aggregator_prepends_vendor(self):
        result = normalize_model_for_provider("gemini-2.5-flash", "openrouter")
        assert result == "google/gemini-2.5-flash"

    def test_gemma_aggregator_prepends_vendor(self):
        result = normalize_model_for_provider("gemma-4-31b-it", "openrouter")
        assert result == "google/gemma-4-31b-it"


# ── Context Length ──

class TestGeminiContextLength:
    def test_gemma_4_31b_context(self):
        # Mock external API lookups to test against hardcoded defaults
        # (models.dev and OpenRouter may return different values like 262144).
        with patch("agent.models_dev.lookup_models_dev_context", return_value=None), \
             patch("agent.model_metadata.fetch_model_metadata", return_value={}):
            ctx = get_model_context_length("gemma-4-31b-it", provider="gemini")
        assert ctx == 256000

    def test_gemma_4_26b_context(self):
        ctx = get_model_context_length("gemma-4-26b-it", provider="gemini")
        assert ctx == 256000

    def test_gemini_3_context(self):
        ctx = get_model_context_length("gemini-3.1-pro-preview", provider="gemini")
        assert ctx == 1048576


# ── Agent Init (no SyntaxError) ──

class TestGeminiAgentInit:
    def test_agent_imports_without_error(self):
        """Verify run_agent.py has no SyntaxError (the critical bug)."""
        import importlib
        import run_agent
        importlib.reload(run_agent)

    def test_gemini_agent_uses_chat_completions(self, monkeypatch):
        """Gemini falls through to chat_completions — no special elif needed."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with patch("run_agent.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from run_agent import AIAgent
            agent = AIAgent(
                model="gemini-2.5-flash",
                provider="gemini",
                api_key="test-key",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            )
            assert agent.api_mode == "chat_completions"
            assert agent.provider == "gemini"


# ── Tool Schema Sanitization for Google ──

class TestGeminiToolConversion:
    """Verify OpenAI-format tools are converted to Google-native format."""

    @pytest.fixture()
    def agent(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        with patch("run_agent.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from run_agent import AIAgent
            agent = AIAgent(
                model="gemini-2.5-flash",
                provider="gemini",
                api_key="test-key",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            )
        return agent

    def test_is_google_api(self, agent):
        assert agent._is_google_api()

    def test_is_google_api_false_for_openai(self, agent):
        agent.base_url = "https://api.openai.com/v1"
        assert not agent._is_google_api()

    def test_convert_tools_unwraps_openai_format(self, agent):
        """OpenAI wrapper (type+function) should be stripped for Google."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                },
            }
        ]
        result = agent._convert_tools_for_google(tools)
        assert len(result) == 1
        assert "function_declarations" in result[0]
        decls = result[0]["function_declarations"]
        assert len(decls) == 1
        assert decls[0]["name"] == "read_file"
        assert decls[0]["description"] == "Read a file"
        assert "type" not in result[0]  # no OpenAI wrapper
        assert "function" not in result[0]  # no OpenAI wrapper

    def test_convert_tools_multiple(self, agent):
        tools = [
            {"type": "function", "function": {"name": "tool_a", "description": "A", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "tool_b", "description": "B", "parameters": {"type": "object", "properties": {}}}},
        ]
        result = agent._convert_tools_for_google(tools)
        decls = result[0]["function_declarations"]
        assert len(decls) == 2
        assert decls[0]["name"] == "tool_a"
        assert decls[1]["name"] == "tool_b"

    def test_convert_tools_empty(self, agent):
        assert agent._convert_tools_for_google([]) == []
        assert agent._convert_tools_for_google(None) == []

    def test_sanitize_strips_additional_properties(self, agent):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "additionalProperties": False,
        }
        result = agent._sanitize_google_schema(schema)
        assert "additionalProperties" not in result
        assert result["type"] == "object"
        assert result["properties"]["x"]["type"] == "string"

    def test_sanitize_strips_unsupported_keys(self, agent):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string", "default": "hi", "title": "X"}},
            "anyOf": [{"type": "string"}],
            "$ref": "#/defs/Foo",
        }
        result = agent._sanitize_google_schema(schema)
        assert "anyOf" not in result
        assert "$ref" not in result
        assert "default" not in result["properties"]["x"]
        assert "title" not in result["properties"]["x"]

    def test_sanitize_adds_missing_type(self, agent):
        schema = {"properties": {"a": {"type": "integer"}}}
        result = agent._sanitize_google_schema(schema)
        assert result["type"] == "object"

    def test_sanitize_nested_objects(self, agent):
        schema = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "default": "test"},
                    },
                    "additionalProperties": True,
                },
            },
        }
        result = agent._sanitize_google_schema(schema)
        nested = result["properties"]["config"]
        assert "additionalProperties" not in nested
        assert "default" not in nested["properties"]["name"]

    def test_sanitize_array_items(self, agent):
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "default": ""},
                },
            },
        }
        result = agent._sanitize_google_schema(schema)
        assert "default" not in result["properties"]["tags"]["items"]

    def test_build_api_kwargs_google_uses_extra_body(self, agent):
        """For Google endpoints, tools go in extra_body, not top-level tools."""
        agent.tools = [
            {
                "type": "function",
                "function": {
                    "name": "terminal",
                    "description": "Run commands",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        agent.max_tokens = None
        agent.reasoning_config = None
        agent.request_overrides = None
        agent.providers_allowed = None
        agent.providers_ignored = None
        agent.providers_order = None
        agent.provider_sort = None
        agent.provider_require_parameters = False
        agent.provider_data_collection = None
        agent._ollama_num_ctx = None
        msgs = [{"role": "system", "content": "You are helpful."}]
        kwargs = agent._build_api_kwargs(msgs)
        # tools should NOT be in top-level kwargs (would fail Google validation)
        assert "tools" not in kwargs
        # tools should be in extra_body as Google-native format
        assert "extra_body" in kwargs
        google_tools = kwargs["extra_body"]["tools"]
        assert "function_declarations" in google_tools[0]
        assert google_tools[0]["function_declarations"][0]["name"] == "terminal"


# ── models.dev Integration ──

class TestGeminiModelsDev:
    def test_gemini_mapped_to_google(self):
        assert PROVIDER_TO_MODELS_DEV.get("gemini") == "google"

    def test_noise_filter_excludes_tts(self):
        assert _NOISE_PATTERNS.search("gemini-2.5-pro-preview-tts")

    def test_noise_filter_excludes_dated_preview(self):
        assert _NOISE_PATTERNS.search("gemini-2.5-flash-preview-04-17")

    def test_noise_filter_excludes_embedding(self):
        assert _NOISE_PATTERNS.search("gemini-embedding-001")

    def test_noise_filter_excludes_live(self):
        assert _NOISE_PATTERNS.search("gemini-live-2.5-flash")

    def test_noise_filter_excludes_image(self):
        assert _NOISE_PATTERNS.search("gemini-2.5-flash-image")

    def test_noise_filter_excludes_customtools(self):
        assert _NOISE_PATTERNS.search("gemini-3.1-pro-preview-customtools")

    def test_noise_filter_passes_stable(self):
        assert not _NOISE_PATTERNS.search("gemini-2.5-flash")

    def test_noise_filter_passes_preview(self):
        # Non-dated preview (e.g. gemini-3-flash-preview) should pass
        assert not _NOISE_PATTERNS.search("gemini-3-flash-preview")

    def test_noise_filter_passes_gemma(self):
        assert not _NOISE_PATTERNS.search("gemma-4-31b-it")

    def test_list_agentic_models_with_mock_data(self):
        """list_agentic_models filters correctly from mock models.dev data."""
        mock_data = {
            "google": {
                "models": {
                    "gemini-3-flash-preview": {"tool_call": True},
                    "gemini-2.5-pro": {"tool_call": True},
                    "gemini-embedding-001": {"tool_call": False},
                    "gemini-2.5-flash-preview-tts": {"tool_call": False},
                    "gemini-live-2.5-flash": {"tool_call": True},
                    "gemini-2.5-flash-preview-04-17": {"tool_call": True},
                    "gemma-4-31b-it": {"tool_call": True},
                }
            }
        }
        with patch("agent.models_dev.fetch_models_dev", return_value=mock_data):
            result = list_agentic_models("gemini")
        assert "gemini-3-flash-preview" in result
        assert "gemini-2.5-pro" in result
        assert "gemma-4-31b-it" in result
        # Filtered out:
        assert "gemini-embedding-001" not in result      # no tool_call
        assert "gemini-2.5-flash-preview-tts" not in result  # no tool_call
        assert "gemini-live-2.5-flash" not in result     # noise: live-
        assert "gemini-2.5-flash-preview-04-17" not in result  # noise: dated preview
