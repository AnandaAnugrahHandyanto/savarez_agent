"""Tests for fallback provider restore behavior."""
from unittest.mock import MagicMock, patch

import pytest


class TestFallbackRestore:
    """Fallback restore should properly track state and notify on persistent failure."""

    def test_fallback_activated_cleared_on_successful_restore(self):
        """_fallback_activated should be False after successful restore."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()

        # Simulate fallback activation
        agent._fallback_activated = True
        agent._fallback_index = 1
        agent._primary_runtime = {
            "model": "test-model",
            "provider": "test-provider",
            "base_url": "https://api.test.com",
            "api_mode": "openai_chat",
            "api_key": "test-key-1234567890",
            "client_kwargs": {},
            "use_prompt_caching": False,
            "compressor_model": None,
            "compressor_context_length": None,
            "compressor_base_url": None,
            "compressor_api_key": None,
            "compressor_provider": None,
        }

        # Mock client creation and context compressor
        with (
            patch.object(agent, "_create_openai_client", return_value=MagicMock()),
            patch.object(agent.context_compressor, "update_model"),
        ):
            result = agent._restore_primary_runtime()

        assert result is True
        assert agent._fallback_activated is False
        assert agent._fallback_index == 0
        assert agent._fallback_restore_fail_count == 0

    def test_fallback_activated_remains_true_on_failed_restore(self):
        """When restore fails, _fallback_activated should remain True."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()

        # Simulate fallback activation with a broken primary_runtime
        agent._fallback_activated = True
        agent._fallback_index = 1
        agent._primary_runtime = {"model": None}  # Will cause KeyError in restore

        result = agent._restore_primary_runtime()

        assert result is False
        assert agent._fallback_activated is True
        assert agent._fallback_restore_fail_count >= 1

    def test_restore_fail_count_increments_on_consecutive_failures(self):
        """Consecutive restore failures should increment the counter."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()

        agent._fallback_activated = True
        agent._fallback_index = 1
        agent._primary_runtime = {"model": None}  # Broken

        # First failure
        agent._restore_primary_runtime()
        count_after_first = agent._fallback_restore_fail_count

        # Second failure
        agent._fallback_activated = True  # Still in fallback
        agent._restore_primary_runtime()
        count_after_second = agent._fallback_restore_fail_count

        assert count_after_second == count_after_first + 1

    def test_restore_fail_count_resets_on_success(self):
        """Successful restore should reset the failure counter."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()

        # Simulate prior failures
        agent._fallback_restore_fail_count = 5

        agent._fallback_activated = True
        agent._fallback_index = 1
        agent._primary_runtime = {
            "model": "test-model",
            "provider": "test-provider",
            "base_url": "https://api.test.com",
            "api_mode": "openai_chat",
            "api_key": "test-key-1234567890",
            "client_kwargs": {},
            "use_prompt_caching": False,
            "compressor_model": None,
            "compressor_context_length": None,
            "compressor_base_url": None,
            "compressor_api_key": None,
            "compressor_provider": None,
        }

        with (
            patch.object(agent, "_create_openai_client", return_value=MagicMock()),
            patch.object(agent.context_compressor, "update_model"),
        ):
            agent._restore_primary_runtime()

        assert agent._fallback_restore_fail_count == 0
