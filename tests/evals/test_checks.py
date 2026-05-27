import pytest

from evals.checks import DeterministicScore, EvalCheckError, aggregate_assertion_scores, evaluate_assertion, evaluate_assertions
from evals.schemas import AssertionResult, DeterministicAssertion


def _assertion(kind: str, *, params: dict | None = None, weight: float = 1.0, required: bool = True) -> DeterministicAssertion:
    return DeterministicAssertion(kind=kind, params=params or {}, weight=weight, required=required)


class TestDeterministicChecks:
    def test_non_empty_output_rejects_blank_response(self):
        result = evaluate_assertion(_assertion("non_empty_output"), final_response="   \n", tool_calls=[])

        assert result.passed is False
        assert result.score == 0.0
        assert result.details["trimmed_chars"] == 0

    def test_max_chars_and_max_lines_use_observed_response_shape(self):
        response = "line one\nline two"

        chars = evaluate_assertion(_assertion("max_chars", params={"max_chars": len(response)}), final_response=response, tool_calls=[])
        lines = evaluate_assertion(_assertion("max_lines", params={"max_lines": 2}), final_response=response, tool_calls=[])
        lines_fail = evaluate_assertion(_assertion("max_lines", params={"max_lines": 1}), final_response=response, tool_calls=[])

        assert chars.passed is True
        assert chars.details["observed_chars"] == len(response)
        assert lines.passed is True
        assert lines.details["observed_lines"] == 2
        assert lines_fail.passed is False

    def test_required_and_forbidden_regex_checks(self):
        response = "Visible hero banner with 20% discount."

        required = evaluate_assertion(
            _assertion("required_regex", params={"pattern": r"\bdiscount\b"}),
            final_response=response,
            tool_calls=[],
        )
        forbidden = evaluate_assertion(
            _assertion("forbidden_regex", params={"pattern": r"\bfree money\b", "ignore_case": True}),
            final_response=response,
            tool_calls=[],
        )

        assert required.passed is True
        assert forbidden.passed is True

    def test_tool_used_and_tool_not_used_accept_multiple_trace_key_shapes(self):
        tool_calls = [
            {"name": "browser_navigate"},
            {"tool_name": "browser_vision"},
            {"tool": "web_extract"},
        ]

        used = evaluate_assertion(_assertion("tool_used", params={"tool": "browser_vision"}), final_response="ok", tool_calls=tool_calls)
        not_used = evaluate_assertion(_assertion("tool_not_used", params={"tool": "terminal"}), final_response="ok", tool_calls=tool_calls)
        used_fail = evaluate_assertion(_assertion("tool_used", params={"tool": "terminal"}), final_response="ok", tool_calls=tool_calls)

        assert used.passed is True
        assert sorted(used.details["used_tools"]) == ["browser_navigate", "browser_vision", "web_extract"]
        assert not_used.passed is True
        assert used_fail.passed is False

    def test_contains_url_detects_http_and_https(self):
        result = evaluate_assertion(
            _assertion("contains_url"),
            final_response="Source: https://example.com/report and http://backup.example.com.",
            tool_calls=[],
        )

        assert result.passed is True
        assert result.details["matched_url"] == "https://example.com/report"

    @pytest.mark.parametrize(
        ("response", "expected_match"),
        [
            ("Lorem ipsum placeholder copy", "Lorem ipsum"),
            ("TODO: replace this section", "TODO"),
            ("[insert screenshot summary]", "[insert screenshot summary]"),
            ("Use <company name> in the recommendation", "<company name>"),
            ("Write your answer here before sending", "your answer here"),
        ],
    )
    def test_no_placeholder_language_flags_common_placeholder_patterns(self, response: str, expected_match: str):
        result = evaluate_assertion(_assertion("no_placeholder_language"), final_response=response, tool_calls=[])

        assert result.passed is False
        assert result.details["matched_placeholder"] == expected_match

    def test_evaluate_assertions_runs_batch(self):
        assertions = [
            _assertion("non_empty_output"),
            _assertion("required_regex", params={"pattern": r"hero"}),
        ]

        results = evaluate_assertions(assertions, final_response="Visible hero banner", tool_calls=[])

        assert [result.kind for result in results] == ["non_empty_output", "required_regex"]
        assert all(result.passed for result in results)

    def test_unknown_assertion_kind_raises_clear_error(self):
        with pytest.raises(EvalCheckError, match=r"Unknown assertion kind"):
            evaluate_assertion(_assertion("language_is"), final_response="hello", tool_calls=[])


class TestDeterministicScoring:
    def test_weighted_scoring_uses_fractional_scores(self):
        assertions = [
            _assertion("non_empty_output", weight=1.0),
            _assertion("contains_url", weight=3.0, required=False),
        ]
        results = [
            AssertionResult(kind="non_empty_output", passed=True, score=1.0, details={}),
            AssertionResult(kind="contains_url", passed=False, score=0.0, details={}),
        ]

        score = aggregate_assertion_scores(assertions, results)

        assert isinstance(score, DeterministicScore)
        assert score.score == pytest.approx(0.25)
        assert score.earned_weight == pytest.approx(1.0)
        assert score.total_weight == pytest.approx(4.0)
        assert score.passed is True
        assert score.required_failures == []

    def test_required_failure_blocks_pass_even_when_optional_weight_score_is_high(self):
        assertions = [
            _assertion("required_regex", params={"pattern": r"required"}, weight=1.0, required=True),
            _assertion("contains_url", weight=5.0, required=False),
        ]
        results = [
            AssertionResult(kind="required_regex", passed=False, score=0.0, details={}),
            AssertionResult(kind="contains_url", passed=True, score=1.0, details={}),
        ]

        score = aggregate_assertion_scores(assertions, results)

        assert score.score == pytest.approx(5.0 / 6.0)
        assert score.passed is False
        assert score.required_failures == ["required_regex"]

    def test_zero_assertions_returns_full_score(self):
        score = aggregate_assertion_scores([], [])

        assert score.score == 1.0
        assert score.passed is True
        assert score.total_weight == 0.0
        assert score.earned_weight == 0.0

    def test_aggregate_scoring_rejects_mismatched_lengths(self):
        with pytest.raises(EvalCheckError, match=r"length mismatch"):
            aggregate_assertion_scores([_assertion("non_empty_output")], [])

    def test_aggregate_scoring_rejects_invalid_score_range(self):
        with pytest.raises(EvalCheckError, match=r"outside \[0, 1\]"):
            aggregate_assertion_scores(
                [_assertion("non_empty_output")],
                [AssertionResult(kind="non_empty_output", passed=True, score=1.5, details={})],
            )

    def test_aggregate_scoring_rejects_negative_weight(self):
        with pytest.raises(EvalCheckError, match=r"negative weight"):
            aggregate_assertion_scores(
                [_assertion("non_empty_output", weight=-1.0)],
                [AssertionResult(kind="non_empty_output", passed=True, score=1.0, details={})],
            )
