from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


EXPECTED_KEYS = (
    "must_include",
    "must_not_include",
    "regex_include",
    "regex_not_include",
)


def _normalize_patterns(value, *, case_id: str, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(
        f"case '{case_id}' field '{field_name}' must be a string or list of strings"
    )


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL case: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no}: case must be a JSON object")
        case_id = payload.get("id")
        expected = payload.get("expected")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_no}: case id must be a non-empty string")
        if not isinstance(expected, dict):
            raise ValueError(f"{path}:{line_no}: case '{case_id}' is missing expected rules")
        normalized_expected = {
            key: _normalize_patterns(
                expected.get(key), case_id=case_id, field_name=key
            )
            for key in EXPECTED_KEYS
        }
        cases.append(
            {
                "id": case_id,
                "input": payload.get("input"),
                "expected": normalized_expected,
                "tags": payload.get("tags", []),
            }
        )
    return cases


def count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def count_lines(text: str) -> int:
    return len(text.splitlines())


def evaluate_text(text: str, cases: list[dict]) -> dict:
    failures: list[dict] = []
    passed = 0
    passed_case_ids: list[str] = []
    failed_case_ids: list[str] = []

    for case in cases:
        case_failures: list[dict] = []
        expected = case["expected"]

        for phrase in expected["must_include"]:
            if phrase not in text:
                case_failures.append(
                    {
                        "id": case["id"],
                        "reason": "missing required phrase",
                        "check": "must_include",
                        "expected": phrase,
                    }
                )

        for phrase in expected["must_not_include"]:
            if phrase in text:
                case_failures.append(
                    {
                        "id": case["id"],
                        "reason": "found forbidden phrase",
                        "check": "must_not_include",
                        "expected": phrase,
                    }
                )

        for pattern in expected["regex_include"]:
            if re.search(pattern, text, re.MULTILINE) is None:
                case_failures.append(
                    {
                        "id": case["id"],
                        "reason": "missing required regex match",
                        "check": "regex_include",
                        "expected": pattern,
                    }
                )

        for pattern in expected["regex_not_include"]:
            if re.search(pattern, text, re.MULTILINE) is not None:
                case_failures.append(
                    {
                        "id": case["id"],
                        "reason": "found forbidden regex match",
                        "check": "regex_not_include",
                        "expected": pattern,
                    }
                )

        if case_failures:
            failures.extend(case_failures)
            failed_case_ids.append(case["id"])
            continue

        passed += 1
        passed_case_ids.append(case["id"])

    failed = len(cases) - passed
    score = passed / len(cases) if cases else 0.0
    return {
        "cases_total": len(cases),
        "passed": passed,
        "failed": failed,
        "score": score,
        "failures": failures,
        "passed_case_ids": passed_case_ids,
        "failed_case_ids": failed_case_ids,
    }


def _count_delta(candidate_value: int, baseline_value: int | None) -> int:
    if baseline_value is None:
        return 0
    return candidate_value - baseline_value


def compare_evaluations(
    candidate_evaluation: dict,
    baseline_evaluation: dict | None,
    *,
    candidate_tokens: int,
    baseline_tokens: int | None,
    candidate_lines: int,
    baseline_lines: int | None,
    reject_ties: bool,
    max_token_growth: float | None,
    max_line_growth: int | None,
) -> tuple[str, list[str], list[str], int, int]:
    reasons: list[str] = []
    regressions: list[str] = []
    token_delta = _count_delta(candidate_tokens, baseline_tokens)
    line_delta = _count_delta(candidate_lines, baseline_lines)

    if baseline_evaluation is not None:
        regressions = sorted(
            set(baseline_evaluation["passed_case_ids"])
            & set(candidate_evaluation["failed_case_ids"])
        )

        if candidate_evaluation["score"] < baseline_evaluation["score"]:
            reasons.append("candidate scored worse than baseline")
        elif (
            reject_ties
            and candidate_evaluation["score"] == baseline_evaluation["score"]
        ):
            reasons.append("candidate tied baseline and reject_ties is set")

        if max_token_growth is not None:
            baseline_cap = (
                0 if baseline_tokens is None else baseline_tokens * max_token_growth
            )
            if token_delta > baseline_cap:
                reasons.append("candidate exceeded max token growth")

        if max_line_growth is not None and line_delta > max_line_growth:
            reasons.append("candidate exceeded max line growth")

        if reasons:
            return "reject", reasons, regressions, token_delta, line_delta
        if candidate_evaluation["score"] == baseline_evaluation["score"]:
            return "needs-review", reasons, regressions, token_delta, line_delta

    if candidate_evaluation["failed"] > 0:
        reasons.append("candidate failed eval cases")
        return "reject", reasons, regressions, token_delta, line_delta

    return "accept", reasons, regressions, token_delta, line_delta


def build_result(
    candidate_path: Path,
    candidate_text: str,
    candidate_evaluation: dict,
    *,
    baseline_path: Path | None = None,
    baseline_text: str | None = None,
    baseline_evaluation: dict | None = None,
    reject_ties: bool = False,
    max_token_growth: float | None = None,
    max_line_growth: int | None = None,
) -> dict:
    candidate_token_count = count_tokens(candidate_text)
    baseline_token_count = count_tokens(baseline_text) if baseline_text is not None else None
    candidate_line_count = count_lines(candidate_text)
    baseline_line_count = count_lines(baseline_text) if baseline_text is not None else None
    decision, reasons, regressions, token_delta, line_delta = compare_evaluations(
        candidate_evaluation,
        baseline_evaluation,
        candidate_tokens=candidate_token_count,
        baseline_tokens=baseline_token_count,
        candidate_lines=candidate_line_count,
        baseline_lines=baseline_line_count,
        reject_ties=reject_ties,
        max_token_growth=max_token_growth,
        max_line_growth=max_line_growth,
    )

    return {
        "skill": str(candidate_path),
        "baseline_skill": str(baseline_path) if baseline_path is not None else None,
        "cases_total": candidate_evaluation["cases_total"],
        "passed": candidate_evaluation["passed"],
        "failed": candidate_evaluation["failed"],
        "score": candidate_evaluation["score"],
        "failures": candidate_evaluation["failures"],
        "regressions": regressions,
        "token_delta": token_delta,
        "line_delta": line_delta,
        "token_count": candidate_token_count,
        "line_count": candidate_line_count,
        "baseline_score": (
            baseline_evaluation["score"] if baseline_evaluation is not None else None
        ),
        "baseline_passed": (
            baseline_evaluation["passed"] if baseline_evaluation is not None else None
        ),
        "baseline_failed": (
            baseline_evaluation["failed"] if baseline_evaluation is not None else None
        ),
        "decision": decision,
        "reasons": reasons,
    }


def write_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def format_receipt(payload: dict) -> str:
    receipt = (
        f"{payload['decision'].upper()} "
        f"{payload['passed']}/{payload['cases_total']} "
        f"score={payload['score']:.3f} failures={payload['failed']}"
    )
    if payload["reasons"]:
        receipt += f" reason={payload['reasons'][0]}"
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic offline skill eval.")
    skill_group = parser.add_mutually_exclusive_group(required=True)
    skill_group.add_argument("--skill", help="Path to the skill markdown file.")
    skill_group.add_argument(
        "--candidate-skill",
        help="Path to the candidate skill markdown file.",
    )
    parser.add_argument(
        "--baseline-skill",
        help="Path to the baseline skill markdown file for comparison.",
    )
    parser.add_argument("--cases", required=True, help="Path to the JSONL eval cases.")
    parser.add_argument("--output", required=True, help="Path to write the JSON result.")
    parser.add_argument(
        "--reject-ties",
        action="store_true",
        help="Reject candidate skills that tie the baseline score.",
    )
    parser.add_argument(
        "--max-token-growth",
        type=float,
        help="Maximum allowed token growth relative to the baseline.",
    )
    parser.add_argument(
        "--max-line-growth",
        type=int,
        help="Maximum allowed line growth relative to the baseline.",
    )
    parser.add_argument(
        "--fail-on-reject",
        action="store_true",
        help="Return a non-zero exit code when the decision is reject.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        candidate_path = Path(args.candidate_skill or args.skill)
        baseline_path = Path(args.baseline_skill) if args.baseline_skill else None
        cases_path = Path(args.cases)
        output_path = Path(args.output)
        if baseline_path is None and (
            args.reject_ties
            or args.max_token_growth is not None
            or args.max_line_growth is not None
        ):
            raise ValueError("baseline comparison flags require --baseline-skill")
        candidate_text = candidate_path.read_text(encoding="utf-8")
        baseline_text = (
            baseline_path.read_text(encoding="utf-8") if baseline_path is not None else None
        )
        cases = load_cases(cases_path)
        candidate_evaluation = evaluate_text(candidate_text, cases)
        baseline_evaluation = (
            evaluate_text(baseline_text, cases) if baseline_text is not None else None
        )
        payload = build_result(
            candidate_path,
            candidate_text,
            candidate_evaluation,
            baseline_path=baseline_path,
            baseline_text=baseline_text,
            baseline_evaluation=baseline_evaluation,
            reject_ties=args.reject_ties,
            max_token_growth=args.max_token_growth,
            max_line_growth=args.max_line_growth,
        )
        write_result(output_path, payload)
        print(format_receipt(payload))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.fail_on_reject and payload["decision"] == "reject":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
