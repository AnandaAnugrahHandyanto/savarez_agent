"""
Tests for configurable default_headers feature (#12785).

Verifies that user-configured default_headers from config.yaml are merged
into OpenAI client kwargs for both the main agent client and auxiliary clients,
with user-configured headers winning over provider defaults on key conflicts.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_openai_client(**kwargs):
    """Create a MagicMock that looks like an OpenAI client."""
    c = MagicMock()
    c.api_key = kwargs.get("api_key", "sk-test-key-1234567890")
    c.base_url = kwargs.get("base_url", "https://api.example.com/v1")
    c._default_headers = kwargs.get("default_headers", None)
    return c


def _make_tool_defs():
    """Minimal tool definitions list."""
    return []


def _minimal_agent_kwargs():
    """Return the minimal kwargs that let AIAgent.__init__ succeed."""
    return dict(
        api_key="sk-test-key-1234567890",
        base_url="https://api.test.com/v1",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )


# ── Config file fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def hermes_home_config(tmp_path):
    """Fixture that sets HERMES_HOME to a temp dir and writes a config.yaml.

    The config can be overridden via the `config_override` dict parameter.
    """
    config_dir = tmp_path / ".hermes"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"

    def _write(config_override: dict = None):
        import yaml
        base = {"model": {"default_headers": {}}}
        if config_override:
            # Deep merge
            _merge = base.copy()
            for k, v in config_override.items():
                if isinstance(v, dict) and k in _merge and isinstance(_merge[k], dict):
                    _merge[k].update(v)
                else:
                    _merge[k] = v
            base = _merge
        config_path.write_text(yaml.dump(base, default_flow_style=False))
        return config_path

    with patch.dict(os.environ, {"HERMES_HOME": str(config_dir)}, clear=False):
        yield _write


# ── Tests for run_agent.py (main client) ─────────────────────────────────────

class TestMainAgentDefaultHeaders:
    """Tests that user-configured default_headers flow into the main agent client."""

    def test_user_headers_are_merged_into_client_kwargs(self, hermes_home_config):
        """User-configured default_headers should appear in client_kwargs."""
        hermes_home_config({
            "model": {
                "default_headers": {
                    "User-Agent": "HermesAgent/1.0",
                    "X-Client-Name": "Hermes",
                }
            }
        })
        with patch("run_agent.OpenAI", return_value=_mock_openai_client()), \
             patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()), \
             patch("run_agent.check_toolset_requirements", return_value={}):
            agent = AIAgent(**_minimal_agent_kwargs())
            kw = agent._client_kwargs
            assert "default_headers" in kw
            headers = kw["default_headers"]
            assert headers.get("User-Agent") == "HermesAgent/1.0"
            assert headers.get("X-Client-Name") == "Hermes"

    def test_user_headers_override_provider_headers(self, hermes_home_config):
        """User headers win over provider-level default_headers on key conflicts."""
        hermes_home_config({
            "model": {
                "default_headers": {
                    "User-Agent": "MyCustomAgent/2.0",
                }
            }
        })
        # Simulate a provider profile that also sets User-Agent
        with patch("run_agent.OpenAI", return_value=_mock_openai_client()), \
             patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()), \
             patch("run_agent.check_toolset_requirements", return_value={}), \
             patch("providers.get_provider_profile") as mock_get_profile:
            mock_profile = MagicMock()
            mock_profile.default_headers = {"User-Agent": "ProviderDefault/1.0"}
            mock_get_profile.return_value = mock_profile

            agent = AIAgent(
                api_key="sk-test-key-1234567890",
                base_url="https://custom.example.com/v1",
                provider="custom",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            kw = agent._client_kwargs
            headers = kw.get("default_headers", {})
            # User's User-Agent should win
            assert headers.get("User-Agent") == "MyCustomAgent/2.0"

    def test_user_headers_empty_dict_no_effect(self, hermes_home_config):
        """An empty default_headers dict should not overwrite provider headers."""
        hermes_home_config({
            "model": {
                "default_headers": {},
            }
        })
        with patch("run_agent.OpenAI", return_value=_mock_openai_client()), \
             patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()), \
             patch("run_agent.check_toolset_requirements", return_value={}), \
             patch("providers.get_provider_profile") as mock_get_profile:
            mock_profile = MagicMock()
            mock_profile.default_headers = {"X-Provider": "test"}
            mock_get_profile.return_value = mock_profile

            agent = AIAgent(
                api_key="sk-test-key-1234567890",
                base_url="https://custom.example.com/v1",
                provider="custom",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            kw = agent._client_kwargs
            headers = kw.get("default_headers", {})
            # Provider headers should still be present
            assert headers.get("X-Provider") == "test"

    def test_user_headers_are_not_lost_with_routed_client(self, hermes_home_config):
        """When using routed client (no explicit creds), user headers still merge."""
        hermes_home_config({
            "model": {
                "default_headers": {
                    "User-Agent": "RoutedTest/1.0",
                }
            }
        })
        mock_client = _mock_openai_client(
            api_key="sk-routed",
            base_url="https://routed.example.com/v1",
        )
        mock_client._default_headers = {"X-Router": "yes"}

        from agent.auxiliary_client import resolve_provider_client
        with patch("run_agent.OpenAI", return_value=_mock_openai_client()), \
             patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()), \
             patch("run_agent.check_toolset_requirements", return_value={}), \
             patch("agent.auxiliary_client.resolve_provider_client",
                   return_value=(mock_client, "some-model")):
            agent = AIAgent(
                provider="test-provider",
                model="test-model",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            kw = agent._client_kwargs
            headers = kw.get("default_headers", {})
            assert headers.get("User-Agent") == "RoutedTest/1.0"
            # Router headers preserved
            assert headers.get("X-Router") == "yes"

    def test_no_config_file_does_not_crash(self):
        """When no config.yaml exists, agent init should not crash."""
        with patch("run_agent.OpenAI", return_value=_mock_openai_client()), \
             patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()), \
             patch("run_agent.check_toolset_requirements", return_value={}), \
             patch("hermes_cli.config.load_config", return_value={}):
            agent = AIAgent(**_minimal_agent_kwargs())
            kw = agent._client_kwargs
            # Should not crash; default_headers may or may not be present
            assert "default_headers" not in kw or kw["default_headers"] == {}


# ── Tests for cli.py (config defaults) ───────────────────────────────────────

class TestCliConfigDefaults:
    """Tests that load_cli_config() includes default_headers in its defaults."""

    def test_default_headers_in_config_defaults(self):
        """The defaults dict in load_cli_config should have default_headers."""
        from cli import load_cli_config
        config = load_cli_config()
        model_section = config.get("model", {})
        assert "default_headers" in model_section
        assert model_section["default_headers"] == {}

    def test_user_config_preserves_default_headers(self, hermes_home_config):
        """User config with default_headers should be reflected in load_cli_config."""
        hermes_home_config({
            "model": {
                "default_headers": {
                    "User-Agent": "CLI-Test/1.0",
                    "X-Custom": "value",
                }
            }
        })
        from cli import load_cli_config
        config = load_cli_config()
        model_section = config.get("model", {})
        assert model_section.get("default_headers", {}).get("User-Agent") == "CLI-Test/1.0"
        assert model_section.get("default_headers", {}).get("X-Custom") == "value"
