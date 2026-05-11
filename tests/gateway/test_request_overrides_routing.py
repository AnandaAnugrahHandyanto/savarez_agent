from gateway.run import GatewayRunner


def test_turn_route_keeps_request_overrides_out_of_runtime_kwargs():
    runner = object.__new__(GatewayRunner)
    runner._service_tier = None

    route = runner._resolve_turn_agent_config(
        "hello",
        "Qwen/Qwen3.6-27B-FP8",
        {
            "api_key": "test-key",
            "base_url": "https://example.test/v1",
            "provider": "llmos-qwen36",
            "api_mode": "chat_completions",
            "max_tokens": 8192,
            "request_overrides": {
                "temperature": 0,
                "extra_body": {"existing": True},
            },
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            },
        },
    )

    assert "request_overrides" not in route["runtime"]
    assert "extra_body" not in route["runtime"]
    assert route["runtime"]["max_tokens"] == 8192
    assert route["request_overrides"] == {
        "temperature": 0,
        "extra_body": {
            "existing": True,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    }

    # Mirrors the gateway constructor shape:
    # AIAgent(model=..., **route["runtime"], request_overrides=...)
    # If request_overrides leaks into runtime, Python raises TypeError here.
    def fake_agent(**kwargs):
        return kwargs

    kwargs = fake_agent(
        model=route["model"],
        **route["runtime"],
        request_overrides=route.get("request_overrides"),
    )
    assert kwargs["request_overrides"]["extra_body"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }
