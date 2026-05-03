"""Tests for model.max_tokens config wiring (#19360).

OpenAI-compatible proxies that forward to Anthropic models require
``max_tokens`` whenever ``tools`` are present, so users must be able to set
the output cap from config.yaml.
"""

from unittest.mock import patch


def _build_agent(
    model_cfg,
    custom_providers=None,
    model="anthropic/claude-opus-4.6",
    constructor_max_tokens=None,
):
    cfg = {"model": model_cfg}
    if custom_providers is not None:
        cfg["custom_providers"] = custom_providers

    base_url = model_cfg.get("base_url", "")

    with (
        patch("hermes_cli.config.load_config", return_value=cfg),
        patch("agent.model_metadata.get_model_context_length", return_value=128_000),
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            model=model,
            api_key="test-key-1234567890",
            base_url=base_url,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_tokens=constructor_max_tokens,
        )
    return agent


def test_model_max_tokens_from_config():
    """model.max_tokens in config.yaml should be applied to self.max_tokens."""
    agent = _build_agent({
        "default": "claude-opus-4.6",
        "provider": "custom",
        "base_url": "http://proxy:8045/v1",
        "max_tokens": 4096,
    })
    assert agent.max_tokens == 4096
    assert agent._session_init_model_config["max_tokens"] == 4096


def test_model_max_tokens_string_numeric_works():
    """String '4096' should parse via int()."""
    agent = _build_agent({
        "default": "claude-opus-4.6",
        "provider": "custom",
        "base_url": "http://proxy:8045/v1",
        "max_tokens": "4096",
    })
    assert agent.max_tokens == 4096


def test_model_max_tokens_invalid_warns_and_ignored():
    """Invalid values should warn and leave max_tokens unset."""
    with patch("run_agent.logger") as mock_logger:
        agent = _build_agent({
            "default": "claude-opus-4.6",
            "provider": "custom",
            "base_url": "http://proxy:8045/v1",
            "max_tokens": "4K",
        })
    assert agent.max_tokens is None
    warning_calls = [c for c in mock_logger.warning.call_args_list
                     if "Invalid model.max_tokens" in str(c)]
    assert len(warning_calls) == 1


def test_model_max_tokens_zero_is_ignored():
    """A non-positive value isn't a useful cap; ignore it."""
    with patch("run_agent.logger") as mock_logger:
        agent = _build_agent({
            "default": "claude-opus-4.6",
            "provider": "custom",
            "base_url": "http://proxy:8045/v1",
            "max_tokens": 0,
        })
    assert agent.max_tokens is None
    warning_calls = [c for c in mock_logger.warning.call_args_list
                     if "Invalid model.max_tokens" in str(c)]
    assert len(warning_calls) == 1


def test_constructor_max_tokens_wins_over_config():
    """Explicit constructor argument should override config."""
    agent = _build_agent(
        {
            "default": "claude-opus-4.6",
            "provider": "custom",
            "base_url": "http://proxy:8045/v1",
            "max_tokens": 4096,
        },
        constructor_max_tokens=8192,
    )
    assert agent.max_tokens == 8192


def test_no_max_tokens_in_config_keeps_none():
    """Without config or constructor value, max_tokens stays None."""
    agent = _build_agent({
        "default": "claude-opus-4.6",
        "provider": "custom",
        "base_url": "http://proxy:8045/v1",
    })
    assert agent.max_tokens is None


def test_custom_providers_per_model_max_tokens():
    """custom_providers[i].models.<name>.max_tokens should apply."""
    custom_providers = [
        {
            "name": "AntigravityProxy",
            "base_url": "http://proxy:8045/v1",
            "models": {
                "claude-opus-4-6-thinking": {"max_tokens": 16384},
            },
        }
    ]
    agent = _build_agent(
        {
            "default": "claude-opus-4-6-thinking",
            "provider": "custom",
            "base_url": "http://proxy:8045/v1",
        },
        custom_providers=custom_providers,
        model="claude-opus-4-6-thinking",
    )
    assert agent.max_tokens == 16384


def test_top_level_model_max_tokens_wins_over_custom_providers():
    """Top-level model.max_tokens takes precedence over per-model entry."""
    custom_providers = [
        {
            "name": "AntigravityProxy",
            "base_url": "http://proxy:8045/v1",
            "models": {
                "claude-opus-4-6-thinking": {"max_tokens": 16384},
            },
        }
    ]
    agent = _build_agent(
        {
            "default": "claude-opus-4-6-thinking",
            "provider": "custom",
            "base_url": "http://proxy:8045/v1",
            "max_tokens": 4096,
        },
        custom_providers=custom_providers,
        model="claude-opus-4-6-thinking",
    )
    assert agent.max_tokens == 4096
