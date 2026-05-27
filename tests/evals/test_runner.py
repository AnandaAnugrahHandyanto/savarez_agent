from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from evals.runner import (
    _extract_session_metrics,
    build_result_from_components,
    run_eval_case,
    run_eval_suite,
)
from evals.schemas import (
    DeterministicAssertion,
    EvalCase,
    EvalRunResult,
    JudgeDimension,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(
    case_id: str = "test.simple",
    suite: str = "test",
    task_type: str = "analysis",
    title: str = "Simple test",
    prompt: str = "What is 2+2?",
    context: str | None = None,
    enabled_toolsets: list[str] | None = None,
    judge_dimensions: list[JudgeDimension] | None = None,
) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        suite=suite,
        task_type=task_type,  # type: ignore[arg-type]
        title=title,
        prompt=prompt,
        context=context,
        enabled_toolsets=enabled_toolsets or [],
        expected_tools=[],
        forbidden_tools=[],
        assertions=[],
        judge_dimensions=judge_dimensions or [],
    )


def _mock_agent(
    *,
    run_result: dict | None = None,
    session: dict | None = None,
    messages: list[dict] | None = None,
    model: str = "gpt-5.4",
    provider: str = "openai-codex",
    run_raises: Exception | None = None,
) -> MagicMock:
    agent = MagicMock()
    agent.model = model
    agent.provider = provider

    if run_raises:
        agent.run_conversation.side_effect = run_raises
    else:
        agent.run_conversation.return_value = run_result or {
            "final_response": "4",
            "completed": True,
            "api_calls": 1,
            "messages": [
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": "4"},
            ],
        }

    if session is not None or messages is not None:
        db = MagicMock()
        db.get_session.return_value = session or _default_session()
        db.get_messages.return_value = messages or _default_messages()
        agent._session_db = db
        agent.session_id = "sess_eval_test"
    else:
        agent._session_db = None
        agent.session_id = None

    return agent


def _default_session() -> dict:
    return {
        "input_tokens": 50,
        "output_tokens": 10,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "estimated_cost_usd": 0.001,
        "actual_cost_usd": 0.002,
    }


def _default_messages() -> list[dict]:
    return [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
    ]


def _tool_messages() -> list[dict]:
    return [
        {"role": "user", "content": "Search for X"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": "{}"},
                },
            ],
        },
        {"role": "tool", "content": "Results", "tool_name": "web_search"},
        {
            "role": "assistant",
            "content": "Here are the results",
            "tool_calls": [
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "web_extract", "arguments": "{}"},
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# run_eval_case — integration with mocked agent
# ---------------------------------------------------------------------------


class TestRunEvalCase:
    def test_successful_run_populates_all_fields(self):
        """A successful agent run yields a complete EvalRunResult."""
        case = _make_case()
        agent = _mock_agent()

        result = run_eval_case(case, injected_agent=agent)

        assert isinstance(result, EvalRunResult)
        assert result.case_id == "test.simple"
        assert result.suite == "test"
        assert result.final_response == "4"
        assert result.completed is True
        assert result.failed is False
        assert result.error is None
        assert ":Z" in result.started_at or "T" in result.started_at
        assert ":Z" in result.ended_at or "T" in result.ended_at
        assert result.elapsed_ms >= 0
        assert result.run_id.startswith("run_")
        assert result.model == "gpt-5.4"
        assert result.provider == "openai-codex"

    def test_captures_session_metrics(self):
        """Token/cost fields are populated from the agent's session DB."""
        case = _make_case()
        agent = _mock_agent(
            session=_default_session(),
            messages=_default_messages(),
        )

        result = run_eval_case(case, injected_agent=agent)

        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.cache_read_tokens == 0
        assert result.cache_write_tokens == 0
        assert result.estimated_cost_usd == 0.001
        assert result.actual_cost_usd == 0.002
        assert result.tool_calls == []

    def test_captures_tool_calls_from_messages(self):
        """Tool calls in assistant messages appear in the result."""
        case = _make_case()
        agent = _mock_agent(
            session=_default_session(),
            messages=_tool_messages(),
        )

        result = run_eval_case(case, injected_agent=agent)

        assert len(result.tool_calls) == 2
        names = {tc["name"] for tc in result.tool_calls}
        assert names == {"web_search", "web_extract"}

    def test_records_agent_failure(self):
        """When run_conversation raises, the result records the error."""
        case = _make_case()
        agent = _mock_agent(run_raises=RuntimeError("API timeout"))

        result = run_eval_case(case, injected_agent=agent)

        assert result.failed is True
        assert result.completed is False
        assert result.error is not None
        assert "RuntimeError" in result.error
        assert "API timeout" in result.error
        assert result.final_response == ""

    def test_records_incomplete_run_as_failed(self):
        """When completed=False, the run is failed but not an exception."""
        case = _make_case()
        agent = _mock_agent(
            run_result={
                "final_response": "partial answer",
                "completed": False,
            },
        )

        result = run_eval_case(case, injected_agent=agent)

        assert result.completed is False
        assert result.failed is True
        assert result.error is None
        assert result.final_response == "partial answer"

    def test_handles_missing_session_db_gracefully(self):
        """All metrics are None/empty when the agent has no session DB."""
        case = _make_case()
        agent = _mock_agent()
        agent._session_db = None
        agent.session_id = None

        result = run_eval_case(case, injected_agent=agent)

        assert result.input_tokens is None
        assert result.output_tokens is None
        assert result.estimated_cost_usd is None
        assert result.actual_cost_usd is None
        assert result.tool_calls == []

    def test_runs_optional_judge_and_combines_scores(self):
        case = _make_case(
            prompt="Review the summary",
            judge_dimensions=[
                JudgeDimension(
                    name="factuality",
                    description="Grounded in evidence",
                    pass_threshold=4,
                ),
                JudgeDimension(
                    name="specificity",
                    description="Specific instead of generic",
                    pass_threshold=4,
                ),
            ],
        )
        agent = _mock_agent(
            run_result={
                "final_response": "Strong answer with specifics.",
                "completed": True,
            }
        )

        def fake_judge(**_: object) -> str:
            return """
            {
              "scores": [
                {"dimension": "factuality", "score": 5, "passed": true, "rationale": "Grounded."},
                {"dimension": "specificity", "score": 4, "passed": true, "rationale": "Concrete."}
              ],
              "overall_pass": true,
              "summary": "Strong and specific review."
            }
            """

        result = run_eval_case(
            case,
            injected_agent=agent,
            judge_model="gpt-5.4-mini",
            judge_provider="openrouter",
            injected_judge=fake_judge,
        )

        assert len(result.judge_results) == 2
        assert result.judge_model == "gpt-5.4-mini"
        assert result.judge_provider == "openrouter"
        assert result.aggregate_scores["judge"] == 0.875
        assert result.aggregate_scores["efficiency"] == 1.0
        assert result.aggregate_scores["overall"] == 0.95

    def test_assertions_evaluated_on_final_response(self):
        """Deterministic assertions run against the final response."""
        case = EvalCase(
            case_id="test.assertions",
            suite="test",
            task_type="analysis",  # type: ignore[arg-type]
            title="Assertions test",
            prompt="Say 'hello world'",
            context=None,
            enabled_toolsets=[],
            expected_tools=[],
            forbidden_tools=[],
            assertions=[
                DeterministicAssertion(kind="non_empty_output"),
                DeterministicAssertion(
                    kind="contains_substring",
                    params={"substring": "hello"},
                ),
                DeterministicAssertion(
                    kind="forbidden_regex",
                    params={"pattern": "goodbye"},
                ),
            ],
            judge_dimensions=[],
        )
        agent = _mock_agent(
            run_result={
                "final_response": "hello world",
                "completed": True,
            },
            session=_default_session(),
            messages=_default_messages(),
        )

        result = run_eval_case(case, injected_agent=agent)

        assert len(result.assertions) == 3
        for ar in result.assertions:
            assert ar.passed is True
        assert result.aggregate_scores["deterministic"] == 1.0
        assert result.aggregate_scores["overall"] == 1.0

    def test_assertion_failures_reflected_in_score(self):
        """Failing assertions lower the deterministic score."""
        case = EvalCase(
            case_id="test.fail-assert",
            suite="test",
            task_type="analysis",  # type: ignore[arg-type]
            title="Fail assertions",
            prompt="Say 'goodbye'",
            context=None,
            enabled_toolsets=[],
            expected_tools=[],
            forbidden_tools=[],
            assertions=[
                DeterministicAssertion(
                    kind="contains_substring",
                    params={"substring": "hello"},
                    weight=1.0,
                ),
                DeterministicAssertion(
                    kind="max_lines",
                    params={"max_lines": 1},
                    weight=2.0,
                    required=True,
                ),
            ],
            judge_dimensions=[],
        )
        agent = _mock_agent(
            run_result={
                "final_response": "goodbye\nfriend\nhow are you",
                "completed": True,
            },
        )

        result = run_eval_case(case, injected_agent=agent)

        assert result.assertions[0].passed is False
        assert result.assertions[1].passed is False
        # Score = 0 earned / 3 total = 0.0
        assert result.aggregate_scores["deterministic"] == 0.0

    def test_evaluates_tool_assertions(self):
        """Tool assertions (tool_used, tool_not_used) work via session data."""
        case = EvalCase(
            case_id="test.tool-assert",
            suite="test",
            task_type="tooling",  # type: ignore[arg-type]
            title="Tool assertion test",
            prompt="Search for Hermes Agent",
            enabled_toolsets=["web"],
            expected_tools=[],
            forbidden_tools=[],
            assertions=[
                DeterministicAssertion(
                    kind="tool_used",
                    params={"tool": "web_search"},
                ),
                DeterministicAssertion(
                    kind="tool_not_used",
                    params={"tool": "terminal"},
                ),
            ],
            judge_dimensions=[],
        )
        agent = _mock_agent(
            run_result={
                "final_response": "Here are the results.",
                "completed": True,
            },
            session=_default_session(),
            messages=_tool_messages(),
        )

        result = run_eval_case(case, injected_agent=agent)

        assert result.assertions[0].passed is True  # web_search was used
        assert result.assertions[1].passed is True  # terminal was not used
        assert result.aggregate_scores["deterministic"] == 1.0


# ---------------------------------------------------------------------------
# run_eval_suite
# ---------------------------------------------------------------------------


class TestRunEvalSuite:
    def test_runs_multiple_cases_returns_ordered_results(self):
        cases = [
            _make_case(case_id="suite.first", prompt="First"),
            _make_case(case_id="suite.second", prompt="Second"),
        ]
        agents = [_mock_agent(), _mock_agent()]
        injected = iter(agents)

        # Monkey-patch run_eval_case to inject our agents
        def _patched(case, **kw):
            return run_eval_case(case, injected_agent=next(injected), **kw)

        import evals.runner as runner_mod

        original = runner_mod.run_eval_case
        runner_mod.run_eval_case = _patched
        try:
            results = run_eval_suite(cases, model="gpt-5.4")
        finally:
            runner_mod.run_eval_case = original

        assert len(results) == 2
        assert results[0].case_id == "suite.first"
        assert results[1].case_id == "suite.second"


# ---------------------------------------------------------------------------
# build_result_from_components — direct unit test
# ---------------------------------------------------------------------------


class TestBuildResultFromComponents:
    def test_builds_result_directly(self):
        case = _make_case()
        result = build_result_from_components(
            case,
            final_response="direct answer",
            completed=True,
            tool_calls=[{"name": "web_search"}],
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.01,
        )

        assert result.final_response == "direct answer"
        assert result.completed is True
        assert result.failed is False
        assert result.tool_calls == [{"name": "web_search"}]
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.estimated_cost_usd == 0.01

    def test_builds_failed_result(self):
        case = _make_case()
        result = build_result_from_components(
            case,
            final_response="",
            completed=False,
            failed=True,
            error="ValueError: bad input",
        )

        assert result.completed is False
        assert result.failed is True
        assert result.error == "ValueError: bad input"
        assert result.final_response == ""


# ---------------------------------------------------------------------------
# _extract_session_metrics — edge cases
# ---------------------------------------------------------------------------


class TestExtractSessionMetrics:
    def test_no_session_db_returns_defaults(self):
        agent = MagicMock()
        agent._session_db = None
        agent.session_id = None

        m = _extract_session_metrics(agent)
        assert m["tool_calls"] == []
        assert m["input_tokens"] is None

    def test_exception_during_extraction_is_handled(self):
        db = MagicMock()
        db.get_session.side_effect = RuntimeError("corrupt DB")
        agent = MagicMock()
        agent._session_db = db
        agent.session_id = "sess_bad"

        m = _extract_session_metrics(agent)
        # Should return defaults without propagating the exception
        assert m["tool_calls"] == []
        assert m["input_tokens"] is None

    def test_deduplicates_tool_call_names(self):
        """Same tool name used multiple times only appears once."""
        db = MagicMock()
        db.get_session.return_value = _default_session()
        db.get_messages.return_value = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": "{}"},
                    },
                ],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": "{}"},
                    },
                ],
            },
        ]
        agent = MagicMock()
        agent._session_db = db
        agent.session_id = "sess_dedup"

        m = _extract_session_metrics(agent)
        assert len(m["tool_calls"]) == 1
        assert m["tool_calls"][0]["name"] == "web_search"

    def test_handles_legacy_tool_call_format(self):
        """Some agents store tool_calls as list of {name, args} not {function: {name}}."""
        db = MagicMock()
        db.get_session.return_value = _default_session()
        db.get_messages.return_value = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"name": "web_search", "arguments": "{}"},
                ],
            },
        ]
        agent = MagicMock()
        agent._session_db = db
        agent.session_id = "sess_legacy"

        m = _extract_session_metrics(agent)
        assert len(m["tool_calls"]) == 1
        assert m["tool_calls"][0]["name"] == "web_search"