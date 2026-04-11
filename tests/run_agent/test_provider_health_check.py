"""Tests for provider health check and auto-recovery."""
from unittest.mock import MagicMock, patch

import pytest


class TestProviderHealthCheck:
    """Agent should be able to probe primary provider health and auto-recover."""

    def test_health_check_returns_true_when_primary_healthy(self):
        """A healthy primary provider should return True from health check."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://my-llm.example.com/v1",
                provider="custom",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()
            agent.client.models.list.return_value = MagicMock(data=[])

        result = agent.check_provider_health()
        assert result is True

    def test_health_check_returns_false_when_primary_unreachable(self):
        """An unreachable primary provider should return False from health check."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://my-llm.example.com/v1",
                provider="custom",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()
            agent.client.models.list.side_effect = Exception("Connection refused")

        result = agent.check_provider_health()
        assert result is False

    def test_auto_recovery_restores_primary_when_healthy(self):
        """When primary becomes healthy, auto-recovery should restore it."""
        from run_agent import AIAgent

        with (
            patch("run_agent.get_tool_definitions", return_value=[]),
            patch("run_agent.check_toolset_requirements", return_value={}),
            patch("run_agent.OpenAI"),
        ):
            agent = AIAgent(
                api_key="test-key-1234567890",
                base_url="https://my-llm.example.com/v1",
                provider="custom",
                quiet_mode=True,
                skip_context_files=True,
                skip_memory=True,
            )
            agent.client = MagicMock()
            agent._fallback_activated = True

        # Mock: health check says primary is healthy
        with (
            patch.object(agent, "check_provider_health", return_value=True),
            patch.object(agent, "_restore_primary_runtime", return_value=True),
        ):
            result = agent.try_recover_primary()

        assert result is True
