from agent.smart_model_routing import choose_cheap_model_route


_BASE_CONFIG = {
    "enabled": True,
    "cheap_model": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash",
    },
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


def test_skips_prompt_when_newline_limit_exceeded():
    cfg = {**_BASE_CONFIG, "max_newlines": 0}
    assert choose_cheap_model_route("hello\nworld", cfg) is None


def test_skips_prompt_when_forbidden_pattern_matches():
    cfg = {**_BASE_CONFIG, "forbidden_patterns": [r"ticket-\d+"]}
    assert choose_cheap_model_route("check ticket-123 please", cfg) is None


def test_skips_prompt_when_custom_complex_keyword_matches():
    cfg = {**_BASE_CONFIG, "complex_keywords": ["invoice"]}
    assert choose_cheap_model_route("summarize this invoice", cfg) is None


def test_resolve_turn_route_falls_back_to_primary_when_route_runtime_cannot_be_resolved(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad route")),
    )
    result = resolve_turn_route(
        "what time is it in tokyo?",
        _BASE_CONFIG,
        {
            "model": "anthropic/claude-sonnet-4",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
            "api_key": "sk-primary",
        },
    )
    assert result["model"] == "anthropic/claude-sonnet-4"
    assert result["runtime"]["provider"] == "openrouter"
    assert result["label"] is None


def test_resolve_turn_route_label_shows_primary_and_routed_model(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: {
            "provider": "zai",
            "api_mode": "chat_completions",
            "base_url": "https://open.z.ai/api/v1",
            "api_key": "cheap-key",
        },
    )
    result = resolve_turn_route(
        "what time is it in tokyo?",
        _BASE_CONFIG,
        {
            "model": "anthropic/claude-sonnet-4",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
            "api_key": "sk-primary",
        },
    )
    assert result["label"] == "smart route: anthropic/claude-sonnet-4 (openrouter) -> google/gemini-2.5-flash (zai)"


def test_resolve_turn_route_uses_expensive_model_for_complex_turn(monkeypatch):
    from agent.smart_model_routing import resolve_turn_route

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        lambda **kwargs: {
            "provider": kwargs["requested"],
            "api_mode": "chat_completions",
            "base_url": None,
            "api_key": "key",
        },
    )
    result = resolve_turn_route(
        "debug this traceback",
        {
            "enabled": True,
            "cheap_model": {"provider": "openai-codex", "model": "gpt-5.4-mini"},
            "expensive_model": {"provider": "openai-codex", "model": "gpt-5.4"},
        },
        {
            "model": "claude-sonnet-4-6",
            "provider": "anthropic",
            "base_url": None,
            "api_mode": "anthropic_messages",
            "api_key": "sk-primary",
        },
    )
    assert result["model"] == "gpt-5.4"
    assert result["runtime"]["provider"] == "openai-codex"
