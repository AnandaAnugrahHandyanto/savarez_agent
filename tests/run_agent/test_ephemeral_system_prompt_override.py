from run_agent import AIAgent


def test_effective_system_prompt_uses_override_without_mutating_cached_prompt():
    agent = AIAgent.__new__(AIAgent)
    agent.ephemeral_system_prompt_override = "override"
    agent.ephemeral_system_prompt = "append"

    cached = "cached-base"
    effective = AIAgent._effective_system_prompt(agent, cached)

    assert effective == "override\n\nappend"
    assert cached == "cached-base"


def test_effective_system_prompt_falls_back_to_cached_prompt_when_no_override():
    agent = AIAgent.__new__(AIAgent)
    agent.ephemeral_system_prompt_override = None
    agent.ephemeral_system_prompt = "append"

    assert AIAgent._effective_system_prompt(agent, "cached-base") == "cached-base\n\nappend"
