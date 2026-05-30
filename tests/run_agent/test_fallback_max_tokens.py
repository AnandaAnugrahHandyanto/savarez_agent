"""Fallback activation re-resolves per-model max_tokens (#28782).

The global model.max_tokens must not leak onto a fallback provider; the
fallback model's own per-model custom_providers cap is resolved against the
cached _custom_providers. Explicit constructor values survive.
"""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent

FB_URL = "https://fallback.example/v1"
FB_MODEL = "fb-model"


def _make_agent(*, max_tokens, config_max_tokens, explicit=False, custom_providers=None):
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
            fallback_model=[{"provider": "custom", "model": FB_MODEL, "base_url": FB_URL}],
        )
    agent.client = MagicMock()
    agent.max_tokens = max_tokens
    agent._config_max_tokens = config_max_tokens
    agent._max_tokens_explicit = explicit
    agent._custom_providers = custom_providers or []
    return agent


def _cp(max_tokens, *, model=FB_MODEL, base_url=FB_URL):
    return [{"base_url": base_url, "models": {model: {"max_tokens": max_tokens}}}]


def _activate(agent):
    client = MagicMock()
    client.base_url = FB_URL
    with (
        patch("agent.auxiliary_client.resolve_provider_client", return_value=(client, FB_MODEL)),
        patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m),
    ):
        return agent._try_activate_fallback()


def test_fallback_reresolves_per_model_for_fallback_model():
    agent = _make_agent(max_tokens=131_072, config_max_tokens=131_072, custom_providers=_cp(8000))
    assert _activate(agent) is True
    assert agent.max_tokens == 8000
    assert agent._config_max_tokens == 8000


def test_fallback_drops_global_so_it_does_not_leak():
    # Global cap on the primary, no per-model entry for the fallback → no leak.
    agent = _make_agent(max_tokens=131_072, config_max_tokens=131_072, custom_providers=[])
    assert _activate(agent) is True
    assert agent.max_tokens is None
    assert agent._config_max_tokens is None


def test_explicit_max_tokens_survives_fallback():
    agent = _make_agent(max_tokens=5000, config_max_tokens=None, explicit=True, custom_providers=_cp(8000))
    assert _activate(agent) is True
    assert agent.max_tokens == 5000
