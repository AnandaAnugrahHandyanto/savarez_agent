from __future__ import annotations

from copy import deepcopy
from typing import Any


_TAIL_LIMIT = 4_000

_COMMON_EVIDENCE = ("exit_code",)

_RISK_MATRIX: dict[str, dict[str, Any]] = {
    "docs_only": {
        "commands": [
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check", "--", "{changed_docs}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "changed_docs"],
            }
        ],
        "allowed_skip_reasons": ["docs_only_no_tests_needed"],
    },
    "tool_schema": {
        "commands": [
            {
                "cmd_id": "tool-focused-pytest",
                "argv": ["python", "-m", "pytest", "{focused_tool_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "test_count"],
            },
            {
                "cmd_id": "py-compile",
                "argv": ["python", "-m", "py_compile", "{changed_python_paths}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "py_compile_paths"],
            },
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check"],
                "evidence_fields": [*_COMMON_EVIDENCE],
            },
        ],
        "allowed_skip_reasons": ["schema_or_docs_only_no_broad_tests"],
    },
    "codex_orchestrator": {
        "commands": [
            {
                "cmd_id": "workflow-tool-pytest",
                "argv": ["python", "-m", "pytest", "tests/tools/test_codex_workflow_run_tool.py"],
                "evidence_fields": [*_COMMON_EVIDENCE, "test_count"],
            },
            {
                "cmd_id": "py-compile",
                "argv": ["python", "-m", "py_compile", "tools/codex_workflow_run_tool.py"],
                "evidence_fields": [*_COMMON_EVIDENCE, "py_compile_paths"],
            },
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check"],
                "evidence_fields": [*_COMMON_EVIDENCE],
            },
            {
                "cmd_id": "dry-run-smoke",
                "argv": ["codex_workflow_run", "--mode", "dry_run"],
                "evidence_fields": ["dry_run_json", "no_mutation_proof"],
                "allowed_skip_reasons": ["dry_run_skips_real_codex_implementation"],
            },
        ],
        "allowed_skip_reasons": ["dry_run_skips_real_codex_implementation"],
    },
    "review_guard": {
        "commands": [
            {
                "cmd_id": "review-guard-pytest",
                "argv": ["python", "-m", "pytest", "{review_guard_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "final_json_schema"],
            },
            {
                "cmd_id": "review-packet-smoke",
                "argv": ["codex_review_packet", "--smoke"],
                "evidence_fields": [*_COMMON_EVIDENCE, "flood_metadata"],
            },
            {
                "cmd_id": "py-compile",
                "argv": ["python", "-m", "py_compile", "{review_guard_paths}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "py_compile_paths"],
            },
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check"],
                "evidence_fields": [*_COMMON_EVIDENCE],
            },
        ],
        "allowed_skip_reasons": ["external_codex_review_provider_unavailable_disclosed"],
    },
    "gateway_runtime": {
        "commands": [
            {
                "cmd_id": "gateway-focused-pytest",
                "argv": ["python", "-m", "pytest", "{gateway_focused_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "route_mode_tests", "status"],
            },
            {
                "cmd_id": "py-compile",
                "argv": ["python", "-m", "py_compile", "{gateway_paths}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "py_compile_paths"],
            },
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check"],
                "evidence_fields": [*_COMMON_EVIDENCE],
            },
        ],
        "allowed_skip_reasons": ["restart_requires_explicit_authorization"],
        "recommends_restart": False,
        "recommendation": "no_restart_without_explicit_authorization",
    },
    "compression": {
        "commands": [
            {
                "cmd_id": "context-compressor-pytest",
                "argv": ["python", "-m", "pytest", "{context_compressor_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "token_status_tests"],
            },
            {
                "cmd_id": "py-compile",
                "argv": ["python", "-m", "py_compile", "{compression_paths}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "py_compile_paths"],
            },
            {
                "cmd_id": "diff-check",
                "argv": ["git", "diff", "--check"],
                "evidence_fields": [*_COMMON_EVIDENCE],
            },
        ],
        "allowed_skip_reasons": ["live_provider_test_requires_user_authorization"],
    },
    "secrets/privacy": {
        "commands": [
            {
                "cmd_id": "added-line-secret-scan",
                "argv": ["secret_scan", "--added-lines"],
                "evidence_fields": [*_COMMON_EVIDENCE, "scan_result"],
            },
            {
                "cmd_id": "redaction-pytest",
                "argv": ["python", "-m", "pytest", "{redaction_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "redaction_cases"],
            },
            {
                "cmd_id": "focused-pytest",
                "argv": ["python", "-m", "pytest", "{focused_tests}"],
                "evidence_fields": [*_COMMON_EVIDENCE, "test_count"],
            },
        ],
        "allowed_skip_reasons": [],
        "non_skippable_cmd_ids": ["added-line-secret-scan"],
    },
}


def risk_matrix() -> dict[str, dict[str, Any]]:
    return deepcopy(_RISK_MATRIX)


def _risk_items(risk_classes: Any) -> list[str]:
    if isinstance(risk_classes, str):
        risk_classes = [risk_classes]
    if not isinstance(risk_classes, list):
        return []
    return [risk for risk in risk_classes if isinstance(risk, str) and risk.strip()]


def _normalize_risks(risk_classes: Any) -> list[str]:
    return [risk for risk in _risk_items(risk_classes) if risk in _RISK_MATRIX]


def route_risk_classes(risk_classes: Any) -> dict[str, Any]:
    raw_risks = _risk_items(risk_classes)
    risks = [risk for risk in raw_risks if risk in _RISK_MATRIX]
    unknown_risks = [risk for risk in raw_risks if risk not in _RISK_MATRIX]
    commands_by_id: dict[str, dict[str, Any]] = {}
    evidence_fields: set[str] = set()
    allowed_skip_reasons: set[str] = set()
    allowed_skip_reasons_by_cmd_id: dict[str, set[str]] = {}
    non_skippable_cmd_ids: set[str] = set()
    recommendations: list[str] = []
    recommends_restart = None

    for risk in risks:
        spec = _RISK_MATRIX[risk]
        for command in spec["commands"]:
            cmd_id = command["cmd_id"]
            commands_by_id.setdefault(cmd_id, deepcopy(command))
            evidence_fields.update(command.get("evidence_fields", []))
            allowed_skip_reasons_by_cmd_id.setdefault(cmd_id, set()).update(command.get("allowed_skip_reasons", []))
        allowed_skip_reasons.update(spec.get("allowed_skip_reasons", []))
        non_skippable_cmd_ids.update(spec.get("non_skippable_cmd_ids", []))
        if "recommends_restart" in spec:
            recommends_restart = bool(spec["recommends_restart"])
        if spec.get("recommendation"):
            recommendations.append(str(spec["recommendation"]))

    return {
        "risk_classes": risks,
        "unknown_risk_classes": unknown_risks,
        "risk_input_missing": not bool(raw_risks),
        "required_commands": list(commands_by_id.values()),
        "required_cmd_ids": list(commands_by_id),
        "evidence_fields": sorted(evidence_fields),
        "allowed_skip_reasons": sorted(allowed_skip_reasons),
        "allowed_skip_reasons_by_cmd_id": {
            cmd_id: sorted(reasons) for cmd_id, reasons in sorted(allowed_skip_reasons_by_cmd_id.items())
        },
        "non_skippable_cmd_ids": sorted(non_skippable_cmd_ids),
        "recommends_restart": recommends_restart,
        "recommendations": recommendations,
    }


def bounded_tail(value: Any, limit: int = _TAIL_LIMIT) -> str:
    text = "" if value is None else str(value)
    return text[-limit:]


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    normalized = {
        "cmd_id": result.get("cmd_id"),
        "argv": result.get("argv") if isinstance(result.get("argv"), list) else [],
        "exit_code": result.get("exit_code"),
        "stdout_tail": bounded_tail(result.get("stdout_tail", result.get("stdout"))),
        "stderr_tail": bounded_tail(result.get("stderr_tail", result.get("stderr"))),
        "start_time": result.get("start_time"),
        "end_time": result.get("end_time"),
        "status": status,
        "skip_reason": result.get("skip_reason"),
    }
    return normalized


def validate_verification_results(risk_classes: Any, results: Any) -> dict[str, Any]:
    route = route_risk_classes(risk_classes)
    required_cmd_ids = set(route["required_cmd_ids"])
    allowed_skip_reasons_by_cmd_id = {
        cmd_id: set(reasons) for cmd_id, reasons in route["allowed_skip_reasons_by_cmd_id"].items()
    }
    non_skippable_cmd_ids = set(route["non_skippable_cmd_ids"])
    result_items = results if isinstance(results, list) else []
    normalized_results = [normalize_result(item) for item in result_items if isinstance(item, dict)]
    by_id = {str(item.get("cmd_id")): item for item in normalized_results if item.get("cmd_id")}

    blocking_reasons: list[str] = []
    if route["risk_input_missing"]:
        blocking_reasons.append("missing_risk_class")
    for risk in route["unknown_risk_classes"]:
        blocking_reasons.append(f"unknown_risk_class:{risk}")
    if not route["risk_classes"] and not route["risk_input_missing"]:
        blocking_reasons.append("missing_known_risk_class")
    inspected_cmd_ids = required_cmd_ids | set(by_id)
    for cmd_id in sorted(required_cmd_ids):
        if cmd_id not in by_id:
            blocking_reasons.append(f"missing_required_verification:{cmd_id}")
    for cmd_id in sorted(inspected_cmd_ids):
        if cmd_id not in by_id:
            continue
        result = by_id[cmd_id]
        status = result.get("status")
        if status == "passed":
            continue
        if status == "failed":
            blocking_reasons.append(f"verification_failed:{cmd_id}")
            continue
        if status == "skipped":
            reason = result.get("skip_reason")
            if cmd_id in non_skippable_cmd_ids:
                blocking_reasons.append(f"verification_skip_forbidden:{cmd_id}")
            elif not isinstance(reason, str) or not reason.strip():
                blocking_reasons.append(f"verification_skipped_without_reason:{cmd_id}")
            elif reason not in allowed_skip_reasons_by_cmd_id.get(cmd_id, set()):
                blocking_reasons.append(f"verification_skipped_with_unallowed_reason:{cmd_id}")
            continue
        blocking_reasons.append(f"verification_invalid_status:{cmd_id}")

    return {
        "status": "blocked" if blocking_reasons else "passed",
        "blocks_next_stage": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "required_cmd_ids": route["required_cmd_ids"],
        "allowed_skip_reasons": route["allowed_skip_reasons"],
        "allowed_skip_reasons_by_cmd_id": route["allowed_skip_reasons_by_cmd_id"],
        "unknown_risk_classes": route["unknown_risk_classes"],
        "results": normalized_results,
    }
