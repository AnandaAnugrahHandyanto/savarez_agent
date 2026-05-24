from __future__ import annotations

import builtins
import os
from copy import deepcopy
from pathlib import Path

from agent.memory_read_only_candidate_utils import (
    DEFAULT_FORBIDDEN_TRUE_KEYS,
    DEFAULT_PREVIEW_FIELDS,
    DEFAULT_WRITE_PREVIEW_FIELDS,
    READ_ONLY_POLICY_BASE,
    as_list,
    as_mapping,
    build_stable_digest,
    copy_fields,
    copy_source_lineage,
    deep_copy_mapping,
    merge_validation_errors,
    summarize_candidates,
    validate_forbidden_true_keys,
    validate_policy_flags,
    validate_preview_integrity,
    validate_required_keys,
    validate_write_preview_integrity,
)


def test_constants_match_current_safety_expectations():
    assert READ_ONLY_POLICY_BASE == {
        "read_only": True,
        "would_write_memory": False,
        "would_modify_config": False,
        "would_write_graph": False,
        "does_not_create_operation_events": True,
        "creates_real_proposals": False,
        "writes_proposal_files": False,
        "writes_operation_ledger": False,
        "writes_token_files": False,
        "writes_approval_audit": False,
        "invokes_real_token_write_executor": False,
        "implements_real_token_write_executor": False,
        "creates_executor_source_files": False,
    }
    assert DEFAULT_PREVIEW_FIELDS == (
        "approval_token_record_preview",
        "approval_audit_record_preview",
        "token_target_paths_preview",
        "proposal_record_preview",
        "operation_ledger_preview",
        "target_paths_preview",
    )
    assert DEFAULT_WRITE_PREVIEW_FIELDS == (
        "approval_token_write_payload_preview",
        "approval_audit_write_payload_preview",
        "token_write_target_paths_preview",
    )
    for key in (
        "token_issued",
        "created_real_proposal",
        "created_operation_event",
        "writes_operation_ledger",
        "writes_token_files",
        "writes_approval_audit",
        "invokes_real_token_write_executor",
        "implements_real_token_write_executor",
        "creates_executor_source_files",
        "creates_executor_tests",
    ):
        assert key in DEFAULT_FORBIDDEN_TRUE_KEYS


def test_as_mapping_handles_dict_and_non_dict_safely():
    source = {"nested": {"value": 1}}
    copied = as_mapping(source)

    assert copied == source
    assert as_mapping([("a", 1)]) == {}
    copied["nested"]["value"] = 2
    assert source["nested"]["value"] == 1


def test_as_list_handles_list_tuple_and_non_list_safely():
    source = [{"value": 1}]
    copied = as_list(source)
    copied[0]["value"] = 2

    assert source == [{"value": 1}]
    assert as_list(("a", "b")) == ["a", "b"]
    assert as_list("ab") == []
    assert as_list({"a": 1}) == []


def test_deep_copy_mapping_does_not_alias_nested_values():
    source = {"nested": {"items": [1, 2]}}
    copied = deep_copy_mapping(source)

    copied["nested"]["items"].append(3)

    assert source == {"nested": {"items": [1, 2]}}


def test_copy_fields_does_not_mutate_source():
    source = {"keep": {"nested": [1]}, "skip": True}
    original = deepcopy(source)

    copied = copy_fields(source, ("keep", "missing"))
    copied["keep"]["nested"].append(2)

    assert copied == {"keep": {"nested": [1, 2]}}
    assert source == original


def test_copy_source_lineage_copies_selected_keys_only():
    source = {
        "source_plan_id": "plan-1",
        "source_gate_id": "gate-1",
        "unrelated": "skip",
    }

    assert copy_source_lineage(source, ("source_plan_id", "source_gate_id")) == {
        "source_plan_id": "plan-1",
        "source_gate_id": "gate-1",
    }


def test_validate_required_keys_returns_missing_key_errors():
    assert validate_required_keys({"present": None}, ("present", "missing")) == [
        "missing_missing"
    ]


def test_validate_forbidden_true_keys_catches_forbidden_true_flags():
    candidate = {
        "writes_operation_ledger": True,
        "writes_token_files": False,
        "safe": True,
    }

    assert validate_forbidden_true_keys(candidate) == [
        "writes_operation_ledger_must_be_false"
    ]


def test_validate_policy_flags_catches_true_and_false_expectations():
    policy = dict(READ_ONLY_POLICY_BASE)
    policy["read_only"] = False
    policy["would_write_memory"] = True
    policy["does_not_create_operation_events"] = False

    assert validate_policy_flags(policy) == [
        "policy_read_only_must_be_true",
        "policy_would_write_memory_must_be_false",
        "policy_does_not_create_operation_events_must_be_true",
    ]


def test_validate_preview_integrity_catches_forbidden_true_flags_inside_previews():
    candidate = {
        "approval_token_record_preview": {
            "preview_only": True,
            "token_issued": True,
        },
        "proposal_record_preview": {
            "preview_only": False,
            "created_real_proposal": True,
        },
    }

    assert validate_preview_integrity(candidate) == [
        "approval_token_record_preview_token_issued_must_not_be_true",
        "proposal_record_preview_must_be_preview_only",
        "proposal_record_preview_created_real_proposal_must_not_be_true",
    ]


def test_validate_write_preview_integrity_catches_forbidden_true_flags_inside_write_previews():
    candidate = {
        "approval_token_write_payload_preview": {
            "preview_only": True,
            "written": True,
        },
        "token_write_target_paths_preview": {
            "preview_only": True,
            "writes_token_files": True,
        },
    }

    assert validate_write_preview_integrity(candidate) == [
        "approval_token_write_payload_preview_written_must_not_be_true",
        "token_write_target_paths_preview_writes_token_files_must_not_be_true",
    ]


def test_build_stable_digest_is_deterministic_and_ignores_volatile_keys():
    payload_a = {
        "candidate_id": "volatile-1",
        "stable": {"b": 2, "a": 1, "updated_at": "volatile"},
    }
    payload_b = {
        "stable": {"a": 1, "updated_at": "changed", "b": 2},
        "candidate_id": "volatile-2",
    }

    digest_a = build_stable_digest(
        "memory-read-only-candidate-utils:v0.1",
        payload_a,
        ignored_keys=("candidate_id", "updated_at"),
    )
    digest_b = build_stable_digest(
        "memory-read-only-candidate-utils:v0.1",
        payload_b,
        ignored_keys=("candidate_id", "updated_at"),
    )

    assert digest_a == digest_b
    assert digest_a.startswith("memory-read-only-candidate-utils:v0.1:")
    assert len(digest_a.rsplit(":", 1)[1]) == 16


def test_summarize_candidates_counts_total_status_type_and_block_type():
    candidates = [
        {"status": "valid", "candidate_type": "contract", "block_type": "preference"},
        {"status": "locked", "candidate_type": "contract", "block_type": "preference"},
        {"status": "valid", "candidate_type": "review", "block_type": "procedural_rules"},
    ]

    assert summarize_candidates(candidates, "status", type_key="candidate_type") == {
        "total": 3,
        "by_status": {"locked": 1, "valid": 2},
        "by_block_type": {"preference": 2, "procedural_rules": 1},
        "by_type": {"contract": 2, "review": 1},
    }


def test_merge_validation_errors_preserves_order_and_removes_duplicates():
    assert merge_validation_errors(
        ["missing_source", "policy_read_only_must_be_true"],
        ("missing_source", "writes_token_files_must_be_false"),
        ["policy_read_only_must_be_true"],
    ) == [
        "missing_source",
        "policy_read_only_must_be_true",
        "writes_token_files_must_be_false",
    ]


def test_helpers_do_not_write_files_or_create_directories(monkeypatch):
    def fail_write(*args, **kwargs):
        raise AssertionError("read-only candidate utilities must not write files")

    monkeypatch.setattr(builtins, "open", fail_write)
    monkeypatch.setattr(os, "mkdir", fail_write)
    monkeypatch.setattr(os, "makedirs", fail_write)
    monkeypatch.setattr(Path, "mkdir", fail_write)

    candidate = {
        "policy": READ_ONLY_POLICY_BASE,
        "approval_token_record_preview": {"preview_only": True},
        "approval_token_write_payload_preview": {"preview_only": True},
        "status": "valid",
        "block_type": "procedural_rules",
    }

    assert as_mapping(candidate)
    assert as_list([candidate])
    assert deep_copy_mapping(candidate)
    assert copy_fields(candidate, ("status",))
    assert copy_source_lineage(candidate, ("block_type",))
    assert validate_required_keys(candidate, ("status",)) == []
    assert validate_forbidden_true_keys(candidate) == []
    assert validate_policy_flags(candidate["policy"]) == []
    assert validate_preview_integrity(candidate) == []
    assert validate_write_preview_integrity(candidate) == []
    assert build_stable_digest("read-only", candidate)
    assert summarize_candidates([candidate], "status")["total"] == 1
    assert merge_validation_errors(["a"], ["a", "b"]) == ["a", "b"]


def test_inputs_are_not_mutated():
    candidate = {
        "policy": dict(READ_ONLY_POLICY_BASE),
        "approval_token_record_preview": {"preview_only": True, "created": False},
        "approval_token_write_payload_preview": {"preview_only": True, "written": False},
        "source_ids": ["source-1"],
        "status": "valid",
        "candidate_type": "contract",
        "block_type": "procedural_rules",
    }
    original = deepcopy(candidate)

    as_mapping(candidate)
    as_list([candidate])
    deep_copy_mapping(candidate)
    copy_fields(candidate, ("policy", "source_ids"))
    copy_source_lineage(candidate, ("source_ids",))
    validate_required_keys(candidate, ("policy", "status"))
    validate_forbidden_true_keys(candidate)
    validate_policy_flags(candidate["policy"])
    validate_preview_integrity(candidate)
    validate_write_preview_integrity(candidate)
    build_stable_digest("read-only", candidate, ignored_keys=("status",))
    summarize_candidates([candidate], "status", type_key="candidate_type")
    merge_validation_errors(["a"], ["b"])

    assert candidate == original
