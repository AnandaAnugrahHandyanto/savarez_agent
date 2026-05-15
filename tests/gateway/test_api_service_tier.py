"""Tests for direct OpenAI API service-tier routing in the gateway."""


def _make_runner(*, api_service_tier=None, api_service_tier_fallback=None, service_tier=None):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._api_service_tier = api_service_tier
    runner._api_service_tier_fallback = api_service_tier_fallback
    runner._service_tier = service_tier
    return runner


def _runtime(base_url="https://api.openai.com/v1", provider="custom", api_mode="codex_responses"):
    return {
        "api_key": "test",
        "base_url": base_url,
        "provider": provider,
        "api_mode": api_mode,
        "command": None,
        "args": [],
        "credential_pool": None,
    }


def test_gateway_direct_openai_api_flex_adds_service_tier_flex():
    runner = _make_runner(api_service_tier="flex", api_service_tier_fallback=None, service_tier=None)
    route = runner._resolve_turn_agent_config("hi", "gpt-5.5", _runtime())
    assert route["request_overrides"] == {"service_tier": "flex"}


def test_gateway_direct_openai_api_flex_can_fallback_to_standard():
    runner = _make_runner(api_service_tier="flex", api_service_tier_fallback="standard", service_tier=None)
    route = runner._resolve_turn_agent_config("hi", "gpt-5.5", _runtime())
    assert route["request_overrides"] == {
        "service_tier": "flex",
        "_fallback_request_overrides": {},
    }


def test_gateway_direct_openai_api_standard_does_not_inherit_fast():
    runner = _make_runner(api_service_tier=None, service_tier="priority")
    route = runner._resolve_turn_agent_config("hi", "gpt-5.4", _runtime())
    assert route["request_overrides"] == {}


def test_gateway_non_openai_api_keeps_existing_fast_service_tier_behavior():
    runner = _make_runner(api_service_tier="flex", api_service_tier_fallback="standard", service_tier="priority")
    route = runner._resolve_turn_agent_config(
        "hi",
        "gpt-5.4",
        _runtime(base_url="https://openrouter.ai/api/v1", provider="openrouter", api_mode="chat_completions"),
    )
    assert route["request_overrides"] == {"service_tier": "priority"}
