import json

from run_agent import AIAgent


def _make_agent():
    agent = AIAgent(
        provider='custom',
        api_key='test-key',
        base_url='https://example.com/v1',
        model='gpt-5.4-mini',
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    agent.valid_tool_names = {'skills_list', 'skill_view', 'session_search'}
    return agent


def test_repair_repeated_tool_names():
    agent = _make_agent()
    try:
        assert agent._repair_tool_call('skills_listskills_list') == 'skills_list'
        assert agent._repair_tool_call('skill_viewskill_view') == 'skill_view'
        assert agent._repair_tool_call('session_searchsession_search') == 'session_search'
        assert agent._repair_tool_call('skills_list skills_list') == 'skills_list'
    finally:
        agent.client.close()


def test_repair_duplicated_json_args_exact_repeats():
    agent = _make_agent()
    try:
        repaired = agent._repair_duplicated_json_args('{"category":"research"}{"category":"research"}')
        assert json.loads(repaired) == {"category": "research"}

        repaired = agent._repair_duplicated_json_args('{"a":1}{"a":1}{"a":1}')
        assert json.loads(repaired) == {"a": 1}
    finally:
        agent.client.close()


def test_repair_duplicated_json_args_rejects_mismatch():
    agent = _make_agent()
    try:
        assert agent._repair_duplicated_json_args('{"a":1}{"a":2}') is None
        assert agent._repair_duplicated_json_args('{"a":1}') is None
    finally:
        agent.client.close()
