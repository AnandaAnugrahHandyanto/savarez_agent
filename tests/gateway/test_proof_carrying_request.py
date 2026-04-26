from __future__ import annotations

from dataclasses import replace

from gateway.proof_carrying_request import (
    FAILURE_TAXONOMY,
    build_external_action_audit,
    build_provider_request_contract,
    build_provider_response_contract,
)
from gateway.tool_profile_snapshot import (
    build_tool_loader_contract,
    build_tool_registry,
    evaluate_tool_load_request,
)


TURN_CONTRACT = {
    "turn_contract_id": "turn:1",
    "allowed_tool_profile": "conversation_direct",
    "allowed_model_profile": "conversation_renderer",
    "latency_slo": "conversation_warm",
    "forbidden_claims": ["current_assignment", "memory_truth"],
}

PROFILE_DIRECT = {
    "profile_name": "conversation_direct",
    "profile_version": "v1",
    "tool_names": [],
    "tool_schema_hash": "none",
    "static_prefix_hash": "prefix-direct",
}


def test_provider_request_contract_carries_required_proof_fields() -> None:
    request = build_provider_request_contract(
        turn_contract=TURN_CONTRACT,
        profile_snapshot=PROFILE_DIRECT,
        context_budget={"context_budget_id": "budget:1"},
        answerability={
            "state": "answerable",
            "max_claim_strength": "memory_truth",
            "answer_type": "explicit_user_fact",
        },
        answer_evidence=[{"id": "profile:debug_marker", "value": "1231231X"}],
        prompt_snapshot="User private path /home/lauratom/private",
        brainstack_packet_id="brainstack:packet:1",
        regression_family="memory_answerable",
    )

    assert request.turn_contract_id == "turn:1"
    assert request.profile_snapshot_id.startswith("conversation_direct:v1:")
    assert request.brainstack_packet_id == "brainstack:packet:1"
    assert request.allowed_claim_strength == "memory_truth"
    assert request.answer_evidence_ids == ("profile:debug_marker",)
    assert request.redacted_prompt_snapshot_ref.startswith("redacted_prompt_snapshot:")
    assert request.no_hidden_full_tool_fallback is True


def test_response_contract_detects_forbidden_claim_wrong_tool_and_latency() -> None:
    request = build_provider_request_contract(
        turn_contract=TURN_CONTRACT,
        profile_snapshot=PROFILE_DIRECT,
        context_budget={"context_budget_id": "budget:1"},
        answerability={"state": "unanswerable", "max_claim_strength": "none", "answer_type": "none"},
        answer_evidence=[],
        regression_family="unsupported_abstain",
    )
    response = build_provider_response_contract(
        request,
        claims_made=["memory_truth"],
        answer_evidence_used=[],
        tool_calls_made=["terminal"],
        latency_slo_satisfied=False,
        degradation_policy_used="none",
    )

    assert response.contract_satisfied is False
    assert response.forbidden_claims_detected == ("memory_truth",)
    assert response.tool_call_violations == ("terminal",)
    assert set(response.failure_codes) == {
        "FORBIDDEN_CLAIM",
        "WRONG_TOOL_CALL",
        "PROVIDER_LATENCY_FAILURE",
    }


def test_external_action_audit_blocks_read_only_side_effects() -> None:
    request = build_provider_request_contract(
        turn_contract=TURN_CONTRACT,
        profile_snapshot=PROFILE_DIRECT,
        context_budget={"context_budget_id": "budget:1"},
        answerability={"state": "answerable", "max_claim_strength": "memory_truth"},
        regression_family="read_only_heavy",
        external_action_audit=build_external_action_audit(side_effect_tool_calls=["file_write"]),
    )
    response = build_provider_response_contract(
        request,
        latency_slo_satisfied=True,
        degradation_policy_used="none",
    )

    assert response.contract_satisfied is False
    assert response.side_effect_violations == ("file_write",)
    assert "UNEXPECTED_SIDE_EFFECT" in response.failure_codes


def test_hidden_full_tool_fallback_is_visible() -> None:
    bad_profile = {
        **PROFILE_DIRECT,
        "tool_names": ["terminal"],
    }
    request = build_provider_request_contract(
        turn_contract=TURN_CONTRACT,
        profile_snapshot=bad_profile,
        context_budget={"context_budget_id": "budget:1"},
        answerability={"state": "answerable", "max_claim_strength": "memory_truth"},
        regression_family="no_tools_hidden_prompt_audit",
    )
    response = build_provider_response_contract(
        request,
        latency_slo_satisfied=True,
        degradation_policy_used="none",
    )

    assert request.no_hidden_full_tool_fallback is False
    assert response.contract_satisfied is False
    assert response.failure_codes == ("PROFILE_SNAPSHOT_DRIFT",)


def test_tool_loader_legality_and_cleanup_contracts() -> None:
    schemas = [
        {"function": {"name": "brainstack_recall", "description": "Recall memory"}},
        {"function": {"name": "terminal", "description": "Run shell command"}},
    ]
    registry = build_tool_registry(schemas)
    loader = build_tool_loader_contract(
        "conversation_tools",
        ["brainstack_recall"],
        registry,
    )

    allowed, reason = evaluate_tool_load_request(loader, registry, "brainstack_recall")
    denied_cross_profile, cross_reason = evaluate_tool_load_request(loader, registry, "terminal")

    assert allowed is True
    assert reason == "ALLOWED"
    assert denied_cross_profile is False
    assert cross_reason == "TOOL_NOT_IN_ALLOWED_ENUM"
    assert loader.turn_end_cleanup_required is True
    assert loader.session_end_cleanup_required is True


def test_tool_loader_denies_config_disabled_gated_and_side_effect_without_approval() -> None:
    schemas = [{"function": {"name": "terminal", "description": "Run shell command"}}]
    registry = build_tool_registry(schemas)
    terminal = registry["terminal"]
    loader = build_tool_loader_contract("heavy_code", ["terminal"], registry)

    disabled_registry = {**registry, "terminal": replace(terminal, config_disabled=True)}
    gated_registry = {**registry, "terminal": replace(terminal, gated=True)}

    disabled_ok, disabled_reason = evaluate_tool_load_request(loader, disabled_registry, "terminal")
    gated_ok, gated_reason = evaluate_tool_load_request(loader, gated_registry, "terminal")
    side_effect_ok, side_effect_reason = evaluate_tool_load_request(loader, registry, "terminal")

    assert disabled_ok is False
    assert disabled_reason == "TOOL_CONFIG_DISABLED"
    assert gated_ok is False
    assert gated_reason == "TOOL_GATED_UNAVAILABLE"
    assert side_effect_ok is False
    assert side_effect_reason == "TOOL_SIDE_EFFECT_APPROVAL_REQUIRED"


def test_failure_taxonomy_contains_required_phase156_classes() -> None:
    assert {
        "CONTRACT_COMPILE_FAILURE",
        "BUDGET_FAILURE",
        "PROFILE_SNAPSHOT_DRIFT",
        "PROVIDER_LATENCY_FAILURE",
        "FORBIDDEN_CLAIM",
        "WRONG_TOOL_CALL",
        "ILLEGAL_TOOL_LOAD",
        "TOOL_CLEANUP_FAILURE",
        "SIDE_EFFECT_APPROVAL_BYPASS",
        "STALE_RESPONSE",
        "DUPLICATE_EVENT",
        "UNEXPECTED_SIDE_EFFECT",
        "MEMORY_ANSWERABILITY_MISMATCH",
    }.issubset(set(FAILURE_TAXONOMY))
