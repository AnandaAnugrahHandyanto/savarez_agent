"""Tests for per-provider streaming configuration in fallback chain.

Covers issue #21522: custom fallback providers that don't support SSE
streaming should be usable via a ``stream: false`` config flag.  Also
tests that streaming state is correctly restored when advancing through
the fallback chain.
"""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent(fallback_model=None):
    """Create a minimal AIAgent with optional fallback config."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model,
        )
        agent.client = MagicMock()
        return agent


def _mock_client(base_url="https://openrouter.ai/api/v1", api_key="fb-key"):
    mock = MagicMock()
    mock.base_url = base_url
    mock.api_key = api_key
    return mock


# ── Per-provider stream config ───────────────────────────────────────────


class TestFallbackStreamConfig:
    """Tests for the ``stream`` field in fallback provider config."""

    def test_stream_false_sets_disable_streaming(self):
        """When fallback has stream: false, _disable_streaming is set."""
        fbs = [
            {
                "provider": "custom",
                "model": "my-model",
                "base_url": "http://proxy:8080/v1",
                "stream": False,
            }
        ]
        agent = _make_agent(fallback_model=fbs)
        # Before activation, streaming should not be disabled
        assert not getattr(agent, "_disable_streaming", False)

        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(base_url="http://proxy:8080/v1"), "my-model"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent._disable_streaming is True

    def test_stream_true_keeps_streaming_enabled(self):
        """When fallback has stream: true (or omitted), streaming stays on."""
        fbs = [
            {
                "provider": "openai",
                "model": "gpt-4o",
                "stream": True,
            }
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(), "gpt-4o"),
        ):
            assert agent._try_activate_fallback() is True
            assert not getattr(agent, "_disable_streaming", False)

    def test_stream_omitted_defaults_to_true(self):
        """When stream is not specified, streaming remains enabled."""
        fbs = [{"provider": "openai", "model": "gpt-4o"}]
        agent = _make_agent(fallback_model=fbs)
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(), "gpt-4o"),
        ):
            assert agent._try_activate_fallback() is True
            assert not getattr(agent, "_disable_streaming", False)

    def test_stream_false_string_treated_as_false(self):
        """YAML may parse 'false' as a string — handle gracefully."""
        fbs = [
            {
                "provider": "custom",
                "model": "my-model",
                "base_url": "http://proxy:8080/v1",
                "stream": "false",
            }
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(base_url="http://proxy:8080/v1"), "my-model"),
        ):
            assert agent._try_activate_fallback() is True
            assert agent._disable_streaming is True


# ── Streaming state restoration across fallback chain ────────────────────


class TestStreamingStateRestoration:
    """Tests that streaming state resets correctly across fallback chain."""

    def test_streaming_restored_after_non_streaming_fallback(self):
        """When advancing from stream:false to stream:true provider,
        _disable_streaming should be cleared."""
        fbs = [
            {
                "provider": "custom",
                "model": "no-sse-model",
                "base_url": "http://proxy:8080/v1",
                "stream": False,
            },
            {
                "provider": "openai",
                "model": "gpt-4o",
            },
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(), "resolved"),
        ):
            # First fallback: stream: false
            assert agent._try_activate_fallback() is True
            assert agent._disable_streaming is True

            # Second fallback: stream not set (defaults to True)
            assert agent._try_activate_fallback() is True
            assert not getattr(agent, "_disable_streaming", False)

    def test_streaming_disabled_across_multiple_non_streaming(self):
        """Multiple stream:false providers in a row keep it disabled."""
        fbs = [
            {"provider": "custom", "model": "a", "stream": False},
            {"provider": "custom", "model": "b", "stream": False},
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(), "resolved"),
        ):
            agent._try_activate_fallback()
            assert agent._disable_streaming is True
            agent._try_activate_fallback()
            assert agent._disable_streaming is True

    def test_runtime_disable_cleared_by_streaming_fallback(self):
        """If _disable_streaming was set at runtime (error detection),
        a stream:true fallback should still clear it."""
        fbs = [
            {"provider": "openai", "model": "gpt-4o"},
        ]
        agent = _make_agent(fallback_model=fbs)
        # Simulate runtime detection setting the flag
        agent._disable_streaming = True
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
            return_value=(_mock_client(), "gpt-4o"),
        ):
            assert agent._try_activate_fallback() is True
            # stream config not set (defaults True) → clear the flag
            assert not getattr(agent, "_disable_streaming", False)
