#!/usr/bin/env python3
"""Hermes eval runner — CLI entrypoint for suite/case execution.

Usage examples::

    # Run a full suite
    python scripts/run_evals.py --suite ci-briefings

    # Run with a specific model
    python scripts/run_evals.py --suite analysis --model gpt-5.4

    # Run a specific case
    python scripts/run_evals.py --case routing.browser-vs-webextract --output evals/results/manual/

    # Run with judge model
    python scripts/run_evals.py --suite review --model gpt-5.5 --judge-model gpt-5.5

    # Run with baseline comparison
    python scripts/run_evals.py --suite ci-briefings --baseline evals/results/baseline.ci-briefings.json

    # Save baseline after running
    python scripts/run_evals.py --suite ci-briefings --save-baseline evals/results/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TYPE_CHECKING = False

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("run_evals")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Hermes eval suites/cases.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target selection
    target = parser.add_argument_group("target selection")
    target.add_argument(
        "--suite",
        action="append",
        default=[],
        dest="suites",
        help="Suite filter (repeatable, e.g. --suite ci-briefings --suite analysis). "
        "When omitted, all suites are included.",
    )
    target.add_argument(
        "--case",
        action="append",
        default=[],
        dest="case_ids",
        help="Specific case IDs (repeatable). When set, only these cases run.",
    )
    target.add_argument(
        "--max-cases",
        type=int,
        default=0,
        metavar="N",
        help="Limit number of cases run (default: no limit).",
    )

    # Model / provider
    model = parser.add_argument_group("model configuration")
    model.add_argument(
        "--model",
        default=None,
        help="Model name override (e.g. gpt-5.4, claude-sonnet-4).",
    )
    model.add_argument(
        "--provider",
        default=None,
        help="Provider override (e.g. openai-codex, anthropic, openrouter).",
    )
    model.add_argument(
        "--judge-model",
        default=None,
        help="Judge model for rubric-based scoring (requires evals/judges.py).",
    )
    model.add_argument(
        "--judge-provider",
        default=None,
        help="Provider for the judge model.",
    )

    # Output
    output = parser.add_argument_group("output")
    output.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="DIR",
        help="Output directory for results. Default: evals/results/<suite>/<timestamp>/",
    )
    output.add_argument(
        "--json",
        dest="json_only",
        action="store_true",
        default=False,
        help="Only output JSON (no markdown report).",
    )

    # Baseline
    baseline = parser.add_argument_group("baseline comparison")
    baseline.add_argument(
        "--baseline",
        default=None,
        metavar="PATH",
        help="Path to baseline snapshot JSON for comparison.",
    )
    baseline.add_argument(
        "--save-baseline",
        default=None,
        metavar="DIR",
        help="Directory to save baseline snapshot(s) after running.",
    )

    # Pass/fail gate
    gate = parser.add_argument_group("pass/fail gate")
    gate.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        metavar="SCORE",
        help="Minimum aggregate pass rate (0-1) required to pass. "
        "Exits with code 1 when the pass rate is below this threshold.",
    )
    gate.add_argument(
        "--fixture-results",
        default=None,
        metavar="PATH",
        help="Offline fixture payload (YAML or JSON) used to build canned eval results "
        "for CI-safe smoke runs without calling a live model.",
    )

    # Cases root
    parser.add_argument(
        "--cases-root",
        default="evals/cases",
        metavar="DIR",
        help="Root directory for case YAML files (default: evals/cases).",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # ---- Load cases --------------------------------------------------------
    from evals.loader import load_eval_cases

    logger.info(
        "Loading cases from %s (suites=%s, case_ids=%s)",
        args.cases_root,
        args.suites or "all",
        args.case_ids or "all",
    )

    try:
        cases = load_eval_cases(
            args.cases_root,
            suites=args.suites or None,
            case_ids=args.case_ids or None,
        )
    except Exception as exc:
        logger.error("Failed to load cases: %s", exc)
        return 1

    if not cases:
        logger.warning("No cases matched the given filters.")
        return 0

    if args.max_cases > 0 and len(cases) > args.max_cases:
        logger.info("Limiting to %d/%d cases", args.max_cases, len(cases))
        cases = cases[: args.max_cases]

    logger.info("Loaded %d case(s)", len(cases))
    for case in cases:
        logger.info("  [%s] %s — %s", case.suite, case.case_id, case.title)

    # ---- Run cases ---------------------------------------------------------
    if args.fixture_results:
        logger.info("Building %d canned fixture result(s) from %s", len(cases), args.fixture_results)
        try:
            results = _build_fixture_results(
                cases,
                fixture_path=args.fixture_results,
                model=args.model,
                provider=args.provider,
                judge_model=args.judge_model,
                judge_provider=args.judge_provider,
            )
        except Exception as exc:
            logger.error("Failed to build fixture results: %s", exc)
            return 1
    else:
        from evals.runner import run_eval_suite

        logger.info(
            "Running %d case(s) (model=%s, provider=%s)", len(cases), args.model, args.provider
        )

        results = run_eval_suite(
            cases,
            model=args.model,
            provider=args.provider,
            judge_model=args.judge_model,
            judge_provider=args.judge_provider,
        )

    # ---- Reporting helpers -------------------------------------------------
    from evals.reporting import _is_pass, write_markdown_report, write_results_json

    passed = sum(1 for r in results if _is_pass(r))
    failed = len(results) - passed
    logger.info("Results: %d passed, %d failed (of %d)", passed, failed, len(results))

    # ---- Write output ------------------------------------------------------

    output_dir = args.output
    if not output_dir:
        # Default: evals/results/<first_suite>/<timestamp>/
        from datetime import datetime, timezone

        first_suite = args.suites[0] if args.suites else "all"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_dir = str(Path("evals/results") / first_suite / timestamp)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = output_path / "results.json"
    write_results_json(results, json_path)
    logger.info("Wrote JSON results to %s", json_path)

    # Markdown (unless --json-only)
    if not args.json_only:
        md_path = output_path / "report.md"
        write_markdown_report(results, md_path)
        logger.info("Wrote markdown report to %s", md_path)

    # ---- Baseline snapshot -------------------------------------------------
    from evals.baselines import BaselineSnapshot, ComparisonReport, compare_baselines, snapshot_dir_from_results

    if args.save_baseline:
        snapshot_dir_from_results(results, args.save_baseline)
        logger.info("Baseline snapshot(s) saved to %s", args.save_baseline)

    # ---- Baseline comparison -----------------------------------------------
    comparison: ComparisonReport | None = None
    if args.baseline:
        try:
            from evals.baselines import load_baseline

            baseline = load_baseline(args.baseline)
            candidate = BaselineSnapshot.from_results(results, suite=baseline.suite)
            comparison = compare_baselines(
                baseline, candidate, fail_under=args.fail_under
            )

            # Write comparison report to the same output dir
            report_path = output_path / "comparison.json"
            report_path.write_text(
                json.dumps(_comparison_to_dict(comparison), indent=2) + "\n",
                encoding="utf-8",
            )
            logger.info("Comparison report written to %s", report_path)

            # Print decision to stderr
            _print_comparison(comparison)

        except Exception as exc:
            logger.error("Baseline comparison failed: %s", exc)
            comparison = None

    # ---- Fail-under gate ---------------------------------------------------
    if args.fail_under > 0.0:
        pass_rate = passed / len(results) if results else 0.0
        if pass_rate < args.fail_under:
            logger.error(
                "FAIL: pass rate %.1f%% is below --fail-under %.1f%%",
                pass_rate * 100,
                args.fail_under * 100,
            )
            return 1
        logger.info(
            "PASS: pass rate %.1f%% meets --fail-under %.1f%%",
            pass_rate * 100,
            args.fail_under * 100,
        )

    return 0


def _print_comparison(comparison: ComparisonReport) -> None:
    """Print the comparison report to stderr in a human-readable format."""
    print(file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("BASELINE COMPARISON", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Recommendation: {comparison.recommendation}", file=sys.stderr)
    print(file=sys.stderr)
    print(comparison.summary, file=sys.stderr)
    print(file=sys.stderr)

    if comparison.guardrails:
        print("Guardrails:", file=sys.stderr)
        for g in comparison.guardrails:
            print(f"  ⚠  {g}", file=sys.stderr)
        print(file=sys.stderr)

    if comparison.regressions:
        print(f"Regressions ({len(comparison.regressions)}):", file=sys.stderr)
        for r in comparison.regressions:
            print(f"  ↓ {r}", file=sys.stderr)
        print(file=sys.stderr)

    if comparison.improvements:
        print(f"Improvements ({len(comparison.improvements)}):", file=sys.stderr)
        for imp in comparison.improvements:
            print(f"  ↑ {imp}", file=sys.stderr)
        print(file=sys.stderr)

    print(
        f"Pass rate: {comparison.pass_rate_candidate:.1%} (was {comparison.pass_rate_baseline:.1%})",
        file=sys.stderr,
    )
    print(
        f"Median latency: {comparison.median_latency_candidate:.0f}ms "
        f"(was {comparison.median_latency_baseline:.0f}ms)",
        file=sys.stderr,
    )
    if comparison.median_cost_candidate is not None:
        print(
            f"Median cost: ${comparison.median_cost_candidate:.6f} "
            f"(was ${comparison.median_cost_baseline:.6f})",
            file=sys.stderr,
        )
    print("=" * 60, file=sys.stderr)


def _comparison_to_dict(comparison: ComparisonReport) -> dict[str, Any]:
    """Serialise a ComparisonReport for JSON output."""
    return {
        "recommendation": comparison.recommendation,
        "summary": comparison.summary,
        "pass_rate_baseline": comparison.pass_rate_baseline,
        "pass_rate_candidate": comparison.pass_rate_candidate,
        "pass_rate_delta": comparison.pass_rate_delta,
        "median_latency_baseline_ms": comparison.median_latency_baseline,
        "median_latency_candidate_ms": comparison.median_latency_candidate,
        "median_cost_baseline_usd": comparison.median_cost_baseline,
        "median_cost_candidate_usd": comparison.median_cost_candidate,
        "improvements": comparison.improvements,
        "regressions": comparison.regressions,
        "guardrails": comparison.guardrails,
        "case_comparisons": [
            {
                "case_id": cc.case_id,
                "suite": cc.suite,
                "baseline_score": cc.baseline_score,
                "candidate_score": cc.candidate_score,
                "delta": cc.delta,
                "regression": cc.regression,
                "improvement": cc.improvement,
                "details": cc.details,
            }
            for cc in comparison.case_comparisons
        ],
    }


def _build_fixture_results(
    cases: list[Any],
    *,
    fixture_path: str,
    model: str | None,
    provider: str | None,
    judge_model: str | None,
    judge_provider: str | None,
) -> list[Any]:
    from evals.runner import build_result_from_components

    fixture_payload = _load_fixture_payload(fixture_path)
    defaults = fixture_payload.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("fixture payload 'defaults' must be a mapping when present")

    cases_payload = fixture_payload.get("cases")
    if not isinstance(cases_payload, dict):
        raise ValueError("fixture payload must contain a top-level 'cases' mapping")

    results = []
    for case in cases:
        case_fixture = cases_payload.get(case.case_id)
        if not isinstance(case_fixture, dict):
            raise ValueError(f"fixture payload missing case entry for {case.case_id}")

        merged = dict(defaults)
        merged.update(case_fixture)
        tool_calls = _normalize_tool_calls(merged.get("tool_calls"))
        results.append(
            build_result_from_components(
                case,
                final_response=str(merged.get("final_response", "")),
                completed=bool(merged.get("completed", True)),
                failed=bool(merged.get("failed", False)),
                error=_optional_string(merged.get("error")),
                tool_calls=tool_calls,
                input_tokens=_optional_int(merged.get("input_tokens")),
                output_tokens=_optional_int(merged.get("output_tokens")),
                cache_read_tokens=_optional_int(merged.get("cache_read_tokens")),
                cache_write_tokens=_optional_int(merged.get("cache_write_tokens")),
                estimated_cost_usd=_optional_float(merged.get("estimated_cost_usd")),
                actual_cost_usd=_optional_float(merged.get("actual_cost_usd")),
                model=model or _optional_string(merged.get("model")) or "fixture-smoke",
                provider=provider or _optional_string(merged.get("provider")) or "fixture",
                judge_model=judge_model or _optional_string(merged.get("judge_model")),
                judge_provider=judge_provider or _optional_string(merged.get("judge_provider")),
                elapsed_ms=_optional_int(merged.get("elapsed_ms")) or 0,
            )
        )
    return results


def _load_fixture_payload(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    if path.endswith(".json"):
        payload = json.loads(raw)
    else:
        payload = yaml.safe_load(raw)
    if not isinstance(payload, dict):
        raise ValueError("fixture payload root must be a mapping")
    return payload


def _normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]]:
    if raw_tool_calls is None:
        return []
    if not isinstance(raw_tool_calls, list):
        raise ValueError("fixture tool_calls must be a list")

    normalized: list[dict[str, Any]] = []
    for item in raw_tool_calls:
        if isinstance(item, str):
            normalized.append({"name": item})
        elif isinstance(item, dict):
            normalized.append(dict(item))
        else:
            raise ValueError("fixture tool_calls entries must be strings or mappings")
    return normalized


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


if __name__ == "__main__":
    sys.exit(main())
