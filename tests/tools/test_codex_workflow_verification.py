from agent import codex_workflow_verification as verification


def _result(cmd_id: str, status: str = "passed", **extra):
    payload = {
        "cmd_id": cmd_id,
        "argv": ["echo", cmd_id],
        "exit_code": 0 if status == "passed" else 1,
        "stdout": "ok",
        "stderr": "",
        "start_time": "2026-06-07T00:00:00Z",
        "end_time": "2026-06-07T00:00:01Z",
        "status": status,
    }
    payload.update(extra)
    return payload


def test_risk_router_maps_codex_orchestrator_to_required_commands():
    routed = verification.route_risk_classes(["codex_orchestrator"])

    assert routed["required_cmd_ids"] == [
        "workflow-tool-pytest",
        "py-compile",
        "diff-check",
        "dry-run-smoke",
    ]
    assert "dry_run_json" in routed["evidence_fields"]
    assert "no_mutation_proof" in routed["evidence_fields"]
    assert "dry_run_skips_real_codex_implementation" in routed["allowed_skip_reasons"]


def test_verification_failure_blocks_next_stage():
    results = [
        _result("workflow-tool-pytest"),
        _result("py-compile", "failed"),
        _result("diff-check"),
        _result("dry-run-smoke"),
    ]

    gate = verification.validate_verification_results(["codex_orchestrator"], results)

    assert gate["status"] == "blocked"
    assert gate["blocks_next_stage"] is True
    assert "verification_failed:py-compile" in gate["blocking_reasons"]


def test_skipped_verification_requires_reason():
    results = [
        _result("workflow-tool-pytest"),
        _result("py-compile", "skipped", exit_code=None),
        _result("diff-check"),
        _result("dry-run-smoke"),
    ]

    gate = verification.validate_verification_results(["codex_orchestrator"], results)

    assert gate["status"] == "blocked"
    assert "verification_skipped_without_reason:py-compile" in gate["blocking_reasons"]


def test_secret_privacy_risk_cannot_skip_scan():
    results = [
        _result(
            "added-line-secret-scan",
            "skipped",
            exit_code=None,
            skip_reason="provider_unavailable",
        ),
        _result("redaction-pytest"),
        _result("focused-pytest"),
    ]

    gate = verification.validate_verification_results(["secrets/privacy"], results)

    assert gate["status"] == "blocked"
    assert gate["blocks_next_stage"] is True
    assert "verification_skip_forbidden:added-line-secret-scan" in gate["blocking_reasons"]


def test_gateway_runtime_risk_recommends_no_restart_by_default():
    routed = verification.route_risk_classes(["gateway_runtime"])

    assert routed["recommends_restart"] is False
    assert routed["recommendations"] == ["no_restart_without_explicit_authorization"]
    assert "gateway-focused-pytest" in routed["required_cmd_ids"]


def test_missing_or_unknown_risk_classes_block_next_stage():
    passed_anything = [_result("diff-check")]

    missing = verification.validate_verification_results([], passed_anything)
    unknown = verification.validate_verification_results(["future_phase"], passed_anything)

    assert missing["status"] == "blocked"
    assert "missing_risk_class" in missing["blocking_reasons"]
    assert unknown["status"] == "blocked"
    assert "unknown_risk_class:future_phase" in unknown["blocking_reasons"]
    assert "missing_known_risk_class" in unknown["blocking_reasons"]


def test_allowed_skip_reason_only_applies_to_declared_command():
    py_compile_skipped = [
        _result("workflow-tool-pytest"),
        _result(
            "py-compile",
            "skipped",
            exit_code=None,
            skip_reason="dry_run_skips_real_codex_implementation",
        ),
        _result("diff-check"),
        _result("dry-run-smoke"),
    ]
    dry_run_skipped = [
        _result("workflow-tool-pytest"),
        _result("py-compile"),
        _result("diff-check"),
        _result(
            "dry-run-smoke",
            "skipped",
            exit_code=None,
            skip_reason="dry_run_skips_real_codex_implementation",
        ),
    ]

    blocked = verification.validate_verification_results(["codex_orchestrator"], py_compile_skipped)
    passed = verification.validate_verification_results(["codex_orchestrator"], dry_run_skipped)

    assert blocked["status"] == "blocked"
    assert "verification_skipped_with_unallowed_reason:py-compile" in blocked["blocking_reasons"]
    assert passed["status"] == "passed"
    assert passed["blocks_next_stage"] is False


def test_unallowed_skip_reason_blocks():
    results = [
        _result("workflow-tool-pytest"),
        _result("py-compile"),
        _result("diff-check"),
        _result("dry-run-smoke", "skipped", exit_code=None, skip_reason="provider_unavailable"),
    ]

    gate = verification.validate_verification_results(["codex_orchestrator"], results)

    assert gate["status"] == "blocked"
    assert "verification_skipped_with_unallowed_reason:dry-run-smoke" in gate["blocking_reasons"]


def test_normalized_verification_result_schema_includes_bounded_tails_and_skip_reason():
    normalized = verification.normalize_result(
        {
            "cmd_id": "dry-run-smoke",
            "argv": ["codex_workflow_run", "--mode", "dry_run"],
            "exit_code": None,
            "stdout": "x" * (verification._TAIL_LIMIT + 5),
            "stderr": "y" * (verification._TAIL_LIMIT + 5),
            "start_time": "2026-06-07T00:00:00Z",
            "end_time": "2026-06-07T00:00:01Z",
            "status": "skipped",
            "skip_reason": "dry_run_skips_real_codex_implementation",
        }
    )

    assert set(normalized) == {
        "cmd_id",
        "argv",
        "exit_code",
        "stdout_tail",
        "stderr_tail",
        "start_time",
        "end_time",
        "status",
        "skip_reason",
    }
    assert len(normalized["stdout_tail"]) == verification._TAIL_LIMIT
    assert len(normalized["stderr_tail"]) == verification._TAIL_LIMIT
    assert normalized["skip_reason"] == "dry_run_skips_real_codex_implementation"
