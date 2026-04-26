#!/usr/bin/env python3
"""Write Phase 152 observe-only context budget proof artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.context_budget import (  # noqa: E402
    SCHEMA_VERSION,
    ContextBudget,
    build_budget_proof,
    build_policy_static_prefix,
    compact_tool_response,
    compile_context_budget,
    make_context_item,
)


def _json_dump(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _load_snapshots(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    return data["profiles"]


def build_proof(snapshot_path: Path) -> dict[str, Any]:
    snapshots = _load_snapshots(snapshot_path)
    scenarios: dict[str, Any] = {}

    scenarios["conversation_direct_answerable"] = build_budget_proof(
        profile_name="conversation_direct",
        tool_schema_tokens_est=snapshots["conversation_direct"]["tool_schema_tokens_est"],
        answerability={
            "state": "answerable",
            "max_claim_strength": "memory_truth",
            "answer_type": "explicit_user_fact",
            "reason_code": "AUTHORITATIVE_MEMORY_EVIDENCE",
        },
        answer_evidence=[{"id": "profile:debug_marker", "value": "1231231X"}],
        forbidden_claims=["external_verification", "current_assignment_without_typed_authority"],
        current_user_message="Mi volt a debug markerem?",
        supporting_context=["prior assistant residue 1231231Y should not outrank answer evidence"],
        diagnostics=["candidate trace is available via inspect_ref, not full prompt dump"],
    )

    scenarios["conversation_tools_compact_response"] = build_budget_proof(
        profile_name="conversation_tools",
        tool_schema_tokens_est=snapshots["conversation_tools"]["tool_schema_tokens_est"],
        answerability={
            "state": "unanswerable",
            "max_claim_strength": "none",
            "answer_type": "none",
            "reason_code": "NO_SUPPORTED_MEMORY_TRUTH",
        },
        answer_evidence=[],
        forbidden_claims=["memory_truth", "lifetime_certainty"],
        current_user_message="Mi a zeta omega durable keyem?",
        supporting_context=["supporting context only, not answer truth"] * 40,
        recent_history=["recent chat noise"] * 40,
        diagnostics=["backend health ok; candidates omitted in model-facing prompt"] * 20,
    )

    scenarios["overflow_minimum_viable_context"] = build_budget_proof(
        profile_name="conversation_direct",
        tool_schema_tokens_est=0,
        answerability={
            "state": "answerable",
            "max_claim_strength": "bounded_event",
            "answer_type": "conversation_event",
            "reason_code": "RECORDED_SCOPE_EVENT",
        },
        answer_evidence=[
            {
                "id": "event:turn-42",
                "event_type": "user_turn_event",
                "preview": "markeres dolgot kérdezted",
            }
        ],
        forbidden_claims=["lifetime_certainty", "durable_user_fact"],
        current_user_message="Kérdeztem már ezt?",
        supporting_context=["noise " * 600] * 10,
        recent_history=["history " * 600] * 10,
        diagnostics=["/home/lauratom/private/path sk-abcdef1234567890"] * 3,
    )
    tiny_budget = ContextBudget(
        total_input_budget_tokens=25,
        static_system_budget_tokens=10,
        tool_schema_budget_tokens=0,
        memory_packet_budget_tokens=5,
        recent_history_budget_tokens=0,
        safety_margin_tokens=5,
    )
    tiny_static_prefix = build_policy_static_prefix(
        profile_name="conversation_direct",
        tool_profile="conversation_direct",
        max_claim_strength="memory_truth",
        latency_mode="conversation_warm",
        forbidden_claims=["external_verification"],
    )
    tiny_items = [
        make_context_item(
            "answerability",
            "answerability",
            '{"state":"answerable","max_claim_strength":"memory_truth"}',
            tokens_est=15,
        ),
        make_context_item(
            "answer_evidence:0",
            "answer_evidence",
            '{"id":"profile:debug_marker","value":"1231231X"}',
            tokens_est=15,
        ),
        make_context_item("supporting:0", "supporting_context", "drop this supporting context", tokens_est=15),
    ]
    tiny_assembly = compile_context_budget(
        profile_name="conversation_direct",
        budget=tiny_budget,
        static_prefix=tiny_static_prefix,
        tool_schema_tokens_est=0,
        items=tiny_items,
    )
    tiny_selected = {item.item_id for item in tiny_assembly.selected_items}
    tiny_protected = {item.item_id for item in tiny_items if item.protected}
    scenarios["minimum_viable_context_forced"] = {
        "schema": SCHEMA_VERSION,
        "profile_name": "conversation_direct",
        "budget": tiny_budget.to_dict(),
        "assembly": tiny_assembly.to_dict(),
        "protected_ids": sorted(tiny_protected),
        "protected_preserved": tiny_protected.issubset(tiny_selected),
        "tool_schema_budget_zero": True,
        "provider_cache_observable": False,
    }

    tool_response = compact_tool_response(
        "brainstack_recall",
        {
            "memory_answerability": {
                "state": "answerable",
                "max_claim_strength": "memory_truth",
            },
            "answer_evidence": [{"id": "profile:debug_marker", "value": "1231231X"}],
            "supporting_context": ["large support " * 1000],
            "forbidden_claims": ["external_verification"],
        },
        cap_tokens=900,
        inspect_ref="inspect://phase152/brainstack_recall/debug-marker",
        continuation_token="phase152-continuation",
    )

    protected_ok = all(scenario["protected_preserved"] for scenario in scenarios.values())
    return {
        "schema": SCHEMA_VERSION,
        "source_snapshot": str(snapshot_path),
        "scenarios": scenarios,
        "tool_response_envelopes": {
            "brainstack_recall": tool_response.to_dict(),
        },
        "verdict": {
            "passed": protected_ok
            and snapshots["conversation_direct"]["tool_schema_tokens_est"] == 1
            and snapshots["conversation_tools"]["tool_schema_tokens_est"] <= 1500,
            "protected_context_preserved": protected_ok,
            "minimum_viable_context_exercised": any(
                scenario["assembly"]["minimum_viable_context_used"]
                for scenario in scenarios.values()
            ),
            "conversation_direct_effective_tool_schema_zero": snapshots["conversation_direct"]["tool_count"] == 0,
            "conversation_tools_compact_schema_tokens": snapshots["conversation_tools"]["tool_schema_tokens_est"],
            "provider_cache_required": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    proof = build_proof(Path(args.snapshot))
    _json_dump(Path(args.output), proof)
    print(
        json.dumps(
            {
                "schema": proof["schema"],
                "passed": proof["verdict"]["passed"],
                "conversation_tools_tokens": proof["verdict"]["conversation_tools_compact_schema_tokens"],
                "provider_cache_required": proof["verdict"]["provider_cache_required"],
            },
            sort_keys=True,
        )
    )
    return 0 if proof["verdict"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
