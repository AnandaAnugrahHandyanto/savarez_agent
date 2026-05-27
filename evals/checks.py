from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .schemas import AssertionResult, DeterministicAssertion

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_PLACEHOLDER_PATTERNS = (
    re.compile(r"\blorem ipsum\b", re.IGNORECASE),
    re.compile(r"\b(?:todo|tbd|fixme|placeholder)\b", re.IGNORECASE),
    re.compile(r"\b(?:your|the)\s+(?:answer|content|response|text|details|summary)\s+here\b", re.IGNORECASE),
    re.compile(r"\b(?:insert|add|provide|include|write)\s+(?:your|the)\s+(?:answer|content|response|text|details|summary)\b", re.IGNORECASE),
    re.compile(r"\[\s*(?:insert|add|provide|write)[^\]]*\]", re.IGNORECASE),
    re.compile(r"<[^>\n]{1,120}>"),
)


class EvalCheckError(ValueError):
    """Raised when an assertion is unknown or misconfigured."""


@dataclass(slots=True)
class DeterministicScore:
    score: float
    passed: bool
    total_weight: float
    earned_weight: float
    required_failures: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "total_weight": self.total_weight,
            "earned_weight": self.earned_weight,
            "required_failures": list(self.required_failures),
        }


_CHECKS = {
    "non_empty_output",
    "max_chars",
    "max_lines",
    "contains_substring",
    "required_regex",
    "forbidden_regex",
    "tool_used",
    "tool_not_used",
    "contains_url",
    "no_placeholder_language",
}


def evaluate_assertion(
    assertion: DeterministicAssertion,
    *,
    final_response: str,
    tool_calls: Iterable[Mapping[str, Any]] | None = None,
) -> AssertionResult:
    response = final_response or ""
    tools = _normalize_tool_names(tool_calls or [])

    if assertion.kind not in _CHECKS:
        allowed = ", ".join(sorted(_CHECKS))
        raise EvalCheckError(f"Unknown assertion kind {assertion.kind!r}; expected one of [{allowed}]")

    passed, details = _evaluate_kind(assertion.kind, assertion.params, response, tools)
    details = {
        **details,
        "weight": assertion.weight,
        "required": assertion.required,
    }
    return AssertionResult(
        kind=assertion.kind,
        passed=passed,
        score=1.0 if passed else 0.0,
        details=details,
    )



def evaluate_assertions(
    assertions: Iterable[DeterministicAssertion],
    *,
    final_response: str,
    tool_calls: Iterable[Mapping[str, Any]] | None = None,
) -> list[AssertionResult]:
    return [
        evaluate_assertion(assertion, final_response=final_response, tool_calls=tool_calls)
        for assertion in assertions
    ]



def aggregate_assertion_scores(
    assertions: Iterable[DeterministicAssertion],
    results: Iterable[AssertionResult],
) -> DeterministicScore:
    assertion_list = list(assertions)
    result_list = list(results)
    if len(assertion_list) != len(result_list):
        raise EvalCheckError(
            f"Assertion/result length mismatch: {len(assertion_list)} assertions vs {len(result_list)} results"
        )

    total_weight = 0.0
    earned_weight = 0.0
    required_failures: list[str] = []

    for assertion, result in zip(assertion_list, result_list, strict=True):
        weight = _validate_weight(assertion)
        total_weight += weight
        normalized_score = _normalize_result_score(result.score, result.kind)
        earned_weight += normalized_score * weight
        if assertion.required and not result.passed:
            required_failures.append(assertion.kind)

    score = 1.0 if total_weight == 0 else earned_weight / total_weight
    return DeterministicScore(
        score=score,
        passed=not required_failures,
        total_weight=total_weight,
        earned_weight=earned_weight,
        required_failures=required_failures,
    )



def _evaluate_kind(
    kind: str,
    params: Mapping[str, Any],
    response: str,
    tool_names: set[str],
) -> tuple[bool, dict[str, Any]]:
    if kind == "non_empty_output":
        trimmed = response.strip()
        return bool(trimmed), {"chars": len(response), "trimmed_chars": len(trimmed)}

    if kind == "max_chars":
        max_chars = _require_int(params, "max_chars", kind)
        observed = len(response)
        return observed <= max_chars, {"max_chars": max_chars, "observed_chars": observed}

    if kind == "max_lines":
        max_lines = _require_int(params, "max_lines", kind)
        observed = len(response.splitlines()) if response else 0
        return observed <= max_lines, {"max_lines": max_lines, "observed_lines": observed}

    if kind == "contains_substring":
        expected = _require_string(params, "substring", kind)
        ignore_case = _optional_bool(params.get("ignore_case"), default=False, path=f"{kind}.ignore_case")
        haystack = response.casefold() if ignore_case else response
        needle = expected.casefold() if ignore_case else expected
        return needle in haystack, {"substring": expected, "ignore_case": ignore_case}

    if kind == "required_regex":
        pattern = _require_string(params, "pattern", kind)
        flags = re.IGNORECASE if _optional_bool(params.get("ignore_case"), default=False, path=f"{kind}.ignore_case") else 0
        matched = re.search(pattern, response, flags=flags) is not None
        return matched, {"pattern": pattern, "ignore_case": bool(flags & re.IGNORECASE)}

    if kind == "forbidden_regex":
        pattern = _require_string(params, "pattern", kind)
        flags = re.IGNORECASE if _optional_bool(params.get("ignore_case"), default=False, path=f"{kind}.ignore_case") else 0
        matched = re.search(pattern, response, flags=flags) is not None
        return not matched, {"pattern": pattern, "ignore_case": bool(flags & re.IGNORECASE)}

    if kind == "tool_used":
        tool_name = _require_string(params, "tool", kind)
        return tool_name in tool_names, {"tool": tool_name, "used_tools": sorted(tool_names)}

    if kind == "tool_not_used":
        tool_name = _require_string(params, "tool", kind)
        return tool_name not in tool_names, {"tool": tool_name, "used_tools": sorted(tool_names)}

    if kind == "contains_url":
        url = _first_url(response)
        return url is not None, {"matched_url": url}

    if kind == "no_placeholder_language":
        matched_pattern = _first_placeholder_match(response)
        return matched_pattern is None, {"matched_placeholder": matched_pattern}

    raise EvalCheckError(f"Unhandled assertion kind {kind!r}")



def _normalize_tool_names(tool_calls: Iterable[Mapping[str, Any]]) -> set[str]:
    names: set[str] = set()
    for tool_call in tool_calls:
        if not isinstance(tool_call, Mapping):
            continue
        raw_name = tool_call.get("tool_name") or tool_call.get("name") or tool_call.get("tool")
        if isinstance(raw_name, str) and raw_name.strip():
            names.add(raw_name.strip())
    return names



def _first_url(response: str) -> str | None:
    match = _URL_RE.search(response)
    return match.group(0) if match else None



def _first_placeholder_match(response: str) -> str | None:
    for pattern in _PLACEHOLDER_PATTERNS:
        match = pattern.search(response)
        if match:
            return match.group(0)
    return None



def _validate_weight(assertion: DeterministicAssertion) -> float:
    weight = assertion.weight
    if weight < 0:
        raise EvalCheckError(f"Assertion {assertion.kind!r} has negative weight {weight}")
    return float(weight)



def _normalize_result_score(score: float, kind: str) -> float:
    normalized = float(score)
    if normalized < 0 or normalized > 1:
        raise EvalCheckError(f"Assertion result {kind!r} has score outside [0, 1]: {normalized}")
    return normalized



def _require_string(params: Mapping[str, Any], key: str, kind: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvalCheckError(f"Assertion {kind!r} requires non-empty string param {key!r}")
    return value



def _require_int(params: Mapping[str, Any], key: str, kind: str) -> int:
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvalCheckError(f"Assertion {kind!r} requires integer param {key!r}")
    return value



def _optional_bool(value: Any, *, default: bool, path: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise EvalCheckError(f"{path} must be a boolean when provided")
