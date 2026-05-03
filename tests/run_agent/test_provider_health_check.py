"""Tests for provider health check and auto-recovery."""
from unittest.mock import MagicMock, patch, call

import pytest


def _make_agent(provider="custom", api_mode=None):
    """Create a minimal AIAgent for health-check tests."""
    from run_agent import AIAgent

    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://my-llm.example.com/v1",
            provider=provider,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    if api_mode:
        agent._primary_runtime["api_mode"] = api_mode
    return agent


class TestProviderHealthCheck:
    """Agent should be able to probe primary provider health and auto-recover."""

    def test_health_check_returns_true_when_primary_healthy(self):
        """A healthy primary provider should return True from health check."""
        agent = _make_agent()
        mock_probe = MagicMock()
        mock_probe.models.list.return_value = MagicMock(data=[])

        with (
            patch.object(agent, "_create_openai_client", return_value=mock_probe),
            patch.object(agent, "_close_openai_client"),
        ):
            result = agent.check_provider_health()

        assert result is True
        mock_probe.models.list.assert_called_once()

    def test_health_check_returns_false_when_primary_unreachable(self):
        """An unreachable primary provider should return False from health check."""
        agent = _make_agent()
        mock_probe = MagicMock()
        mock_probe.models.list.side_effect = Exception("Connection refused")

        with (
            patch.object(agent, "_create_openai_client", return_value=mock_probe),
            patch.object(agent, "_close_openai_client"),
        ):
            result = agent.check_provider_health()

        assert result is False

    def test_health_check_probes_primary_not_fallback_client(self):
        """Health check must probe the primary endpoint, not self.client (fallback)."""
        agent = _make_agent()
        # Simulate: agent is on fallback — self.client is the fallback client
        fallback_client = MagicMock(name="fallback_client")
        fallback_client.models.list.return_value = MagicMock(data=[])
        agent.client = fallback_client
        agent._fallback_activated = True

        # The primary probe client is separate
        primary_probe = MagicMock(name="primary_probe")
        primary_probe.models.list.return_value = MagicMock(data=[])

        with (
            patch.object(agent, "_create_openai_client", return_value=primary_probe),
            patch.object(agent, "_close_openai_client"),
        ):
            result = agent.check_provider_health()

        assert result is True
        # The probe must use _create_openai_client (primary creds), NOT self.client
        primary_probe.models.list.assert_called_once()
        fallback_client.models.list.assert_not_called()

    def test_health_check_skips_probe_for_anthropic_mode_primary(self):
        """Anthropic-mode primaries have no models.list; probe should be skipped (returns True)."""
        agent = _make_agent(provider="anthropic", api_mode="anthropic_messages")
        # self.client is None for anthropic_messages mode
        agent.client = None

        with patch.object(agent, "_create_openai_client") as mock_create:
            result = agent.check_provider_health()

        assert result is True
        # No OpenAI client should be created for an Anthropic-mode primary
        mock_create.assert_not_called()

    def test_health_check_probe_client_always_closed(self):
        """The temporary probe client must be closed even when models.list raises."""
        agent = _make_agent()
        mock_probe = MagicMock()
        mock_probe.models.list.side_effect = Exception("timeout")

        with (
            patch.object(agent, "_create_openai_client", return_value=mock_probe) as mock_create,
            patch.object(agent, "_close_openai_client") as mock_close,
        ):
            result = agent.check_provider_health()

        assert result is False
        mock_close.assert_called_once_with(mock_probe, reason="health_check_probe", shared=False)

    def test_auto_recovery_restores_primary_when_healthy(self):
        """When primary becomes healthy, auto-recovery should restore it."""
        agent = _make_agent()
        agent._fallback_activated = True

        with (
            patch.object(agent, "check_provider_health", return_value=True),
            patch.object(agent, "_restore_primary_runtime", return_value=True),
        ):
            result = agent.try_recover_primary()

        assert result is True

    def test_auto_recovery_skips_restore_when_already_on_primary(self):
        """try_recover_primary should be a no-op (return True) when not on fallback."""
        agent = _make_agent()
        agent._fallback_activated = False

        with (
            patch.object(agent, "check_provider_health") as mock_health,
            patch.object(agent, "_restore_primary_runtime") as mock_restore,
        ):
            result = agent.try_recover_primary()

        assert result is True
        mock_health.assert_not_called()
        mock_restore.assert_not_called()

    def test_auto_recovery_does_not_restore_when_still_unhealthy(self):
        """When primary is still down, try_recover_primary should return False without restoring."""
        agent = _make_agent()
        agent._fallback_activated = True

        with (
            patch.object(agent, "check_provider_health", return_value=False),
            patch.object(agent, "_restore_primary_runtime") as mock_restore,
        ):
            result = agent.try_recover_primary()

        assert result is False
        mock_restore.assert_not_called()
