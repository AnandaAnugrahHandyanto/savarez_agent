from types import SimpleNamespace

from run_agent import AIAgent


def _tool_call(name="terminal", arguments="{}", tool_id="tc"):
    return SimpleNamespace(
        id=tool_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _agent(max_calls=2, repeat_threshold=3):
    agent = AIAgent.__new__(AIAgent)
    agent.max_tool_calls_per_turn = max_calls
    agent.repeat_tool_threshold = repeat_threshold
    agent._turn_tool_call_count = 0
    agent._turn_repeat_tool_warnings = 0
    agent._turn_budget_hit = False
    agent._turn_recent_tool_call_signatures = []
    agent._turn_repeat_tool_warning_active = False
    return agent


def test_reserve_tool_calls_enforces_per_turn_limit():
    agent = _agent(max_calls=2)

    allowed, skipped, warnings = agent._reserve_tool_calls_for_turn([
        _tool_call(tool_id="1"),
        _tool_call(tool_id="2"),
        _tool_call(tool_id="3"),
    ])

    assert [tc.id for tc in allowed] == ["1", "2"]
    assert [tc.id for tc in skipped] == ["3"]
    assert agent._turn_tool_call_count == 3
    assert agent._turn_budget_hit is True
    assert len(warnings) == 1


def test_repeat_warning_resets_when_tool_signature_changes():
    agent = _agent(max_calls=10, repeat_threshold=3)

    _, _, first_warnings = agent._reserve_tool_calls_for_turn([
        _tool_call("terminal", "{}", "1"),
        _tool_call("terminal", "{}", "2"),
        _tool_call("terminal", "{}", "3"),
    ])
    _, _, second_warnings = agent._reserve_tool_calls_for_turn([
        _tool_call("read_file", '{"path":"a"}', "4"),
        _tool_call("terminal", "{}", "5"),
        _tool_call("terminal", "{}", "6"),
        _tool_call("terminal", "{}", "7"),
    ])

    assert len(first_warnings) == 1
    assert len(second_warnings) == 1
    assert agent._turn_repeat_tool_warnings == 2
