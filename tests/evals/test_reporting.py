import json

from evals.reporting import render_markdown_report, results_to_json_bytes, write_markdown_report, write_results_json
from evals.schemas import AssertionResult, EvalRunResult, JudgeResult


def _make_result(
    *,
    run_id: str,
    suite: str,
    case_id: str,
    completed: bool = True,
    failed: bool = False,
    error: str | None = None,
    overall: float = 1.0,
    deterministic: float = 1.0,
) -> EvalRunResult:
    return EvalRunResult(
        run_id=run_id,
        case_id=case_id,
        suite=suite,
        provider="openai",
        model="gpt-5.4",
        judge_provider=None,
        judge_model=None,
        started_at="2026-05-26T12:00:00Z",
        ended_at="2026-05-26T12:00:01Z",
        elapsed_ms=1000,
        completed=completed,
        failed=failed,
        error=error,
        final_response="Decision-ready answer.",
        tool_calls=[{"name": "browser_navigate"}],
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        estimated_cost_usd=0.01,
        actual_cost_usd=0.02,
        assertions=[
            AssertionResult(kind="max_lines", passed=not failed, score=deterministic, details={"max_lines": 10})
        ],
        judge_results=[
            JudgeResult(
                dimension="factuality",
                score=4.0 if not failed else 2.0,
                passed=not failed,
                rationale="Grounded in evidence." if not failed else "Missing evidence.",
            )
        ],
        aggregate_scores={"deterministic": deterministic, "overall": overall},
        labels={"channel": "ci"},
    )


class TestResultsJson:
    def test_results_to_json_bytes_is_stable_and_sorted(self):
        later = _make_result(run_id="run-2", suite="zeta", case_id="zeta.case")
        earlier = _make_result(run_id="run-1", suite="alpha", case_id="alpha.case")

        payload = results_to_json_bytes([later, earlier]).decode("utf-8")
        parsed = json.loads(payload)

        assert [item["case_id"] for item in parsed["results"]] == ["alpha.case", "zeta.case"]
        assert parsed["summary"] == {
            "total": 2,
            "completed": 2,
            "failed": 0,
            "passed": 2,
            "suites": 2,
        }
        assert payload.endswith("\n")
        assert payload == results_to_json_bytes([later, earlier]).decode("utf-8")

    def test_write_results_json_writes_parent_directories(self, tmp_path):
        output_path = tmp_path / "nested" / "results.json"
        result = _make_result(run_id="run-1", suite="alpha", case_id="alpha.case")

        written = write_results_json([result], output_path)

        assert written == output_path
        assert output_path.exists()
        assert json.loads(output_path.read_text(encoding="utf-8"))["results"][0]["case_id"] == "alpha.case"


class TestMarkdownReporting:
    def test_render_markdown_report_summarizes_failures_and_scores(self):
        passing = _make_result(run_id="run-1", suite="alpha", case_id="alpha.case", overall=0.95)
        failing = _make_result(
            run_id="run-2",
            suite="beta",
            case_id="beta.case",
            failed=True,
            error="tool timeout",
            overall=0.25,
            deterministic=0.0,
        )

        report = render_markdown_report([failing, passing])

        assert report.startswith("# Hermes eval report\n")
        assert "- Total runs: 2" in report
        assert "- Passed: 1" in report
        assert "- Failed: 1" in report
        assert "## Failed runs" in report
        assert "beta.case" in report
        assert "tool timeout" in report
        assert "| alpha | alpha.case | ✅ | 0.950 | 1.000 | 1000 |" in report
        assert "| beta | beta.case | ❌ | 0.250 | 0.000 | 1000 |" in report

    def test_write_markdown_report_writes_parent_directories(self, tmp_path):
        output_path = tmp_path / "nested" / "summary.md"
        result = _make_result(run_id="run-1", suite="alpha", case_id="alpha.case")

        written = write_markdown_report([result], output_path)

        assert written == output_path
        assert output_path.read_text(encoding="utf-8").startswith("# Hermes eval report\n")
