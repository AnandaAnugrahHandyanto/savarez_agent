from agent.smart_routing import build_route_notice, is_simple_turn, resolve_turn_route


def test_is_simple_turn_accepts_short_plain_question():
    config = {
        "enabled": True,
        "max_simple_chars": 500,
        "max_simple_words": 80,
    }
    assert is_simple_turn("what time is it in tokyo?", config) is True


def test_is_simple_turn_rejects_debugging_language():
    config = {
        "enabled": True,
        "max_simple_chars": 500,
        "max_simple_words": 80,
    }
    assert is_simple_turn("debug this failing test in my repo", config) is False


def test_is_simple_turn_rejects_technical_tooling_language():
    config = {
        "enabled": True,
        "max_simple_chars": 500,
        "max_simple_words": 80,
    }
    assert is_simple_turn("check this api config in json", config) is False


def test_resolve_turn_route_uses_default_when_disabled():
    runtime = {
        "api_key": "sk-primary",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "openrouter",
        "api_mode": "chat_completions",
        "command": None,
        "args": [],
        "credential_pool": object(),
    }
    model, routed_runtime = resolve_turn_route(
        "what time is it in tokyo?",
        "gpt-5",
        runtime,
        routing_config={"enabled": False},
    )
    assert model == "gpt-5"
    assert routed_runtime == runtime


def test_resolve_turn_route_switches_to_configured_cheap_model():
    runtime = {
        "api_key": "sk-primary",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "provider": "openai-codex",
        "api_mode": "codex_responses",
        "command": None,
        "args": [],
        "credential_pool": object(),
    }
    model, routed_runtime = resolve_turn_route(
        "what time is it in tokyo?",
        "gpt-5.4",
        runtime,
        routing_config={
            "enabled": True,
            "max_simple_chars": 500,
            "max_simple_words": 80,
            "cheap_model": {
                "provider": "custom",
                "model": "qwen_qwen3.5-9b",
                "base_url": "http://192.168.4.135:1234/v1",
            },
        },
    )
    assert model == "qwen_qwen3.5-9b"
    assert routed_runtime["provider"] == "custom"
    assert routed_runtime["base_url"] == "http://192.168.4.135:1234/v1"
    assert routed_runtime["api_key"] == ""
    assert routed_runtime["api_mode"] is None
    assert routed_runtime["credential_pool"] is None


def test_resolve_turn_route_keeps_primary_for_complex_prompt():
    runtime = {
        "api_key": "***",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "provider": "openai-codex",
        "api_mode": "codex_responses",
        "command": None,
        "args": [],
        "credential_pool": object(),
    }
    model, routed_runtime = resolve_turn_route(
        "debug this failing test in my repo",
        "gpt-5.4",
        runtime,
        routing_config={
            "enabled": True,
            "max_simple_chars": 500,
            "max_simple_words": 80,
            "cheap_model": {
                "provider": "custom",
                "model": "qwen_qwen3.5-9b",
                "base_url": "http://192.168.4.135:1234/v1",
            },
        },
    )
    assert model == "gpt-5.4"
    assert routed_runtime == runtime



def test_build_route_notice_reports_when_cheap_route_is_used():
    default_runtime = {
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "api_mode": "codex_responses",
        "command": None,
        "args": [],
    }
    routed_runtime = {
        "provider": "custom",
        "base_url": "http://192.168.4.135:1234/v1",
        "api_mode": None,
        "command": None,
        "args": [],
    }

    notice = build_route_notice(
        "gpt-5.4",
        default_runtime,
        "qwen_qwen3.5-9b",
        routed_runtime,
    )

    assert notice == "⚡ Smart routing: using qwen_qwen3.5-9b via custom for this turn."



def test_build_route_notice_returns_none_when_route_is_unchanged():
    default_runtime = {
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "api_mode": "codex_responses",
        "command": None,
        "args": [],
    }

    notice = build_route_notice(
        "gpt-5.4",
        default_runtime,
        "gpt-5.4",
        dict(default_runtime),
    )

    assert notice is None
