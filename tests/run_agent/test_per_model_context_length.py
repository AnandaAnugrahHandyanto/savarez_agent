"""Per-model context_length override resolution.

Tests the `model.models.<id>.context_length` config schema: a per-model
override that wins over the flat `model.context_length`. Motivating case:
on OpenRouter some providers serve a model with a smaller context window
than its native size — pinning providers fixes routing, and a per-model
context_length override pins the harness's expectations without mutating
the flat default that other models inherit.
"""

from unittest.mock import patch


def _build_agent(model_cfg, model="moonshotai/kimi-k2.6"):
    cfg = {"model": model_cfg}
    base_url = model_cfg.get("base_url", "")
    with (
        patch("hermes_cli.config.load_config", return_value=cfg),
        patch("agent.model_metadata.get_model_context_length", return_value=64_000),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent
        return AIAgent(
            model=model,
            api_key="test-key-1234567890",
            base_url=base_url,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )


def test_per_model_override_wins_over_flat():
    """model.models.<active>.context_length wins over flat model.context_length."""
    agent = _build_agent({
        "default": "moonshotai/kimi-k2.6",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "context_length": 64_000,  # flat default — what other models would get
        "models": {
            "moonshotai/kimi-k2.6": {"context_length": 256_000},
        },
    })
    assert agent._config_context_length == 256_000


def test_flat_wins_when_no_per_model_entry():
    """Active model with no per-model entry falls through to the flat default."""
    agent = _build_agent({
        "default": "anthropic/claude-opus-4.6",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "context_length": 64_000,
        "models": {
            "moonshotai/kimi-k2.6": {"context_length": 256_000},
        },
    }, model="anthropic/claude-opus-4.6")
    assert agent._config_context_length == 64_000


def test_per_model_override_with_no_flat():
    """Per-model override works even when flat context_length is unset."""
    agent = _build_agent({
        "default": "moonshotai/kimi-k2.6",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": {
            "moonshotai/kimi-k2.6": {"context_length": 256_000},
        },
    })
    assert agent._config_context_length == 256_000


def test_invalid_per_model_value_falls_back_to_flat():
    """An invalid per-model value warns and falls back to the flat default."""
    with patch("run_agent.logger") as mock_logger:
        agent = _build_agent({
            "default": "moonshotai/kimi-k2.6",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "context_length": 64_000,
            "models": {
                "moonshotai/kimi-k2.6": {"context_length": "256K"},
            },
        })
    assert agent._config_context_length == 64_000
    warning_calls = [
        c for c in mock_logger.warning.call_args_list
        if "Invalid model.models." in str(c) and "256K" in str(c)
    ]
    assert len(warning_calls) == 1


def test_missing_models_dict_is_noop():
    """No `models:` key at all — behaves identically to old config."""
    agent = _build_agent({
        "default": "moonshotai/kimi-k2.6",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "context_length": 64_000,
    })
    assert agent._config_context_length == 64_000


def test_string_integer_per_model_value():
    """Quoted integers should parse fine (YAML quirk: '256000' string)."""
    agent = _build_agent({
        "default": "moonshotai/kimi-k2.6",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "context_length": 64_000,
        "models": {
            "moonshotai/kimi-k2.6": {"context_length": "256000"},
        },
    })
    assert agent._config_context_length == 256_000
