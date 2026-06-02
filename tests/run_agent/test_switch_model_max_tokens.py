"""switch_model re-resolves per-model max_tokens for the new model (#28782).

The global model.max_tokens belongs to the primary model only; on a /model
switch the per-model custom_providers cap is re-resolved against the new model
and the global is dropped (never leaks). Explicit constructor values survive.
"""

from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent

OR_URL = "https://openrouter.ai/api/v1"


def _make_agent(*, max_tokens, config_max_tokens, explicit=False):
    """Bare AIAgent exercising only switch_model's max_tokens re-resolution."""
    agent = AIAgent.__new__(AIAgent)
    agent.model = "primary-model"
    agent.provider = "openrouter"
    agent.base_url = OR_URL
    agent.api_key = "sk-primary"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True
    agent.context_compressor = None
    agent._config_context_length = None
    agent.max_tokens = max_tokens
    agent._config_max_tokens = config_max_tokens
    agent._max_tokens_explicit = explicit
    agent._primary_runtime = {}
    return agent


def _switch(agent, resolved):
    """Switch to 'new-model' with the per-model resolver pinned to `resolved`."""
    with (
        patch("hermes_cli.config.load_config", return_value={}),
        patch("hermes_cli.config.get_compatible_custom_providers", return_value=[]),
        patch("hermes_cli.config.get_custom_provider_max_tokens", return_value=resolved),
    ):
        agent.switch_model("new-model", "openrouter", api_key="sk-new", base_url=OR_URL)


def test_switch_reresolves_per_model_for_new_model():
    agent = _make_agent(max_tokens=8000, config_max_tokens=8000)
    _switch(agent, 131_072)
    assert agent.max_tokens == 131_072
    assert agent._config_max_tokens == 131_072


def test_switch_drops_global_so_it_does_not_leak():
    # Primary had a global cap (no per-model); the new model has none → no leak.
    agent = _make_agent(max_tokens=131_072, config_max_tokens=131_072)
    _switch(agent, None)
    assert agent.max_tokens is None
    assert agent._config_max_tokens is None


def test_explicit_max_tokens_survives_switch():
    agent = _make_agent(max_tokens=5000, config_max_tokens=None, explicit=True)
    _switch(agent, 131_072)  # resolver would return 131072, but is skipped
    assert agent.max_tokens == 5000


def test_failed_swap_rolls_back_max_tokens():
    agent = _make_agent(max_tokens=8000, config_max_tokens=8000)
    agent._create_openai_client = MagicMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        _switch(agent, 131_072)
    assert agent.max_tokens == 8000
    assert agent._config_max_tokens == 8000
