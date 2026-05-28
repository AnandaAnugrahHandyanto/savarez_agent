"""Tests for ``platform_request_overrides`` config-driven per-platform
``request_overrides`` layering.

Mirrors the structure of :mod:`tests.agent.test_custom_provider_extra_body`
since the two layers compose: ``custom_providers[].extra_body`` resolves
first, then per-platform overrides layer in for keys the caller did not
pass explicitly.
"""
from types import SimpleNamespace

from agent.agent_init import (
    _merge_platform_request_overrides,
    _platform_request_overrides_for_agent,
)


def _agent(platform="api_server", request_overrides=None):
    return SimpleNamespace(
        platform=platform,
        request_overrides=dict(request_overrides or {}),
    )


# ──────────────────────────────────────────────────────────────────────
# _platform_request_overrides_for_agent
# ──────────────────────────────────────────────────────────────────────


def test_resolver_returns_none_for_missing_block():
    assert _platform_request_overrides_for_agent(
        platform="api_server",
        config={},
    ) is None


def test_resolver_returns_none_for_unknown_platform():
    cfg = {
        "platform_request_overrides": {
            "telegram": {"extra_body": {"reasoning_effort": "high"}},
        }
    }
    assert _platform_request_overrides_for_agent(
        platform="api_server",
        config=cfg,
    ) is None


def test_resolver_returns_none_when_platform_empty():
    cfg = {"platform_request_overrides": {"api_server": {"reasoning_effort": "low"}}}
    assert _platform_request_overrides_for_agent(platform="", config=cfg) is None
    assert _platform_request_overrides_for_agent(platform=None, config=cfg) is None


def test_resolver_case_insensitive_platform_key():
    cfg = {
        "platform_request_overrides": {
            "api_server": {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        }
    }
    result = _platform_request_overrides_for_agent(
        platform="API_Server",
        config=cfg,
    )
    assert result == {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


def test_resolver_returns_copy_not_reference():
    """The resolver must hand back a copy so a caller mutating its result
    can't corrupt the parsed config dict shared with other agents."""
    cfg = {
        "platform_request_overrides": {
            "api_server": {"reasoning_effort": "minimal"},
        }
    }
    result = _platform_request_overrides_for_agent(platform="api_server", config=cfg)
    assert result == {"reasoning_effort": "minimal"}
    result["reasoning_effort"] = "high"
    assert cfg["platform_request_overrides"]["api_server"]["reasoning_effort"] == "minimal"


def test_resolver_tolerates_non_dict_config():
    assert _platform_request_overrides_for_agent(platform="cli", config=None) is None
    assert _platform_request_overrides_for_agent(platform="cli", config=[]) is None


def test_resolver_tolerates_non_dict_section():
    cfg = {"platform_request_overrides": ["api_server"]}
    assert _platform_request_overrides_for_agent(platform="api_server", config=cfg) is None


def test_resolver_tolerates_non_dict_entry():
    cfg = {"platform_request_overrides": {"api_server": "no thinking"}}
    assert _platform_request_overrides_for_agent(platform="api_server", config=cfg) is None


def test_resolver_treats_empty_dict_entry_as_none():
    cfg = {"platform_request_overrides": {"api_server": {}}}
    assert _platform_request_overrides_for_agent(platform="api_server", config=cfg) is None


# ──────────────────────────────────────────────────────────────────────
# _merge_platform_request_overrides
# ──────────────────────────────────────────────────────────────────────


def test_merge_noop_when_no_block():
    agent = _agent()
    _merge_platform_request_overrides(agent, config={}, caller_overrides=None)
    assert agent.request_overrides == {}


def test_merge_noop_when_platform_unmatched():
    agent = _agent(platform="cli")
    cfg = {
        "platform_request_overrides": {
            "api_server": {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    assert agent.request_overrides == {}


def test_merge_writes_extra_body_for_matching_platform():
    agent = _agent(platform="api_server")
    cfg = {
        "platform_request_overrides": {
            "api_server": {
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": False},
                }
            }
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    assert agent.request_overrides == {
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}
    }


def test_merge_top_level_keys_pass_through():
    agent = _agent(platform="api_server")
    cfg = {
        "platform_request_overrides": {
            "api_server": {"service_tier": "priority", "reasoning_effort": "minimal"}
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    assert agent.request_overrides == {
        "service_tier": "priority",
        "reasoning_effort": "minimal",
    }


def test_merge_layers_on_top_of_custom_provider_extra_body():
    """When a custom_provider has already populated ``extra_body``, the
    platform layer should overlay its own extra_body keys without
    erasing siblings.
    """
    agent = _agent(
        platform="api_server",
        request_overrides={"extra_body": {"reasoning_effort": "high"}},
    )
    cfg = {
        "platform_request_overrides": {
            "api_server": {
                "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}
            }
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    assert agent.request_overrides == {
        "extra_body": {
            "reasoning_effort": "high",
            "chat_template_kwargs": {"enable_thinking": False},
        }
    }


def test_merge_respects_caller_extra_body_keys():
    """The caller may explicitly set ``extra_body.enable_thinking``; the
    platform layer must not overwrite it."""
    caller = {"extra_body": {"enable_thinking": True}}
    agent = _agent(
        platform="api_server",
        request_overrides=caller,
    )
    cfg = {
        "platform_request_overrides": {
            "api_server": {"extra_body": {"enable_thinking": False, "reasoning_effort": "low"}}
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=caller)
    assert agent.request_overrides == {
        "extra_body": {
            "enable_thinking": True,         # caller wins
            "reasoning_effort": "low",        # platform fills the gap
        }
    }


def test_merge_respects_caller_top_level_keys():
    caller = {"service_tier": "default"}
    agent = _agent(
        platform="api_server",
        request_overrides=caller,
    )
    cfg = {
        "platform_request_overrides": {
            "api_server": {
                "service_tier": "priority",
                "reasoning_effort": "minimal",
            }
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=caller)
    assert agent.request_overrides == {
        "service_tier": "default",           # caller wins
        "reasoning_effort": "minimal",       # platform fills the gap
    }


def test_merge_ignores_unparseable_extra_body():
    agent = _agent(platform="api_server")
    cfg = {
        "platform_request_overrides": {
            "api_server": {"extra_body": "should be a dict", "reasoning_effort": "low"}
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    # Bad extra_body shape is silently dropped; valid top-level keys still apply.
    assert agent.request_overrides == {"reasoning_effort": "low"}


def test_merge_does_not_create_empty_extra_body():
    agent = _agent(platform="api_server")
    cfg = {
        "platform_request_overrides": {
            "api_server": {"extra_body": {}, "reasoning_effort": "minimal"}
        }
    }
    _merge_platform_request_overrides(agent, config=cfg, caller_overrides=None)
    assert "extra_body" not in agent.request_overrides
    assert agent.request_overrides["reasoning_effort"] == "minimal"
