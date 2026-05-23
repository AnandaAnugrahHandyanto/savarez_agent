from hermes_cli.config import DEFAULT_CONFIG


def test_default_delegation_team_profiles_include_orchestrator_and_evaluator():
    agents = DEFAULT_CONFIG["delegation"]["agents"]

    assert {"orchestrator", "researcher", "evaluator"} <= set(agents)
    assert agents["orchestrator"]["role"] == "orchestrator"
    assert "agent_team" in agents["orchestrator"]["toolsets"]
    assert "agent_task_create" in agents["orchestrator"]["instructions"]

    evaluator = agents["evaluator"]
    assert evaluator["role"] == "leaf"
    assert evaluator["result_schema"]["passed"] == "boolean"
    assert evaluator["result_schema"]["summary"] == "string"
    assert evaluator["result_schema"]["findings"][0]["severity"] == "low|medium|high"
    assert evaluator["result_schema"]["risks"] == ["string"]
    assert evaluator["result_schema"]["tests"] == ["string"]


def test_default_agent_team_policy_points_to_evaluator_gate():
    policy = DEFAULT_CONFIG["agent_team"]["policy"]

    assert policy["default_orchestrator"] == "orchestrator"
    assert policy["default_evaluator"] == "evaluator"
    assert policy["evaluator_gate"] is True
    assert policy["poll_interval_seconds"] == 5
