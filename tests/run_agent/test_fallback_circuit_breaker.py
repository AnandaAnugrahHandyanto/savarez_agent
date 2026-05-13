"""Tests for #24996 — fallback circuit-breaker to prevent memory exhaustion.

Verifies that:
1. >=5 activations in 60s trips the breaker → returns False (chain-exhausted).
2. <2s between activations triggers sleep to enforce the throttle.
3. >2s between activations proceeds without throttle sleep.
4. Breaker counter resets after 60s window passes.
5. Circuit-breaker state is per-instance, not shared across agent instances.
"""

import pytest
import time
from unittest.mock import MagicMock, patch


def _mock_client():
    c = MagicMock()
    c.api_key = "test-key"
    c.base_url = MagicMock()
    c.base_url.__str__ = lambda self: "https://example.com/v1"
    c.base_url.rstrip = lambda s: "https://example.com/v1"
    return c


def _make_agent(fallback_model=None):
    """Minimal AIAgent for testing fallback circuit-breaker."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent
        a = AIAgent(
            api_key="test-key-12345",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model or [],
        )
        a.client = MagicMock()
        a._cached_system_prompt = "You are helpful."
        a._use_prompt_caching = False
        a.tool_delay = 0
        a.compression_enabled = False
        a._fallback_activations = []  # ensure clean state
        return a


class TestFallbackCircuitBreaker:
    """Circuit-breaker throttle (>=2s gap) and breaker (>=5 in 60s)."""

    def test_trips_after_5_activations_in_60s(self):
        """5 activations within 60s → return False (chain exhausted)."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        # Simulate 5 prior activations at "now" (all within 60s window)
        now = time.monotonic()
        agent._fallback_activations = [now - 5, now - 10, now - 20, now - 40, now - 50]

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is False, "Circuit-breaker should trip after 5 activations in 60s"

    def test_allows_activations_after_60s_window_clears(self):
        """Activations older than 60s are pruned, allowing new activations."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        # Simulate 4 recent activations + 1 stale (>60s old) that should be pruned
        now = time.monotonic()
        agent._fallback_activations = [now - 5, now - 10, now - 20, now - 40, now - 120]

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is True, "Stale activation (>60s) should be pruned, allowing new activation"

    def test_throttle_enforces_2s_gap(self):
        """Back-to-back activations (<2s gap) trigger sleep before proceeding."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        # One recent activation 0.5s ago — next should be throttled
        now = time.monotonic()
        agent._fallback_activations = [now - 0.5]

        sleep_calls = []
        def _sleep(duration):
            sleep_calls.append(duration)

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                with patch("time.monotonic", return_value=now):
                    with patch("time.sleep", side_effect=_sleep):
                        ok = agent._try_activate_fallback()

        assert ok is True, "Should still succeed after throttle sleep"
        assert len(sleep_calls) == 1, "Should have called time.sleep exactly once"
        assert 1.4 <= sleep_calls[0] <= 1.6, f"Expected ~1.5s sleep, got {sleep_calls[0]:.2f}s"

    def test_no_throttle_when_gap_exceeds_2s(self):
        """Activations with >2s gap proceed immediately without sleep."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        # Last activation 3s ago — no throttle needed
        now = time.monotonic()
        agent._fallback_activations = [now - 3.0]

        sleep_calls = []
        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                with patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)):
                    ok = agent._try_activate_fallback()

        assert ok is True, "Should succeed without throttle"
        assert sleep_calls == [], f"Expected no sleep calls, got {sleep_calls}"

    def test_activations_accumulated_correctly(self):
        """Successful activation appends to _fallback_activations list."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        initial_count = len(agent._fallback_activations)

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is True
        assert len(agent._fallback_activations) == initial_count + 1

    def test_breaker_state_is_per_instance(self):
        """Circuit-breaker state is isolated — one agent tripping doesn't affect another."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]

        agent_a = _make_agent(fallback_model=fbs)
        agent_b = _make_agent(fallback_model=fbs)

        # Trip the breaker on agent_a
        now = time.monotonic()
        agent_a._fallback_activations = [now - 5, now - 10, now - 20, now - 40, now - 50]

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        # agent_a should trip
        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok_a = agent_a._try_activate_fallback()

        assert ok_a is False, "agent_a should have tripped the breaker"

        # agent_b should still work (fresh instance, no activations)
        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok_b = agent_b._try_activate_fallback()

        assert ok_b is True, "agent_b should have a clean breaker state"

    def test_emits_status_on_breaker_trip(self):
        """Tripping the breaker emits a status message to the user."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        now = time.monotonic()
        agent._fallback_activations = [now - 5, now - 10, now - 20, now - 40, now - 50]

        emit_calls = []
        agent._emit_status = lambda msg: emit_calls.append(msg)

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is False
        assert any("Circuit-breaker" in msg and "5" in msg for msg in emit_calls), (
            f"Expected breaker status message, got: {emit_calls}"
        )

    def test_emits_status_on_throttle_sleep(self):
        """Throttle sleep emits a status message before sleeping."""
        fbs = [{"provider": "openrouter", "model": "z-ai/foo"}]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "minimax"
        agent.model = "MiniMax-M2.7"
        agent.base_url = "https://api.minimax.io/v1"

        now = time.monotonic()
        agent._fallback_activations = [now - 0.5]

        emit_calls = []
        agent._emit_status = lambda msg: emit_calls.append(msg)

        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            return _mock_client(), model

        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                with patch("time.sleep"):
                    ok = agent._try_activate_fallback()

        assert ok is True
        assert any("Circuit-breaker" in msg and "sleeping" in msg for msg in emit_calls), (
            f"Expected throttle status message, got: {emit_calls}"
        )