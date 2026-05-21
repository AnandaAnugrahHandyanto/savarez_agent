from agent.swarm_router import route_request


def test_simple_explanatory_prompt_routes_direct():
    plan = route_request("Explain why the sky is blue")

    assert plan.mode == "direct"
    assert plan.permission_requests == []
    assert plan.verification_required is False


def test_multiple_independent_research_and_review_routes_swarm():
    plan = route_request("Research the API docs and review the code for security issues")

    assert plan.mode == "swarm"
    assert plan.suggested_tasks
    assert plan.verification_required is True


def test_more_than_three_procedural_steps_routes_script_candidate():
    plan = route_request("Collect the logs, then parse errors, validate counts, verify source of truth, and summarize")

    assert plan.mode == "script"
    assert plan.metadata["step_count"] > 3
    assert plan.verification_required is True


def test_external_send_deploy_destructive_wording_requires_permission():
    plan = route_request("Deploy the service and delete the old release")

    assert plan.permission_requests
    assert plan.metadata["permission_required"] is True
    assert plan.verification_required is True


def test_n8n_docker_wording_routes_pipe_with_permission_gate():
    plan = route_request("Run the n8n workflow in docker compose")

    assert plan.mode == "pipe"
    assert any(grant.permission_id == "perm_pipe_execution" for grant in plan.permission_requests)
    assert plan.verification_required is True
