from agent.smart_model_routing import choose_cheap_model_route


ROUTING_CFG = {
    "enabled": True,
    "max_simple_chars": 160,
    "max_simple_words": 28,
    "cheap_model": {
        "provider": "openai-codex",
        "model": "gpt-5.4-mini",
    },
}


def test_choose_cheap_model_route_for_simple_home_command():
    route = choose_cheap_model_route("turn off the lights", ROUTING_CFG)
    assert route is not None
    assert route["provider"] == "openai-codex"
    assert route["model"] == "gpt-5.4-mini"
    assert route["routing_reason"] == "simple_turn"


def test_choose_cheap_model_route_rejects_short_but_judgment_call():
    route = choose_cheap_model_route("Should I text Mackenzie now?", ROUTING_CFG)
    assert route is None


def test_choose_cheap_model_route_rejects_short_interpretive_question():
    route = choose_cheap_model_route("Why is Nora clingy lately?", ROUTING_CFG)
    assert route is None
