from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, TypeVar, cast

import yaml

TaskType = Literal[
    "analysis",
    "review",
    "briefing",
    "browser",
    "multimodal",
    "routing",
    "tooling",
]

_ALLOWED_TASK_TYPES = set(TaskType.__args__)
_T = TypeVar("_T")


class EvalSchemaError(ValueError):
    """Raised when an eval case or result payload violates the schema."""


@dataclass(slots=True)
class DeterministicAssertion:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    required: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "assertions[]") -> "DeterministicAssertion":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(payload, {"kind", "params", "weight", "required"}, path)
        return cls(
            kind=_require_string(payload, "kind", path),
            params=_optional_mapping(payload.get("params"), f"{path}.params"),
            weight=_optional_float(payload.get("weight"), f"{path}.weight", default=1.0),
            required=_optional_bool(payload.get("required"), f"{path}.required", default=True),
        )


@dataclass(slots=True)
class JudgeDimension:
    name: str
    description: str
    scale_min: int = 1
    scale_max: int = 5
    pass_threshold: float | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "judge_dimensions[]") -> "JudgeDimension":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(payload, {"name", "description", "scale_min", "scale_max", "pass_threshold"}, path)
        return cls(
            name=_require_string(payload, "name", path),
            description=_require_string(payload, "description", path),
            scale_min=_optional_int(payload.get("scale_min"), f"{path}.scale_min", default=1),
            scale_max=_optional_int(payload.get("scale_max"), f"{path}.scale_max", default=5),
            pass_threshold=_nullable_float(payload.get("pass_threshold"), f"{path}.pass_threshold"),
        )


@dataclass(slots=True)
class EvalCase:
    case_id: str
    suite: str
    task_type: TaskType
    title: str
    prompt: str
    context: str | None = None
    tags: list[str] = field(default_factory=list)
    enabled_toolsets: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    assertions: list[DeterministicAssertion] = field(default_factory=list)
    judge_dimensions: list[JudgeDimension] = field(default_factory=list)
    gold_answer: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "case") -> "EvalCase":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(
            payload,
            {
                "case_id",
                "suite",
                "task_type",
                "title",
                "prompt",
                "context",
                "tags",
                "enabled_toolsets",
                "expected_tools",
                "forbidden_tools",
                "assertions",
                "judge_dimensions",
                "gold_answer",
                "notes",
            },
            path,
        )
        task_type = _require_string(payload, "task_type", path)
        if task_type not in _ALLOWED_TASK_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_TASK_TYPES))
            raise EvalSchemaError(f"{path}.task_type must be one of [{allowed}], got {task_type!r}")
        return cls(
            case_id=_require_string(payload, "case_id", path),
            suite=_require_string(payload, "suite", path),
            task_type=cast(TaskType, task_type),
            title=_require_string(payload, "title", path),
            prompt=_require_string(payload, "prompt", path),
            context=_nullable_string(payload.get("context"), f"{path}.context"),
            tags=_list_of_strings(payload.get("tags"), f"{path}.tags"),
            enabled_toolsets=_list_of_strings(payload.get("enabled_toolsets"), f"{path}.enabled_toolsets"),
            expected_tools=_list_of_strings(payload.get("expected_tools"), f"{path}.expected_tools"),
            forbidden_tools=_list_of_strings(payload.get("forbidden_tools"), f"{path}.forbidden_tools"),
            assertions=_list_of_objects(payload.get("assertions"), DeterministicAssertion.from_dict, f"{path}.assertions"),
            judge_dimensions=_list_of_objects(payload.get("judge_dimensions"), JudgeDimension.from_dict, f"{path}.judge_dimensions"),
            gold_answer=_nullable_string(payload.get("gold_answer"), f"{path}.gold_answer"),
            notes=_nullable_string(payload.get("notes"), f"{path}.notes"),
        )


@dataclass(slots=True)
class AssertionResult:
    kind: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "assertions[]") -> "AssertionResult":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(payload, {"kind", "passed", "score", "details"}, path)
        return cls(
            kind=_require_string(payload, "kind", path),
            passed=_require_bool(payload, "passed", path),
            score=_require_float(payload, "score", path),
            details=_optional_mapping(payload.get("details"), f"{path}.details"),
        )


@dataclass(slots=True)
class JudgeResult:
    dimension: str
    score: float
    passed: bool
    rationale: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "judge_results[]") -> "JudgeResult":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(payload, {"dimension", "score", "passed", "rationale"}, path)
        return cls(
            dimension=_require_string(payload, "dimension", path),
            score=_require_float(payload, "score", path),
            passed=_require_bool(payload, "passed", path),
            rationale=_require_string(payload, "rationale", path),
        )


@dataclass(slots=True)
class EvalRunResult:
    run_id: str
    case_id: str
    suite: str
    provider: str | None
    model: str | None
    judge_provider: str | None
    judge_model: str | None
    started_at: str
    ended_at: str
    elapsed_ms: int
    completed: bool
    failed: bool
    error: str | None
    final_response: str
    tool_calls: list[dict[str, Any]]
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    assertions: list[AssertionResult]
    judge_results: list[JudgeResult]
    aggregate_scores: dict[str, float]
    labels: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, path: str = "result") -> "EvalRunResult":
        payload = _expect_mapping(data, path)
        _reject_unknown_keys(
            payload,
            {
                "run_id",
                "case_id",
                "suite",
                "provider",
                "model",
                "judge_provider",
                "judge_model",
                "started_at",
                "ended_at",
                "elapsed_ms",
                "completed",
                "failed",
                "error",
                "final_response",
                "tool_calls",
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cache_write_tokens",
                "estimated_cost_usd",
                "actual_cost_usd",
                "assertions",
                "judge_results",
                "aggregate_scores",
                "labels",
            },
            path,
        )
        return cls(
            run_id=_require_string(payload, "run_id", path),
            case_id=_require_string(payload, "case_id", path),
            suite=_require_string(payload, "suite", path),
            provider=_nullable_string(payload.get("provider"), f"{path}.provider"),
            model=_nullable_string(payload.get("model"), f"{path}.model"),
            judge_provider=_nullable_string(payload.get("judge_provider"), f"{path}.judge_provider"),
            judge_model=_nullable_string(payload.get("judge_model"), f"{path}.judge_model"),
            started_at=_require_string(payload, "started_at", path),
            ended_at=_require_string(payload, "ended_at", path),
            elapsed_ms=_require_int(payload, "elapsed_ms", path),
            completed=_require_bool(payload, "completed", path),
            failed=_require_bool(payload, "failed", path),
            error=_nullable_string(payload.get("error"), f"{path}.error"),
            final_response=_require_string(payload, "final_response", path),
            tool_calls=_list_of_mappings(payload.get("tool_calls"), f"{path}.tool_calls"),
            input_tokens=_nullable_int(payload.get("input_tokens"), f"{path}.input_tokens"),
            output_tokens=_nullable_int(payload.get("output_tokens"), f"{path}.output_tokens"),
            cache_read_tokens=_nullable_int(payload.get("cache_read_tokens"), f"{path}.cache_read_tokens"),
            cache_write_tokens=_nullable_int(payload.get("cache_write_tokens"), f"{path}.cache_write_tokens"),
            estimated_cost_usd=_nullable_float(payload.get("estimated_cost_usd"), f"{path}.estimated_cost_usd"),
            actual_cost_usd=_nullable_float(payload.get("actual_cost_usd"), f"{path}.actual_cost_usd"),
            assertions=_list_of_objects(payload.get("assertions"), AssertionResult.from_dict, f"{path}.assertions"),
            judge_results=_list_of_objects(payload.get("judge_results"), JudgeResult.from_dict, f"{path}.judge_results"),
            aggregate_scores=_dict_of_floats(payload.get("aggregate_scores"), f"{path}.aggregate_scores"),
            labels=_optional_mapping(payload.get("labels"), f"{path}.labels"),
        )


def load_eval_case_yaml(raw_yaml: str) -> EvalCase:
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise EvalSchemaError(f"case YAML could not be parsed: {exc}") from exc
    return EvalCase.from_dict(_expect_mapping(data, "case"))


def load_eval_case_file(path: str | Path) -> EvalCase:
    case_path = Path(path)
    try:
        raw_yaml = case_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvalSchemaError(f"could not read case file {case_path}: {exc}") from exc
    return load_eval_case_yaml(raw_yaml)


def _reject_unknown_keys(data: Mapping[str, Any], allowed: set[str], path: str) -> None:
    extras = sorted(set(data) - allowed)
    if extras:
        extra_list = ", ".join(extras)
        raise EvalSchemaError(f"{path} contains unknown field(s): {extra_list}")


def _expect_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvalSchemaError(f"{path} must be a mapping, got {type(value).__name__}")
    return dict(value)


def _require_string(data: Mapping[str, Any], key: str, path: str) -> str:
    if key not in data:
        raise EvalSchemaError(f"{path}.{key} is required")
    return _coerce_string(data[key], f"{path}.{key}")


def _nullable_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _coerce_string(value, path)


def _coerce_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise EvalSchemaError(f"{path} must be a string, got {type(value).__name__}")
    return value


def _require_bool(data: Mapping[str, Any], key: str, path: str) -> bool:
    if key not in data:
        raise EvalSchemaError(f"{path}.{key} is required")
    return _coerce_bool(data[key], f"{path}.{key}")


def _optional_bool(value: Any, path: str, *, default: bool) -> bool:
    if value is None:
        return default
    return _coerce_bool(value, path)


def _coerce_bool(value: Any, path: str) -> bool:
    if isinstance(value, bool):
        return value
    raise EvalSchemaError(f"{path} must be a boolean, got {type(value).__name__}")


def _require_int(data: Mapping[str, Any], key: str, path: str) -> int:
    if key not in data:
        raise EvalSchemaError(f"{path}.{key} is required")
    return _coerce_int(data[key], f"{path}.{key}")


def _optional_int(value: Any, path: str, *, default: int) -> int:
    if value is None:
        return default
    return _coerce_int(value, path)


def _nullable_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _coerce_int(value, path)


def _coerce_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvalSchemaError(f"{path} must be an integer, got {type(value).__name__}")
    return value


def _require_float(data: Mapping[str, Any], key: str, path: str) -> float:
    if key not in data:
        raise EvalSchemaError(f"{path}.{key} is required")
    return _coerce_float(data[key], f"{path}.{key}")


def _optional_float(value: Any, path: str, *, default: float) -> float:
    if value is None:
        return default
    return _coerce_float(value, path)


def _nullable_float(value: Any, path: str) -> float | None:
    if value is None:
        return None
    return _coerce_float(value, path)


def _coerce_float(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvalSchemaError(f"{path} must be a number, got {type(value).__name__}")
    return float(value)


def _optional_mapping(value: Any, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    return _expect_mapping(value, path)


def _list_of_strings(value: Any, path: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvalSchemaError(f"{path} must be a list, got {type(value).__name__}")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_coerce_string(item, f"{path}[{index}]") )
    return result


def _list_of_objects(value: Any, loader: Any, path: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvalSchemaError(f"{path} must be a list, got {type(value).__name__}")
    result: list[Any] = []
    for index, item in enumerate(value):
        result.append(loader(item, path=f"{path}[{index}]") )
    return result


def _list_of_mappings(value: Any, path: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvalSchemaError(f"{path} must be a list, got {type(value).__name__}")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        result.append(_expect_mapping(item, f"{path}[{index}]"))
    return result


def _dict_of_floats(value: Any, path: str) -> dict[str, float]:
    mapping = _optional_mapping(value, path)
    result: dict[str, float] = {}
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise EvalSchemaError(f"{path} keys must be strings, got {type(key).__name__}")
        result[key] = _coerce_float(item, f"{path}.{key}")
    return result
