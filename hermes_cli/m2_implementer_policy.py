"""implementer_policy — write-role(implementer) 게이트 정책 규격 (M2-4)

라이브 role_gate.py의 ROLE_GATE_POLICIES / gate_recipe_for_assignee 구조에 **정합**하게
implementer 역할의 정책·recipe를 standalone 정의한다. (디스크 profile 생성·gateway register 안 함.)

라이브 대비 추가분(M2-6에서 적용할 변경):
  ① ROLE_GATE_POLICIES["implementer"] 등록 (kind="write")
  ② check_plan에 policy="write" 분기 추가 (라이브는 현재 "read-only"만)
  ③ _evaluate_gate_recipe에 신규 check 타입 3종(writes_match_manifest·codex_review_passed·proposal_inert)
     → m2_gate_checks 디스패치

본 모듈은 그 규격을 코드로 박제하고 매핑이 실제 callable로 해소됨을 검증 가능하게 한다.
"""
from __future__ import annotations

from hermes_cli import m2_gate_checks as gc  # noqa: E402

# 라이브 ROLE_GATE_POLICIES와 동일 shape({"kind","deliverable"})
IMPLEMENTER_POLICY = {
    "kind": "write",
    "deliverable": "proposal/MERGE_PROPOSAL.json",   # 워커 산출물 = 부모가 조립할 제안서 경로(선언 leaf)
}

# 라이브 gate_recipe와 동일 shape({"checks":[{"type":...}]})
# 3 M1 게이트(plan_gate·artifact_exists·no_child_cards) + 3 M2 신규 게이트.
M1_CHECK_TYPES = ("plan_gate", "artifact_exists", "no_child_cards")
M2_CHECK_TYPES = ("writes_match_manifest", "codex_review_passed", "proposal_inert")

# 신규 check 타입 → m2_gate_checks 디스패치(_evaluate_gate_recipe 확장 지점)
M2_CHECK_DISPATCH = {
    "writes_match_manifest": gc.writes_match_manifest,   # (phase2_result) -> (ok, detail)
    "codex_review_passed": gc.codex_review_passed,       # (verdict) -> (ok, detail)  [advisory]
    "proposal_inert": gc.proposal_inert,                 # (staged_files) -> {ok, hard_violations, review_flags}
}


def implementer_gate_recipe(deliverable: str | None = None) -> dict:
    """implementer 역할 gate_recipe. 라이브 build_*_gate_recipe와 동일 형식.
    plan_gate policy="write"(M2-6에서 check_plan에 추가) + 결정적 manifest/inert + advisory codex."""
    rel = deliverable or IMPLEMENTER_POLICY["deliverable"]
    return {
        "deliverable": rel,
        "checks": [
            {"type": "plan_gate", "policy": "write"},
            {"type": "artifact_exists", "path": rel},
            {"type": "no_child_cards"},
            {"type": "writes_match_manifest"},
            {"type": "codex_review_passed"},
            {"type": "proposal_inert"},
        ],
    }


def gate_recipe_for_assignee(assignee: str | None, deliverable: str | None = None):
    """라이브 gate_recipe_for_assignee의 write-role 확장. implementer면 recipe, 아니면 None."""
    if (assignee or "").strip() == "implementer":
        return implementer_gate_recipe(deliverable)
    return None
