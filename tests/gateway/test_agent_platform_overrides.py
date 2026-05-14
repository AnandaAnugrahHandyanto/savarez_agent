"""Tests for per-platform gateway agent overrides."""

import gateway.run as gateway_run
from gateway.run import GatewayRunner, _effective_agent_config


def _sample_config():
    return {
        "agent": {
            "reasoning_effort": "xhigh",
            "max_turns": 90,
            "gateway_timeout": 1800,
            "gateway_timeout_warning": 900,
            "gateway_notify_interval": 180,
            "service_tier": "fast",
            "disabled_toolsets": ["browser"],
            "platforms": {
                "discord": {
                    "reasoning_effort": "low",
                    "max_turns": 24,
                    "gateway_timeout": 300,
                    "gateway_timeout_warning": 90,
                    "gateway_notify_interval": 60,
                    "service_tier": "normal",
                    "disabled_toolsets": ["browser", "image_gen"],
                }
            },
        }
    }


def test_effective_agent_config_applies_platform_overlay_only_for_matching_platform():
    cfg = _sample_config()

    discord = _effective_agent_config(cfg, "discord")
    cli = _effective_agent_config(cfg, "cli")

    assert discord["reasoning_effort"] == "low"
    assert discord["max_turns"] == 24
    assert discord["disabled_toolsets"] == ["browser", "image_gen"]
    assert cli["reasoning_effort"] == "xhigh"
    assert cli["max_turns"] == 90
    assert cli["disabled_toolsets"] == ["browser"]


def test_platform_overrides_control_reasoning_service_tier_budget_and_timeouts(monkeypatch):
    cfg = _sample_config()
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: cfg)

    assert GatewayRunner._load_reasoning_config("discord") == {
        "enabled": True,
        "effort": "low",
    }
    assert GatewayRunner._load_reasoning_config("cli") == {
        "enabled": True,
        "effort": "xhigh",
    }

    assert GatewayRunner._load_service_tier("discord") is None
    assert GatewayRunner._load_service_tier("cli") == "priority"

    assert GatewayRunner._load_max_iterations(cfg, "discord") == 24
    assert GatewayRunner._load_max_iterations(cfg, "cli") == 90

    assert GatewayRunner._load_agent_timeout_settings(cfg, "discord") == (
        300.0,
        90.0,
        60.0,
    )
    assert GatewayRunner._load_agent_timeout_settings(cfg, "cli") == (
        1800.0,
        900.0,
        180.0,
    )


def test_cache_busting_keys_use_effective_platform_agent_config():
    cfg = _sample_config()

    discord = GatewayRunner._extract_cache_busting_config(cfg, "discord")
    cli = GatewayRunner._extract_cache_busting_config(cfg, "cli")

    assert discord["agent.max_turns"] == 24
    assert discord["agent.disabled_toolsets"] == ["browser", "image_gen"]
    assert discord["agent.platform_key"] == "discord"
    assert cli["agent.max_turns"] == 90
    assert cli["agent.disabled_toolsets"] == ["browser"]
    assert cli["agent.platform_key"] == "cli"
