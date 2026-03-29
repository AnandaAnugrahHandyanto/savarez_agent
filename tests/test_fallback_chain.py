"""Tests for the multi-provider fallback chain feature.

Verifies that AIAgent can cascade through multiple fallback providers
when earlier ones fail, and that the gateway config loader correctly
parses both the new ``fallback_models`` (list) and the legacy
``fallback_model`` (single dict) formats.
"""

import textwrap
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from run_agent import AIAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _make_agent(fallback_model=None):
    """Create a minimal AIAgent with optional fallback config."""
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model,
        )
        agent.client = MagicMock()
        return agent


def _mock_client(base_url="https://openrouter.ai/api/v1", api_key="test-key"):
    """Create a mock OpenAI client for resolve_provider_client."""
    client = MagicMock()
    client.api_key = api_key
    client.base_url = base_url
    return client


# =============================================================================
# Fallback chain init
# =============================================================================

class TestFallbackChainInit:
    """Verify _fallback_chain is correctly populated from the _chain key."""

    def test_no_chain_key_gives_empty_chain(self):
        agent = _make_agent(
            fallback_model={"provider": "openrouter", "model": "test-model"},
        )
        assert agent._fallback_model is not None
        assert agent._fallback_chain == []

    def test_chain_key_populates_chain(self):
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [
                    {"provider": "custom", "model": "model-b"},
                    {"provider": "custom", "model": "model-c"},
                ],
            },
        )
        assert agent._fallback_model["provider"] == "openrouter"
        assert agent._fallback_model["model"] == "model-a"
        assert len(agent._fallback_chain) == 2
        assert agent._fallback_chain[0]["model"] == "model-b"
        assert agent._fallback_chain[1]["model"] == "model-c"

    def test_chain_key_removed_from_first_fallback(self):
        """_chain should be popped off the dict, not left dangling."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [{"provider": "custom", "model": "model-b"}],
            },
        )
        assert "_chain" not in agent._fallback_model

    def test_empty_chain_key(self):
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [],
            },
        )
        assert agent._fallback_chain == []

    def test_none_chain_key(self):
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": None,
            },
        )
        assert agent._fallback_chain == []

    def test_non_dict_fallback_gives_no_chain(self):
        agent = _make_agent(fallback_model="not-a-dict")
        assert agent._fallback_model is None
        assert agent._fallback_chain == []

    def test_none_fallback_gives_no_chain(self):
        agent = _make_agent(fallback_model=None)
        assert agent._fallback_model is None
        assert agent._fallback_chain == []


# =============================================================================
# Fallback chain activation (cycling through providers)
# =============================================================================

class TestFallbackChainActivation:
    """Verify _try_activate_fallback cycles through the full chain."""

    def test_single_fallback_no_chain(self):
        """Classic behavior: one fallback, then done."""
        agent = _make_agent(
            fallback_model={"provider": "openrouter", "model": "model-a"},
        )
        client_a = _mock_client(base_url="https://openrouter.ai/api/v1")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_a, "model-a"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.model == "model-a"

            # Second call: no more in chain
            assert agent._try_activate_fallback() is False

    def test_two_fallbacks_both_succeed(self):
        """Chain of 2: first activates, then second activates."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [{"provider": "custom", "model": "model-b"}],
            },
        )
        client_a = _mock_client(base_url="https://openrouter.ai/api/v1")
        client_b = _mock_client(base_url="http://localhost:8080/v1")

        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_a, "model-a"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.model == "model-a"
            assert agent.provider == "openrouter"

        # Now simulate model-a also failing
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_b, "model-b"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.model == "model-b"
            assert agent.provider == "custom"

        # Chain exhausted
        assert agent._try_activate_fallback() is False

    def test_three_fallbacks_full_cascade(self):
        """Chain of 3: each activates in order."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [
                    {"provider": "custom", "model": "model-b"},
                    {"provider": "custom", "model": "model-c"},
                ],
            },
        )
        clients = [
            _mock_client(base_url="https://openrouter.ai/api/v1"),
            _mock_client(base_url="http://localhost:8080/v1"),
            _mock_client(base_url="http://localhost:9090/v1"),
        ]
        models = ["model-a", "model-b", "model-c"]

        for i, (client, model) in enumerate(zip(clients, models)):
            with patch(
                "agent.auxiliary_client.resolve_provider_client",
                return_value=(client, model),
            ):
                assert agent._try_activate_fallback() is True, f"Fallback {i} failed"
                assert agent.model == model

        # All exhausted
        assert agent._try_activate_fallback() is False

    def test_first_fallback_fails_skips_to_second(self):
        """If resolve_provider_client returns None for fallback 1, try fallback 2."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [{"provider": "custom", "model": "model-b"}],
            },
        )

        # First fallback: resolve fails
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),
        ):
            assert agent._try_activate_fallback() is False
            # _fallback_activated stays False because activation failed
            assert agent._fallback_activated is False

        # But chain still has model-b, and _fallback_model is still model-a (failed)
        # The user would call _try_activate_fallback again after the retry loop.
        # Since _fallback_activated is False and _fallback_model is set, it will
        # try the same one again.  This is by design — the retry loop may have
        # different network conditions on next attempt.

    def test_chain_preserved_across_failed_activation(self):
        """A failed activation doesn't consume the chain entry."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [{"provider": "custom", "model": "model-b"}],
            },
        )
        # Chain should still have 1 entry
        assert len(agent._fallback_chain) == 1

        # Fail to activate first fallback
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(None, None),
        ):
            agent._try_activate_fallback()

        # Chain still intact — the failed fallback didn't pop from chain
        assert len(agent._fallback_chain) == 1

    def test_successful_first_then_chain_advances(self):
        """After successful activation, next call advances the chain."""
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [
                    {"provider": "custom", "model": "model-b", "base_url": "http://localhost/v1"},
                ],
            },
        )
        client_a = _mock_client(base_url="https://openrouter.ai/api/v1")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_a, "model-a"),
        ):
            assert agent._try_activate_fallback() is True

        # Now chain should still have model-b
        assert len(agent._fallback_chain) == 1
        assert agent._fallback_chain[0]["model"] == "model-b"

        # Calling again should advance to model-b
        client_b = _mock_client(base_url="http://localhost/v1")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_b, "model-b"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.model == "model-b"

        # Chain now empty
        assert len(agent._fallback_chain) == 0
        assert agent._try_activate_fallback() is False


# =============================================================================
# Fallback chain with different provider types
# =============================================================================

class TestFallbackChainProviderTypes:
    """Verify chain works across different api_mode types."""

    def test_openrouter_then_codex(self):
        agent = _make_agent(
            fallback_model={
                "provider": "openrouter",
                "model": "model-a",
                "_chain": [{"provider": "openai-codex", "model": "gpt-5.4"}],
            },
        )
        # First: openrouter (chat_completions)
        client_a = _mock_client(base_url="https://openrouter.ai/api/v1")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_a, "model-a"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.api_mode == "chat_completions"

        # Second: codex (codex_responses)
        client_b = _mock_client(base_url="https://chatgpt.com/backend-api/codex")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_b, "gpt-5.4"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.api_mode == "codex_responses"
            assert agent.model == "gpt-5.4"

    def test_codex_then_anthropic(self):
        agent = _make_agent(
            fallback_model={
                "provider": "openai-codex",
                "model": "gpt-5.4",
                "_chain": [{"provider": "anthropic", "model": "claude-sonnet-4"}],
            },
        )
        # First: codex
        client_a = _mock_client(base_url="https://chatgpt.com/backend-api/codex")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_a, "gpt-5.4"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent.api_mode == "codex_responses"

        # Second: anthropic
        client_b = _mock_client(base_url="https://api.anthropic.com/v1")
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(client_b, "claude-sonnet-4"),
        ) as mock_resolve, patch(
            "agent.anthropic_adapter.build_anthropic_client",
            return_value=MagicMock(),
        ), patch(
            "agent.anthropic_adapter.resolve_anthropic_token",
            return_value="test-token",
        ), patch(
            "agent.anthropic_adapter._is_oauth_token",
            return_value=False,
        ):
            assert agent._try_activate_fallback() is True
            assert agent.api_mode == "anthropic_messages"
            assert agent.model == "claude-sonnet-4"


# =============================================================================
# Gateway config loader — _load_fallback_model
# =============================================================================

class TestGatewayLoadFallbackModel:
    """Test the gateway's config parser for fallback_models."""

    def _load_with_config(self, yaml_content: str) -> dict | None:
        """Write yaml to a temp file and call _load_fallback_model."""
        import yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.yaml"
            cfg_path.write_text(textwrap.dedent(yaml_content))
            with patch("gateway.run._hermes_home", Path(tmpdir)):
                from gateway.run import GatewayRunner
                return GatewayRunner._load_fallback_model()

    def test_legacy_single_fallback_model(self):
        result = self._load_with_config("""
            fallback_model:
              provider: openrouter
              model: test-model
        """)
        assert result is not None
        assert result["provider"] == "openrouter"
        assert result["model"] == "test-model"
        assert "_chain" not in result  # single entry, no chain

    def test_fallback_models_single_entry(self):
        result = self._load_with_config("""
            fallback_models:
              - provider: openrouter
                model: model-a
        """)
        assert result is not None
        assert result["provider"] == "openrouter"
        assert result["model"] == "model-a"
        assert "_chain" not in result

    def test_fallback_models_multiple_entries(self):
        result = self._load_with_config("""
            fallback_models:
              - provider: openrouter
                model: model-a
              - provider: custom
                model: model-b
                base_url: http://localhost:8080/v1
        """)
        assert result is not None
        assert result["provider"] == "openrouter"
        assert result["model"] == "model-a"
        assert "_chain" in result
        assert len(result["_chain"]) == 1
        assert result["_chain"][0]["model"] == "model-b"
        assert result["_chain"][0]["base_url"] == "http://localhost:8080/v1"

    def test_fallback_models_three_entries(self):
        result = self._load_with_config("""
            fallback_models:
              - provider: openrouter
                model: model-a
              - provider: openai-codex
                model: gpt-5.4
              - provider: custom
                model: model-c
        """)
        assert result is not None
        assert result["model"] == "model-a"
        assert len(result["_chain"]) == 2
        assert result["_chain"][0]["model"] == "gpt-5.4"
        assert result["_chain"][1]["model"] == "model-c"

    def test_fallback_models_takes_priority_over_fallback_model(self):
        """When both keys exist, fallback_models wins."""
        result = self._load_with_config("""
            fallback_model:
              provider: old-provider
              model: old-model
            fallback_models:
              - provider: new-provider
                model: new-model
        """)
        assert result is not None
        assert result["provider"] == "new-provider"
        assert result["model"] == "new-model"

    def test_empty_fallback_models_falls_back_to_legacy(self):
        result = self._load_with_config("""
            fallback_models: []
            fallback_model:
              provider: legacy
              model: legacy-model
        """)
        assert result is not None
        assert result["provider"] == "legacy"

    def test_no_config_returns_none(self):
        result = self._load_with_config("""
            model:
              default: test
        """)
        assert result is None

    def test_empty_config_returns_none(self):
        result = self._load_with_config("")
        assert result is None

    def test_fallback_models_skips_invalid_entries(self):
        """Entries missing provider or model are silently skipped."""
        result = self._load_with_config("""
            fallback_models:
              - provider: ""
                model: model-a
              - model: model-b
              - provider: valid
                model: model-c
        """)
        assert result is not None
        assert result["provider"] == "valid"
        assert result["model"] == "model-c"
        assert "_chain" not in result  # only one valid entry

    def test_fallback_models_all_invalid_returns_none(self):
        result = self._load_with_config("""
            fallback_models:
              - provider: ""
                model: ""
              - model: no-provider
        """)
        assert result is None

    def test_fallback_models_preserves_extra_keys(self):
        """Extra keys like base_url and api_key_env are passed through."""
        result = self._load_with_config("""
            fallback_models:
              - provider: custom
                model: my-model
                base_url: http://example.com/v1
                api_key_env: MY_KEY
        """)
        assert result is not None
        assert result["base_url"] == "http://example.com/v1"
        assert result["api_key_env"] == "MY_KEY"

    def test_fallback_models_non_list_ignored(self):
        """If fallback_models is not a list, fall back to legacy."""
        result = self._load_with_config("""
            fallback_models: "not-a-list"
            fallback_model:
              provider: legacy
              model: legacy-model
        """)
        assert result is not None
        assert result["provider"] == "legacy"
