from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from .schemas import EvalRunResult

DEFAULT_RESULTS_DIR = Path("evals/results")


def results_to_json_bytes(results: Iterable[EvalRunResult]) -> bytes:
    ordered_results = _ordered_results(results)
    payload = {
        "summary": _build_summary(ordered_results),
        "results": [_result_to_dict(result) for result in ordered_results],
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_results_json(results: Iterable[EvalRunResult], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(results_to_json_bytes(results))
    return output_path


def render_markdown_report(results: Iterable[EvalRunResult]) -> str:
    ordered_results = _ordered_results(results)
    summary = _build_summary(ordered_results)
    lines = [
        "# Hermes eval report",
        "",
        "## Summary",
        f"- Total runs: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Completed: {summary['completed']}",
        f"- Suites: {summary['suites']}",
    ]

    if ordered_results:
        lines.extend(
            [
                f"- Mean overall score: {_mean_score(ordered_results, 'overall'):.3f}",
                f"- Mean deterministic score: {_mean_score(ordered_results, 'deterministic'):.3f}",
                "",
                "## Runs",
                "| Suite | Case ID | Status | Overall | Deterministic | Elapsed ms |",
                "| --- | --- | --- | ---: | ---: | ---: |",
            ]
        )
        for result in ordered_results:
            lines.append(
                "| {suite} | {case_id} | {status} | {overall:.3f} | {deterministic:.3f} | {elapsed_ms} |".format(
                    suite=result.suite,
                    case_id=result.case_id,
                    status="✅" if _is_pass(result) else "❌",
                    overall=result.aggregate_scores.get("overall", 0.0),
                    deterministic=result.aggregate_scores.get("deterministic", 0.0),
                    elapsed_ms=result.elapsed_ms,
                )
            )

        failed_results = [result for result in ordered_results if not _is_pass(result)]
        if failed_results:
            lines.extend(["", "## Failed runs"])
            for result in failed_results:
                reason = result.error or _failure_reason(result)
                lines.append(f"- `{result.case_id}` ({result.suite}) — {reason}")

    return "\n".join(lines) + "\n"


def write_markdown_report(results: Iterable[EvalRunResult], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(results), encoding="utf-8")
    return output_path


def _ordered_results(results: Iterable[EvalRunResult]) -> list[EvalRunResult]:
    return sorted(results, key=lambda result: (result.suite, result.case_id, result.run_id))


def _build_summary(results: list[EvalRunResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "completed": sum(1 for result in results if result.completed),
        "failed": sum(1 for result in results if result.failed),
        "passed": sum(1 for result in results if _is_pass(result)),
        "suites": len({result.suite for result in results}),
    }


def _result_to_dict(result: EvalRunResult) -> dict[str, Any]:
    return asdict(result)


def _is_pass(result: EvalRunResult) -> bool:
    if result.failed or not result.completed:
        return False
    if any(not assertion.passed for assertion in result.assertions):
        return False
    if any(not judge_result.passed for judge_result in result.judge_results):
        return False
    return True


def _failure_reason(result: EvalRunResult) -> str:
    failed_assertions = [assertion.kind for assertion in result.assertions if not assertion.passed]
    if failed_assertions:
        return f"failed assertions: {', '.join(failed_assertions)}"
    failed_dimensions = [judge.dimension for judge in result.judge_results if not judge.passed]
    if failed_dimensions:
        return f"failed judge dimensions: {', '.join(failed_dimensions)}"
    if not result.completed:
        return "run did not complete"
    return "run marked unsuccessful"


def _mean_score(results: list[EvalRunResult], name: str) -> float:
    values = [result.aggregate_scores[name] for result in results if name in result.aggregate_scores]
    if not values:
        return 0.0
    return mean(values)
