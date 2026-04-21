from gateway.run import GatewayRunner


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner._service_tier = None
    return runner


def test_gateway_turn_routing_adds_user_visible_notice_when_cheap_route_applies(monkeypatch):
    monkeypatch.setattr("agent.smart_routing._load_smart_routing_config", lambda: {
        "enabled": True,
        "max_simple_chars": 500,
        "max_simple_words": 80,
        "cheap_model": {
            "provider": "custom",
            "model": "qwen_qwen3.5-9b",
            "base_url": "http://192.168.4.135:1234/v1",
        },
    })

    route = GatewayRunner._resolve_turn_agent_config(
        _make_runner(),
        "what time is it in tokyo?",
        "gpt-5.4",
        {
            "api_key": "sk-primary",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "command": None,
            "args": [],
            "credential_pool": None,
        },
    )

    assert route["model"] == "qwen_qwen3.5-9b"
    assert route["route_notice"] == "⚡ Smart routing: using qwen_qwen3.5-9b via custom for this turn."


def test_gateway_turn_routing_has_no_notice_when_route_is_unchanged(monkeypatch):
    monkeypatch.setattr("agent.smart_routing._load_smart_routing_config", lambda: {})

    route = GatewayRunner._resolve_turn_agent_config(
        _make_runner(),
        "what time is it in tokyo?",
        "gpt-5.4",
        {
            "api_key": "sk-primary",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "command": None,
            "args": [],
            "credential_pool": None,
        },
    )

    assert route["model"] == "gpt-5.4"
    assert route["route_notice"] is None
