from __future__ import annotations

import pytest

from evals.judges import EvalJudgeError, aggregate_eval_scores, build_judge_prompt, evaluate_judge_output
from evals.schemas import EvalCase, JudgeDimension, JudgeResult


def _make_case(*, prompt: str = "Summarize the page", judge_dimensions: list[JudgeDimension]) -> EvalCase:
    return EvalCase(
        case_id="routing.case",
        suite="routing",
        task_type="routing",
        title="Routing case",
        prompt=prompt,
        context="Ground findings in the provided evidence.",
        tags=[],
        enabled_toolsets=[],
        expected_tools=[],
        forbidden_tools=[],
        assertions=[],
        judge_dimensions=judge_dimensions,
        gold_answer=None,
        notes=None,
    )


def test_build_judge_prompt_mentions_strict_json_contract_and_response():
    case = _make_case(
        judge_dimensions=[
            JudgeDimension(
                name="factuality",
                description="Grounded in evidence",
                pass_threshold=4,
            )
        ]
    )

    prompt = build_judge_prompt(case, final_response="A concise summary")

    assert "strict JSON" in prompt
    assert '"scores"' in prompt
    assert '"overall_pass"' in prompt
    assert '"summary"' in prompt
    assert "factuality" in prompt
    assert "A concise summary" in prompt


def test_evaluate_judge_output_parses_strict_json_normalizes_and_applies_thresholds():
    case = _make_case(
        judge_dimensions=[
            JudgeDimension(
                name="factuality",
                description="Grounded in evidence",
                pass_threshold=4,
            ),
            JudgeDimension(
                name="specificity",
                description="Specific instead of generic",
                pass_threshold=3,
            ),
        ]
    )

    results = evaluate_judge_output(
        case,
        """
        {
          "scores": [
            {"dimension": "factuality", "score": 5, "passed": true, "rationale": "Well grounded."},
            {"dimension": "specificity", "score": 2, "passed": false, "rationale": "Too generic."}
          ],
          "overall_pass": false,
          "summary": "Grounded but too generic overall."
        }
        """,
    )

    assert [result.dimension for result in results] == ["factuality", "specificity"]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].passed is True
    assert results[1].score == pytest.approx(0.25)
    assert results[1].passed is False


def test_evaluate_judge_output_rejects_non_json_framing():
    case = _make_case(
        judge_dimensions=[
            JudgeDimension(
                name="factuality",
                description="Grounded in evidence",
                pass_threshold=4,
            )
        ]
    )

    raw_output = 'Here is the JSON: {"scores": [], "overall_pass": true, "summary": "ok"}'

    with pytest.raises(EvalJudgeError, match="valid JSON"):
        evaluate_judge_output(case, raw_output)


def test_evaluate_judge_output_requires_exact_dimension_set():
    case = _make_case(
        judge_dimensions=[
            JudgeDimension(
                name="factuality",
                description="Grounded in evidence",
                pass_threshold=4,
            ),
            JudgeDimension(
                name="actionability",
                description="Ends with a concrete recommendation",
                pass_threshold=4,
            ),
        ]
    )

    raw_output = """
    {
      "scores": [
        {"dimension": "factuality", "score": 4, "passed": true, "rationale": "Grounded."}
      ],
      "overall_pass": true,
      "summary": "Missing one dimension."
    }
    """

    with pytest.raises(EvalJudgeError, match="actionability"):
        evaluate_judge_output(case, raw_output)


def test_aggregate_eval_scores_uses_plan_weights_when_judges_present():
    judge_results = [
        JudgeResult(dimension="factuality", score=1.0, passed=True, rationale="ok"),
        JudgeResult(dimension="specificity", score=0.5, passed=True, rationale="ok"),
    ]

    scores = aggregate_eval_scores(
        deterministic_score=0.8,
        judge_results=judge_results,
        efficiency_score=0.9,
    )

    assert scores == {
        "deterministic": 0.8,
        "judge": 0.75,
        "efficiency": 0.9,
        "overall": 0.79,
    }
