from agent.smart_model_routing import (
    choose_cheap_model_route,
    choose_primary_agent_route,
)


_BASE_CONFIG = {
    "enabled": True,
    "cheap_model": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash",
    },
}

_PRIMARY = {
    "model": "anthropic/claude-sonnet-4",
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_mode": "chat_completions",
    "api_key": "***",
}


def test_returns_none_when_disabled():
    cfg = {**_BASE_CONFIG, "enabled": False}
    assert choose_cheap_model_route("what time is it in tokyo?", cfg) is None


def test_routes_short_simple_prompt():
    result = choose_cheap_model_route("what time is it in tokyo?", _BASE_CONFIG)
    assert result is not None
    assert result["provider"] == "openrouter"
    assert result["model"] == "google/gemini-2.5-flash"
    assert result["routing_reason"] == "simple_turn"


def test_skips_long_prompt():
    prompt = "please summarize this carefully " * 20
    assert choose_cheap_model_route(prompt, _BASE_CONFIG) is None


def test_skips_code_like_prompt():
    prompt = "debug this traceback: ```python\nraise ValueError('bad')\n```"
    assert choose_cheap_model_route(prompt, _BASE_CONFIG) is None


def test_skips_tool_heavy_prompt_keywords():
    prompt = "implement a patch for this docker error"
    assert choose_cheap_model_route(prompt, _BASE_CONFIG) is None


def test_primary_agent_route_requires_enabled_flag():
    cfg = {
        "enabled": False,
        "primary_agent": {"provider": "anthropic", "model": "claude-sonnet-4.6"},
    }
    assert choose_primary_agent_route(cfg) is None


def test_resolve_turn_route_uses_configured_primary_agent_when_prompt_is_complex(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    calls = []

    def _runtime_resolve(**kwargs):
        calls.append(kwargs)
        assert kwargs["requested"] == "anthropic"
        return {
            "provider": "anthropic",
            "api_mode": "anthropic_messages",
            "base_url": "https://api.anthropic.com",
            "api_key": "strong-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)

    result = resolve_turn_route(
        "implement a patch for this docker error",
        {
            **_BASE_CONFIG,
            "primary_agent": {
                "provider": "anthropic",
                "model": "claude-sonnet-4.6",
            },
        },
        _PRIMARY,
    )

    assert len(calls) == 1
    assert result["model"] == "claude-sonnet-4.6"
    assert result["runtime"]["provider"] == "anthropic"
    assert result["runtime"]["api_key"] == "strong-key"
    assert result["label"] == "smart route → primary claude-sonnet-4.6 (anthropic)"


def test_resolve_turn_route_falls_back_to_configured_primary_agent_when_cheap_runtime_cannot_be_resolved(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    calls = []

    def _runtime_resolve(**kwargs):
        calls.append(kwargs["requested"])
        if kwargs["requested"] == "openrouter":
            raise RuntimeError("cheap route unavailable")
        assert kwargs["requested"] == "anthropic"
        return {
            "provider": "anthropic",
            "api_mode": "anthropic_messages",
            "base_url": "https://api.anthropic.com",
            "api_key": "strong-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)

    result = resolve_turn_route(
        "what time is it in tokyo?",
        {
            **_BASE_CONFIG,
            "primary_agent": {
                "provider": "anthropic",
                "model": "claude-sonnet-4.6",
            },
        },
        _PRIMARY,
    )

    assert calls == ["openrouter", "anthropic"]
    assert result["model"] == "claude-sonnet-4.6"
    assert result["runtime"]["provider"] == "anthropic"
    assert result["label"] == "smart route → primary claude-sonnet-4.6 (anthropic)"


def test_resolve_turn_route_falls_back_to_primary_when_route_runtime_cannot_be_resolved(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad route")),
    )
    result = resolve_turn_route(
        "what time is it in tokyo?",
        _BASE_CONFIG,
        _PRIMARY,
    )
    assert result["model"] == "anthropic/claude-sonnet-4"
    assert result["runtime"]["provider"] == "openrouter"
    assert result["label"] is None
