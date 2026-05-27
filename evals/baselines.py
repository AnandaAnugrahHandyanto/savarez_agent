from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Sequence

from .schemas import EvalRunResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CaseScore:
    """Per-case score snapshot for comparison."""

    case_id: str
    suite: str
    score: float
    deterministic: float
    passed: bool
    failed: bool
    elapsed_ms: int
    estimated_cost_usd: float | None
    actual_cost_usd: float | None

    @classmethod
    def from_run(cls, result: EvalRunResult) -> CaseScore:
        return cls(
            case_id=result.case_id,
            suite=result.suite,
            score=result.aggregate_scores.get("overall", 0.0),
            deterministic=result.aggregate_scores.get("deterministic", 0.0),
            passed=not result.failed and not any(
                not a.passed for a in result.assertions
            ),
            failed=result.failed,
            elapsed_ms=result.elapsed_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            actual_cost_usd=result.actual_cost_usd,
        )


@dataclass(slots=True)
class BaselineSnapshot:
    """A durable baseline snapshot representing one eval run."""

    suite: str
    git_sha: str
    config_fingerprint: str
    run_date: str
    model: str | None
    provider: str | None
    total_cases: int
    passed_cases: int
    pass_rate: float
    median_latency_ms: float
    median_cost_usd: float | None
    per_case: list[CaseScore]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_results(
        cls,
        results: Iterable[EvalRunResult],
        *,
        suite: str | None = None,
        git_sha: str | None = None,
        config_fingerprint: str = "",
    ) -> BaselineSnapshot:
        ordered = list(results)
        if not ordered:
            raise ValueError("cannot create baseline from empty results")

        resolved_suite = suite or ordered[0].suite
        resolved_git_sha = git_sha or _detect_git_sha()

        scores = [CaseScore.from_run(r) for r in ordered]
        passed = sum(1 for s in scores if s.passed)
        total = len(scores)
        latencies = [s.elapsed_ms for s in scores]
        costs = [
            c
            for s in scores
            if (c := s.actual_cost_usd or s.estimated_cost_usd) is not None
        ]

        return cls(
            suite=resolved_suite,
            git_sha=resolved_git_sha,
            config_fingerprint=config_fingerprint,
            run_date=ordered[0].started_at,
            model=ordered[0].model,
            provider=ordered[0].provider,
            total_cases=total,
            passed_cases=passed,
            pass_rate=passed / total if total else 0.0,
            median_latency_ms=median(latencies) if latencies else 0.0,
            median_cost_usd=median(costs) if costs else None,
            per_case=scores,
        )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CaseComparison:
    """Diff of one case between baseline and candidate."""

    case_id: str
    suite: str
    baseline_score: float
    candidate_score: float
    delta: float  # positive = improvement, negative = regression
    regression: bool
    improvement: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ComparisonReport:
    """Full comparison between a baseline and a candidate run."""

    recommendation: str  # "ship" | "ship_with_scope_limit" | "no_ship"
    summary: str
    pass_rate_baseline: float
    pass_rate_candidate: float
    pass_rate_delta: float
    median_latency_baseline: float
    median_latency_candidate: float
    median_cost_baseline: float | None
    median_cost_candidate: float | None
    improvements: list[str]
    regressions: list[str]
    case_comparisons: list[CaseComparison]
    guardrails: list[str]


_DEFAULT_REGRESSION_THRESHOLD = 0.05  # score points


def compare_baselines(
    baseline: BaselineSnapshot,
    candidate: BaselineSnapshot,
    *,
    regression_threshold: float = _DEFAULT_REGRESSION_THRESHOLD,
    fail_under: float = 0.0,
) -> ComparisonReport:
    """Compare a baseline snapshot to a candidate run snapshot.

    Parameters
    ----------
    baseline : BaselineSnapshot
        The reference run.
    candidate : BaselineSnapshot
        The candidate run to evaluate.
    regression_threshold : float
        Minimum score drop (0-1) to classify as a regression.
    fail_under : float
        If candidate pass rate is below this, force no_ship.

    Returns
    -------
    ComparisonReport
        Structured comparison with ship recommendation.
    """
    baseline_map = {s.case_id: s for s in baseline.per_case}
    candidate_map = {s.case_id: s for s in candidate.per_case}
    all_case_ids = sorted(set(baseline_map) | set(candidate_map))

    comparisons: list[CaseComparison] = []
    regressions: list[str] = []
    improvements: list[str] = []
    guardrails: list[str] = []

    for case_id in all_case_ids:
        base_score_s, cand_score_s = 0.0, 0.0
        base_case = baseline_map.get(case_id)
        cand_case = candidate_map.get(case_id)
        present_in_both = base_case is not None and cand_case is not None

        if base_case is not None:
            base_score_s = base_case.score
        if cand_case is not None:
            cand_score_s = cand_case.score

        delta_s = cand_score_s - base_score_s
        is_regression = delta_s < -regression_threshold
        is_improvement = delta_s > regression_threshold

        details: dict[str, Any] = {}
        resolved_suite = ""
        if present_in_both:
            details = {
                "baseline_deterministic": base_case.deterministic,
                "candidate_deterministic": cand_case.deterministic,
                "baseline_elapsed_ms": base_case.elapsed_ms,
                "candidate_elapsed_ms": cand_case.elapsed_ms,
                "baseline_failed": base_case.failed,
                "candidate_failed": cand_case.failed,
            }
            resolved_suite = base_case.suite
        elif base_case is not None:
            details = {"note": "new case (not in baseline)"}
            is_improvement = False  # can't claim improvement on unknown prior
            resolved_suite = base_case.suite
        else:
            details = {"note": "missing from candidate run"}
            is_regression = True  # case disappeared = regression
            if cand_case is not None:
                resolved_suite = cand_case.suite

        if is_regression:
            prefix = f"[{resolved_suite}] " if resolved_suite else ""
            regressions.append(f"{prefix}{case_id} — {delta_s:+.3f}")
        if is_improvement:
            prefix = f"[{resolved_suite}] " if resolved_suite else ""
            improvements.append(f"{prefix}{case_id} — {delta_s:+.3f}")

        comparisons.append(
            CaseComparison(
                case_id=case_id,
                suite=resolved_suite,
                baseline_score=base_score_s,
                candidate_score=cand_score_s,
                delta=delta_s,
                regression=is_regression,
                improvement=is_improvement,
                details=details,
            )
        )

    # Aggregate stats
    pass_rate_baseline_val = baseline.passed_cases / baseline.total_cases
    pass_rate_cand_val = candidate.passed_cases / candidate.total_cases
    pass_rate_delta_val = pass_rate_cand_val - pass_rate_baseline_val

    latency_delta = candidate.median_latency_ms - baseline.median_latency_ms
    cost_str = ""
    if candidate.median_cost_usd is not None and baseline.median_cost_usd is not None:
        cost_ratio = (
            candidate.median_cost_usd / baseline.median_cost_usd
            if baseline.median_cost_usd > 0
            else float("inf")
        )
        cost_str = (
            f"cost {cost_ratio:.2f}x (${candidate.median_cost_usd:.6f} vs ${baseline.median_cost_usd:.6f})"
        )
    elif candidate.median_cost_usd is not None:
        cost_str = f"cost ${candidate.median_cost_usd:.6f} (no baseline cost data)"

    # Decide recommendation
    recommendation = "ship"

    if len(regressions) >= 1:
        # Check if any regression is from a case that was passing before
        critical_regressions = [
            c
            for c in comparisons
            if c.delta < -regression_threshold * 2  # double the threshold = critical
            and c.baseline_score >= 0.8
        ]
        if critical_regressions:
            recommendation = "no_ship"
            guardrails.append(
                f"Critical regression(s) in previously passing cases: {', '.join(c.case_id for c in critical_regressions)}"
            )
        elif len(regressions) >= 3:
            recommendation = "no_ship"
            guardrails.append(f"{len(regressions)} cases regressed — rollup exceeds tolerance")
        elif len(regressions) >= 1:
            recommendation = "ship_with_scope_limit"
            guardrails.append(f"Review regressed cases: {', '.join(r for r in regressions[:5])}")
    if fail_under > 0 and pass_rate_cand_val < fail_under:
        recommendation = "no_ship"
        guardrails.append(f"Candidate pass rate {pass_rate_cand_val:.1%} below --fail-under {fail_under:.1%}")

    candidate_pass_rate_str = f"{candidate.passed_cases}/{candidate.total_cases}"
    baseline_pass_rate_str = f"{baseline.passed_cases}/{baseline.total_cases}"

    summary_parts: list[str] = []

    if recommendation == "ship":
        if improvements:
            summary_parts.insert(
                0,
                f"Recommendation: ship — quality maintained or improved with {candidate_pass_rate_str} pass rate (was {baseline_pass_rate_str}).",
            )
        else:
            summary_parts.insert(
                0,
                f"Recommendation: ship — no material change ({candidate_pass_rate_str} pass rate, was {baseline_pass_rate_str}).",
            )
        if cost_str:
            if latency_delta > 1000:
                guardrails.append(f"Latency increased by {latency_delta:.0f}ms — monitor user-facing impact")
            summary_parts.append(cost_str)
        improvements_prefix = ""
        if improvements:
            improvements_prefix = f"Quality improved across {len(improvements)} case(s). "
        summary_parts.append(f"{improvements_prefix}All cases stable or better.")

    elif recommendation == "ship_with_scope_limit":
        summary_parts.insert(
            0,
            f"Recommendation: ship with scope limits — {len(regressions)} case(s) regressed ({candidate_pass_rate_str} vs {baseline_pass_rate_str}).",
        )
        if cost_str:
            summary_parts.append(cost_str)
        if improvements:
            summary_parts.append(f"{len(improvements)} case(s) improved.")

    else:  # no_ship
        summary_parts.insert(
            0,
            f"Recommendation: no_ship — {len(regressions)} case(s) regressed, "
            f"Pass rate {candidate_pass_rate_str} (was {baseline_pass_rate_str}).",
        )
        if any("Critical regression" in guardrail for guardrail in guardrails):
            summary_parts.append("Critical regressions found in previously passing cases.")
        elif any("below --fail-under" in guardrail for guardrail in guardrails):
            summary_parts.append(f"Candidate pass rate fell below the required {fail_under:.1%} gate.")

    if recommendation != "no_ship":
        guardrails = [g for g in guardrails if "Critical regression" not in g]

    return ComparisonReport(
        recommendation=recommendation,
        summary="\n\n".join(summary_parts),
        pass_rate_baseline=pass_rate_baseline_val,
        pass_rate_candidate=pass_rate_cand_val,
        pass_rate_delta=pass_rate_delta_val,
        median_latency_baseline=baseline.median_latency_ms,
        median_latency_candidate=candidate.median_latency_ms,
        median_cost_baseline=baseline.median_cost_usd,
        median_cost_candidate=candidate.median_cost_usd,
        improvements=improvements,
        regressions=regressions,
        case_comparisons=comparisons,
        guardrails=guardrails,
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def save_baseline(snapshot: BaselineSnapshot, path: str | Path) -> Path:
    """Write a baseline snapshot to disk as JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = snapshot.to_dict()
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logger.info("baseline snapshot saved to %s", output_path)
    return output_path


def load_baseline(path: str | Path) -> BaselineSnapshot:
    """Read a baseline snapshot from a JSON file."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    per_case = [CaseScore(**cs) for cs in data.pop("per_case", [])]
    return BaselineSnapshot(**data, per_case=per_case)


def snapshot_dir_from_results(
    results: Sequence[EvalRunResult], output_dir: str | Path
) -> Path:
    """Write per-suite baseline snapshots into *output_dir*.

    Returns the directory path.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    # Group by suite
    suites: dict[str, list[EvalRunResult]] = {}
    for r in results:
        suites.setdefault(r.suite, []).append(r)

    for suite_name, suite_results in suites.items():
        snapshot = BaselineSnapshot.from_results(suite_results, suite=suite_name)
        path = root / f"baseline.{suite_name}.json"
        save_baseline(snapshot, path)

    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_git_sha() -> str:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        logger.warning("could not detect git sha")
    return "unknown"