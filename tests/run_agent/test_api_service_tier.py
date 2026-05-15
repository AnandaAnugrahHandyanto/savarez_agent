"""Transport and AIAgent checks for direct OpenAI API service-tier fallback."""


def test_codex_responses_transport_passes_service_tier_flex():
    from agent.transports.codex import ResponsesApiTransport

    transport = ResponsesApiTransport()
    kwargs = transport.build_kwargs(
        "gpt-5.5",
        [{"role": "user", "content": "hi"}],
        tools=[],
        request_overrides={"service_tier": "flex"},
        reasoning_config={"enabled": False},
    )
    assert kwargs["service_tier"] == "flex"


def test_codex_responses_transport_strips_private_fallback_override():
    from agent.transports.codex import ResponsesApiTransport

    transport = ResponsesApiTransport()
    kwargs = transport.build_kwargs(
        "gpt-5.5",
        [{"role": "user", "content": "hi"}],
        tools=[],
        request_overrides={"service_tier": "flex", "_fallback_request_overrides": {}},
        reasoning_config={"enabled": False},
    )
    assert kwargs["service_tier"] == "flex"
    assert "_fallback_request_overrides" not in kwargs


def test_chat_completions_profile_path_strips_private_fallback_override():
    from types import SimpleNamespace

    from agent.transports.chat_completions import ChatCompletionsTransport

    profile = SimpleNamespace(
        prepare_messages=lambda messages: messages,
        fixed_temperature=None,
        default_max_tokens=None,
        build_api_kwargs_extras=lambda **kwargs: ({}, {}),
        build_extra_body=lambda **kwargs: {},
    )
    transport = ChatCompletionsTransport()
    kwargs = transport._build_kwargs_from_profile(
        profile,
        "gpt-test",
        [{"role": "user", "content": "hi"}],
        tools=[],
        params={
            "request_overrides": {
                "service_tier": "flex",
                "_fallback_request_overrides": {},
                "extra_body": {"foo": "bar"},
            }
        },
    )
    assert kwargs["service_tier"] == "flex"
    assert kwargs["extra_body"] == {"foo": "bar"}
    assert "_fallback_request_overrides" not in kwargs


def test_agent_set_request_overrides_can_refresh_primary_runtime_snapshot():
    from run_agent import AIAgent

    agent = object.__new__(AIAgent)
    agent.request_overrides = {}
    agent._request_overrides_fallback = None
    agent._request_overrides_fallback_activated = False
    agent._primary_runtime = {}

    agent.set_request_overrides(
        {"service_tier": "flex", "_fallback_request_overrides": {}},
        update_primary_runtime=True,
    )

    assert agent._primary_runtime["request_overrides"] == {"service_tier": "flex"}
    assert agent._primary_runtime["request_overrides_fallback"] == {}


def test_agent_request_override_fallback_switches_to_standard():
    from run_agent import AIAgent

    agent = object.__new__(AIAgent)
    agent.request_overrides = {}
    agent._request_overrides_fallback = None
    agent._request_overrides_fallback_activated = False
    agent._emit_status = lambda message: None

    agent.set_request_overrides({"service_tier": "flex", "_fallback_request_overrides": {}})

    assert agent.request_overrides == {"service_tier": "flex"}
    assert agent._request_overrides_fallback == {}
    assert agent._try_activate_request_overrides_fallback()
    assert agent.request_overrides == {}
    assert not agent._try_activate_request_overrides_fallback()
