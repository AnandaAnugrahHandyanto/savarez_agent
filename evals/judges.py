from __future__ import annotations

import json
from statistics import mean
from typing import Any, Mapping, Sequence

from .schemas import EvalCase, JudgeResult


class EvalJudgeError(ValueError):
    """Raised when judge prompts or outputs are invalid."""


def build_judge_prompt(case: EvalCase, *, final_response: str) -> str:
    """Build a strict-JSON grading prompt for rubric-based eval scoring."""
    if not case.judge_dimensions:
        raise EvalJudgeError("case has no judge_dimensions")

    dimension_lines = []
    for dimension in case.judge_dimensions:
        threshold = (
            f", pass_threshold={dimension.pass_threshold}"
            if dimension.pass_threshold is not None
            else ""
        )
        dimension_lines.append(
            "- {name}: {description} (scale {scale_min}-{scale_max}{threshold})".format(
                name=dimension.name,
                description=dimension.description,
                scale_min=dimension.scale_min,
                scale_max=dimension.scale_max,
                threshold=threshold,
            )
        )

    return "\n".join(
        [
            "You are grading a Hermes eval response.",
            "Score each rubric dimension independently and return strict JSON only.",
            "",
            f"Case ID: {case.case_id}",
            f"Suite: {case.suite}",
            f"Task type: {case.task_type}",
            f"Title: {case.title}",
            "",
            "Rubric dimensions:",
            *dimension_lines,
            "",
            "Return JSON with this exact shape:",
            '{"scores": [{"dimension": "<name>", "score": <number>, "passed": <true|false>, "rationale": "<brief rationale>"}], "overall_pass": <true|false>, "summary": "<brief summary>"}',
            "",
            "Rules:",
            "- Use every dimension exactly once.",
            "- score must stay within the declared scale for that dimension.",
            "- passed must reflect whether the score meets the dimension pass_threshold.",
            "- overall_pass must be a boolean pass/fail recommendation for the full output.",
            "- summary must be concise and evidence-based.",
            "- Do not add markdown fences or extra prose.",
            "",
            "Context:",
            case.context or "",
            "",
            "Prompt:",
            case.prompt,
            "",
            "Model response to grade:",
            final_response,
        ]
    ).strip()


def evaluate_judge_output(
    case: EvalCase,
    judge_output: str | Mapping[str, Any],
) -> list[JudgeResult]:
    """Parse strict-JSON judge output into normalized JudgeResult values."""
    if not case.judge_dimensions:
        return []

    payload = _load_payload(judge_output)
    rows = payload.get("scores")
    if not isinstance(rows, list):
        raise EvalJudgeError("judge output must contain a list field 'scores'")

    overall_pass = payload.get("overall_pass")
    if not isinstance(overall_pass, bool):
        raise EvalJudgeError("judge output field 'overall_pass' must be a boolean")

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise EvalJudgeError("judge output field 'summary' must be a non-empty string")

    by_name = {dimension.name: dimension for dimension in case.judge_dimensions}
    results: list[JudgeResult] = []
    seen: set[str] = set()

    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise EvalJudgeError(f"judge output scores[{idx}] must be an object")

        name = row.get("dimension")
        if not isinstance(name, str) or not name:
            raise EvalJudgeError(f"judge output scores[{idx}].dimension must be a non-empty string")
        if name not in by_name:
            raise EvalJudgeError(f"unknown judge dimension {name!r}")
        if name in seen:
            raise EvalJudgeError(f"duplicate judge dimension {name!r}")
        seen.add(name)

        dimension = by_name[name]
        raw_score = _coerce_float(row.get("score"), f"scores[{idx}].score")
        if raw_score < dimension.scale_min or raw_score > dimension.scale_max:
            raise EvalJudgeError(
                f"judge score for {name!r} out of range: {raw_score} not in [{dimension.scale_min}, {dimension.scale_max}]"
            )

        provided_passed = row.get("passed")
        if not isinstance(provided_passed, bool):
            raise EvalJudgeError(f"judge output scores[{idx}].passed must be a boolean")

        rationale = row.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise EvalJudgeError(f"judge output scores[{idx}].rationale must be a non-empty string")

        normalized = normalize_judge_score(
            raw_score,
            scale_min=dimension.scale_min,
            scale_max=dimension.scale_max,
        )
        threshold = dimension.pass_threshold if dimension.pass_threshold is not None else dimension.scale_min
        threshold_normalized = normalize_judge_score(
            threshold,
            scale_min=dimension.scale_min,
            scale_max=dimension.scale_max,
        )
        computed_passed = normalized >= threshold_normalized
        if provided_passed != computed_passed:
            raise EvalJudgeError(
                f"judge output scores[{idx}].passed disagrees with threshold-derived pass for {name!r}"
            )

        results.append(
            JudgeResult(
                dimension=name,
                score=normalized,
                passed=computed_passed,
                rationale=rationale.strip(),
            )
        )

    missing = [dimension.name for dimension in case.judge_dimensions if dimension.name not in seen]
    if missing:
        raise EvalJudgeError(f"judge output missing dimension(s): {', '.join(missing)}")

    computed_overall_pass = all(result.passed for result in results)
    if overall_pass != computed_overall_pass:
        raise EvalJudgeError("judge output field 'overall_pass' disagrees with dimension pass results")

    return results


def normalize_judge_score(score: float, *, scale_min: float, scale_max: float) -> float:
    """Normalize a raw rubric score into the 0..1 range."""
    if scale_max <= scale_min:
        raise EvalJudgeError(
            f"invalid judge scale: scale_max ({scale_max}) must be greater than scale_min ({scale_min})"
        )
    if score < scale_min or score > scale_max:
        raise EvalJudgeError(f"judge score {score} is outside [{scale_min}, {scale_max}]")
    return (score - scale_min) / (scale_max - scale_min)


def aggregate_eval_scores(
    *,
    deterministic_score: float,
    judge_results: Sequence[JudgeResult] | None = None,
    efficiency_score: float | None = None,
) -> dict[str, float]:
    """Combine deterministic and rubric scores using the eval-plan MVP weights."""
    det = _clamp_01(deterministic_score, name="deterministic_score")
    judge_rows = list(judge_results or [])

    if not judge_rows:
        return {
            "deterministic": det,
            "overall": det,
        }

    judge_score = mean(row.score for row in judge_rows)
    judge_score = _clamp_01(judge_score, name="judge_score")
    eff = 1.0 if efficiency_score is None else _clamp_01(efficiency_score, name="efficiency_score")

    overall = (0.5 * det) + (0.4 * judge_score) + (0.1 * eff)
    return {
        "deterministic": det,
        "judge": judge_score,
        "efficiency": eff,
        "overall": round(overall, 6),
    }


def _load_payload(judge_output: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(judge_output, Mapping):
        payload = judge_output
    else:
        if not isinstance(judge_output, str) or not judge_output.strip():
            raise EvalJudgeError("judge output must be a non-empty JSON string or mapping")
        try:
            payload = json.loads(judge_output)
        except json.JSONDecodeError as exc:
            raise EvalJudgeError(f"judge output is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise EvalJudgeError("judge output JSON root must be an object")
    return payload


def _coerce_float(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvalJudgeError(f"{path} must be a number")
    return float(value)


def _clamp_01(value: float, *, name: str) -> float:
    if value < 0.0 or value > 1.0:
        raise EvalJudgeError(f"{name} must be between 0 and 1 inclusive; got {value}")
    return float(value)
