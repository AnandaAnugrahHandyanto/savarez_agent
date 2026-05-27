from __future__ import annotations

import json
from pathlib import Path

from evals.baselines import BaselineSnapshot, CaseScore, compare_baselines
from evals.schemas import AssertionResult, EvalRunResult
from scripts import run_evals


def _make_case(*, suite: str = "alpha", case_id: str = "alpha.case", title: str = "Alpha case"):
    class Case:
        def __init__(self):
            self.suite = suite
            self.case_id = case_id
            self.title = title

    return Case()


def _make_result(
    *,
    suite: str = "alpha",
    case_id: str = "alpha.case",
    completed: bool = True,
    failed: bool = False,
    assertion_passed: bool = True,
) -> EvalRunResult:
    return EvalRunResult(
        run_id="run_20260526_abcdef",
        case_id=case_id,
        suite=suite,
        provider="openai-codex",
        model="gpt-5.4",
        judge_provider=None,
        judge_model=None,
        started_at="2026-05-26T12:00:00Z",
        ended_at="2026-05-26T12:00:01Z",
        elapsed_ms=1000,
        completed=completed,
        failed=failed,
        error=None,
        final_response="answer",
        tool_calls=[],
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        estimated_cost_usd=0.001,
        actual_cost_usd=0.001,
        assertions=[
            AssertionResult(
                kind="contains_substring",
                passed=assertion_passed,
                score=1.0 if assertion_passed else 0.0,
                details={},
            )
        ],
        judge_results=[],
        aggregate_scores={
            "deterministic": 1.0 if assertion_passed else 0.0,
            "overall": 1.0 if assertion_passed else 0.0,
        },
        labels={},
    )


def test_main_fail_under_counts_assertion_failures_as_not_passed(tmp_path, monkeypatch):
    monkeypatch.setattr("evals.loader.load_eval_cases", lambda *args, **kwargs: [_make_case()])
    monkeypatch.setattr(
        "evals.runner.run_eval_suite",
        lambda *args, **kwargs: [_make_result(assertion_passed=False)],
    )
    monkeypatch.setattr("evals.reporting.write_results_json", lambda results, path: Path(path))
    monkeypatch.setattr("evals.reporting.write_markdown_report", lambda results, path: Path(path))

    exit_code = run_evals.main(
        ["--suite", "alpha", "--fail-under", "1.0", "--output", str(tmp_path)]
    )

    assert exit_code == 1


def test_compare_baselines_fail_under_updates_recommendation_and_summary_together():
    baseline = BaselineSnapshot(
        suite="briefing",
        git_sha="abc123",
        config_fingerprint="cfg-1",
        run_date="2026-05-26T12:00:00Z",
        model="gpt-5.4",
        provider="openai-codex",
        total_cases=1,
        passed_cases=1,
        pass_rate=1.0,
        median_latency_ms=500,
        median_cost_usd=0.001,
        per_case=[
            CaseScore(
                case_id="briefing.stable",
                suite="briefing",
                score=0.9,
                deterministic=1.0,
                passed=True,
                failed=False,
                elapsed_ms=500,
                estimated_cost_usd=0.001,
                actual_cost_usd=0.001,
            )
        ],
    )
    candidate = BaselineSnapshot(
        suite="briefing",
        git_sha="def456",
        config_fingerprint="cfg-2",
        run_date="2026-05-26T13:00:00Z",
        model="gpt-5.4",
        provider="openai-codex",
        total_cases=1,
        passed_cases=0,
        pass_rate=0.0,
        median_latency_ms=480,
        median_cost_usd=0.001,
        per_case=[
            CaseScore(
                case_id="briefing.stable",
                suite="briefing",
                score=0.9,
                deterministic=1.0,
                passed=False,
                failed=False,
                elapsed_ms=480,
                estimated_cost_usd=0.001,
                actual_cost_usd=0.001,
            )
        ],
    )

    comparison = compare_baselines(baseline, candidate, fail_under=0.5)

    assert comparison.recommendation == "no_ship"
    assert comparison.summary.startswith("Recommendation: no_ship")
    assert any("below --fail-under 50.0%" in guardrail for guardrail in comparison.guardrails)


def test_main_passes_judge_flags_to_run_eval_suite(tmp_path, monkeypatch):
    seen: dict[str, object] = {}

    monkeypatch.setattr("evals.loader.load_eval_cases", lambda *args, **kwargs: [_make_case()])

    def fake_run_eval_suite(*args, **kwargs):
        seen.update(kwargs)
        return [_make_result()]

    monkeypatch.setattr("evals.runner.run_eval_suite", fake_run_eval_suite)
    monkeypatch.setattr("evals.reporting.write_results_json", lambda results, path: Path(path))
    monkeypatch.setattr("evals.reporting.write_markdown_report", lambda results, path: Path(path))

    exit_code = run_evals.main(
        [
            "--suite",
            "alpha",
            "--judge-model",
            "gpt-5.4",
            "--judge-provider",
            "openrouter",
            "--output",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert seen["judge_model"] == "gpt-5.4"
    assert seen["judge_provider"] == "openrouter"


def test_main_uses_fixture_results_for_offline_smoke(tmp_path):
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    (cases_root / "alpha.yaml").write_text(
        """
case_id: alpha.case
suite: alpha
task_type: routing
title: Alpha case
prompt: Say Alpha.
assertions:
  - kind: non_empty_output
    required: true
  - kind: contains_substring
    params: {substring: Alpha, ignore_case: true}
    required: true
  - kind: tool_used
    params: {tool: search_files}
    required: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    fixture_path = tmp_path / "fixture.yaml"
    fixture_path.write_text(
        """
defaults:
  provider: fixture-ci
  model: fixture-smoke
cases:
  alpha.case:
    final_response: Alpha answer from fixture mode.
    tool_calls:
      - search_files
""".strip()
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    exit_code = run_evals.main(
        [
            "--case",
            "alpha.case",
            "--cases-root",
            str(cases_root),
            "--fixture-results",
            str(fixture_path),
            "--fail-under",
            "1.0",
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    payload = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 1
    result = payload["results"][0]
    assert result["provider"] == "fixture-ci"
    assert result["model"] == "fixture-smoke"
    assert result["tool_calls"] == [{"name": "search_files"}]
    assert result["final_response"] == "Alpha answer from fixture mode."


def test_main_fixture_results_require_all_requested_cases(tmp_path):
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    (cases_root / "alpha.yaml").write_text(
        """
case_id: alpha.case
suite: alpha
task_type: routing
title: Alpha case
prompt: Say Alpha.
assertions:
  - kind: non_empty_output
    required: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    fixture_path = tmp_path / "fixture.yaml"
    fixture_path.write_text(
        "cases: {}\n",
        encoding="utf-8",
    )

    exit_code = run_evals.main(
        [
            "--case",
            "alpha.case",
            "--cases-root",
            str(cases_root),
            "--fixture-results",
            str(fixture_path),
            "--output",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 1
