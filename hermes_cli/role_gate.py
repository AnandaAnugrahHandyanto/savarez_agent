"""② 결정적 역할 게이트 — 역할 worker의 범위 위반을 결정적으로 차단.

①게이트(`kanban_db._evaluate_gate_recipe`)와 **동일 철학**: 제2 LLM 판단이
아니라 결정적 룰 재실행. 두 층으로 구성한다.

1. `check_plan()` — **실행 전(pre-execution)** worker 계획 텍스트를 결정적으로
   grep. read-only 역할 SOUL.md의 "계획 산출 규격"(kill switch·범위 태그·의존성)
   3요소를 검사. 자율 실행 전 강제하는 ② 본체.

2. `build_readonly_gate_recipe()` — **완료 시(at completion)** 라이브
   `complete_task()`가 평가하는 gate_recipe(dict). 포맷 독립·확실한 check
   타입(`artifact_exists`·`no_child_cards`)만 사용 — 산출물 노트 1개가
   실재하고 부수 child 카드를 만들지 않았음을 결정적으로 확인.

finding 형태는 ①게이트와 동일: ``{"type": str, "ok": bool, "reason": str|None}``.
read-only 역할의 worker 로그 패턴(worker_log_absent) 추가는 실제 worker 로그
샘플 확보 후 ARM 시 보강한다(추측 정규식 금지).
"""

from __future__ import annotations

import re
from typing import Any, Optional

# read-only 역할이 산출물로 쓸 수 있는 유일한 write 대상(SOUL.md와 일치).
READONLY_WRITE_ALLOWLIST = ("조사노트", "note", "research-note", "research_note")

# 역할(assignee) → 게이트 정책 레지스트리. 역할 worker 카드가 어느 경로로
# 생성되든(decompose·직접) 결정적 게이트를 자동 부착하는 단일 출처.
# 신규 역할은 여기에 1줄 추가한다.
ROLE_GATE_POLICIES: dict[str, dict[str, str]] = {
    "news-curator": {"kind": "read-only", "deliverable": "note.md"},
    "invest-watcher": {"kind": "read-only", "deliverable": "note.md"},
    "ops-monitor": {"kind": "read-only", "deliverable": "note.md"},
    # write-role (M2). The lane stays closed in R1 — dispatch is refused at
    # ``kanban_db._default_spawn`` while ``kanban.implementer_enabled`` is off.
    # Registering the policy here only makes the deterministic completion
    # gate (6 checks) attach automatically should the lane ever arm (R4+).
    "implementer": {"kind": "write", "deliverable": "proposal/MERGE_PROPOSAL.json"},
}

# write-role(implementer) 계획의 [write:대상] 태그가 가리켜도 되는 영역.
# m2_manifest_validate.ALLOWED_SUBDIRS 와 동기(단일 출처). plan 텍스트 사전
# 점검용 — 실제 강제는 implementer.sbpl literal + phase2 writes_match_manifest.
WRITE_SCOPE_ALLOWLIST = ("source_staging", "reviews", "output", "proposal")


def gate_recipe_for_assignee(
    assignee: Optional[str], deliverable: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Return the gate_recipe(dict) for a role assignee, or None.

    ``ROLE_GATE_POLICIES`` 에 등록된 역할이면 그 정책에 맞는 결정적 게이트
    recipe 를 만든다(현재 read-only → ②plan_gate + ①artifact_exists +
    no_child_cards). 미등록 assignee(default 등)는 None → 게이트 미부착.
    """
    name = (assignee or "").strip()
    policy = ROLE_GATE_POLICIES.get(name)
    if not policy:
        return None
    if policy.get("kind") == "read-only":
        return build_readonly_gate_recipe(deliverable or policy.get("deliverable") or "note.md")
    if policy.get("kind") == "write":
        # write-role(implementer) — 6 checks(M1 3종 + M2 3종). 단일 출처는
        # m2_implementer_policy.implementer_gate_recipe. lazy import 로 m2
        # 의존(gate_checks→manifest_validate)을 role_gate 로드 비용에서 분리.
        from hermes_cli import m2_implementer_policy as _ip
        return _ip.implementer_gate_recipe(
            deliverable or policy.get("deliverable")
        )
    return None

# 계획에 kill switch / 중단 조건이 선언됐는지 판정하는 키워드(한/영).
_KILL_SWITCH_RE = re.compile(r"kill\s*switch|중단\s*조건|중단한다|STOP\b|중단\b", re.IGNORECASE)
# 단계 범위 태그: [read] / [write:대상]
_SCOPE_TAG_RE = re.compile(r"\[\s*(read|write)\s*(?::\s*([^\]]+?))?\s*\]", re.IGNORECASE)
# 의존성/입력/산출물 경로 선언.
_DEPS_RE = re.compile(r"의존성|입력\b|산출물\s*경로|dependenc|input\b|output\s*path", re.IGNORECASE)


def check_plan(plan_text: str, policy: str = "read-only") -> dict[str, Any]:
    """worker 계획 텍스트를 결정적으로 검사한다(사전 ② 게이트).

    Returns ``{"passed": bool, "findings": [ {type, ok, reason}, ... ]}``.
    ``policy`` ∈ ``{"read-only", "write"}``. read-only(news-curator 등)는
    write 대상을 조사노트 1개로 제한하고, write(implementer)는 [write:대상]
    태그가 manifest 허용영역(source_staging·reviews·output·proposal) 안인지
    검사한다. **plan 텍스트 사전 점검일 뿐, 실제 강제는 완료 시 gate_recipe
    재실행 + sbpl + phase2 writes_match_manifest 가 한다.**
    """
    if policy not in ("read-only", "write"):
        return {
            "passed": False,
            "findings": [{"type": "policy", "ok": False, "reason": f"unsupported policy: {policy}"}],
        }

    text = plan_text or ""
    findings: list[dict[str, Any]] = []

    # 1) kill switch / 중단 조건 (정책 공통)
    has_kill = bool(_KILL_SWITCH_RE.search(text))
    findings.append({
        "type": "kill_switch",
        "ok": has_kill,
        "reason": None if has_kill else "계획에 kill switch/중단 조건 선언 없음",
    })

    # 2) 범위 선언 — 정책별 분기
    tags = _SCOPE_TAG_RE.findall(text)
    write_targets = [(t or "").strip() for kind, t in tags if kind.lower() == "write"]
    if policy == "read-only":
        # read-only: write 대상은 allowlist(조사노트)뿐
        illegal_writes = [
            t for t in write_targets
            if not any(allow in t for allow in READONLY_WRITE_ALLOWLIST)
        ]
        scope_ok = bool(tags) and not illegal_writes
        if not tags:
            scope_reason = "단계 범위 태그([read]/[write:...]) 없음"
        elif illegal_writes:
            scope_reason = f"허용되지 않은 write 대상: {illegal_writes} (read-only 산출물=조사노트 1개만)"
        else:
            scope_reason = None
        findings.append({"type": "scope_readonly", "ok": scope_ok, "reason": scope_reason})
    else:  # policy == "write"
        # write(implementer): [write:대상] ≥1 + 모든 write 대상이 manifest
        # 허용영역 안. 허용영역 밖 write 선언이 있으면 거부(fail-closed).
        illegal_writes = [
            t for t in write_targets
            if not any(allow in t for allow in WRITE_SCOPE_ALLOWLIST)
        ]
        scope_ok = bool(write_targets) and not illegal_writes
        if not write_targets:
            scope_reason = "write 역할 계획에 [write:대상] 태그 없음"
        elif illegal_writes:
            scope_reason = (
                f"manifest 허용영역 밖 write 대상: {illegal_writes} "
                f"(허용={list(WRITE_SCOPE_ALLOWLIST)})"
            )
        else:
            scope_reason = None
        findings.append({"type": "scope_write", "ok": scope_ok, "reason": scope_reason})

    # 3) 의존성/입력·산출물 경로 선언 (정책 공통)
    has_deps = bool(_DEPS_RE.search(text))
    findings.append({
        "type": "dependencies",
        "ok": has_deps,
        "reason": None if has_deps else "계획에 의존성/입력·산출물 경로 선언 없음",
    })

    return {"passed": all(f["ok"] for f in findings), "findings": findings}


def build_readonly_gate_recipe(deliverable_relpath: str) -> dict[str, Any]:
    """완료 시 라이브 `complete_task()` 가 평가할 gate_recipe(dict)를 만든다.

    read-only 역할(news-curator)용 결정적 완료 게이트:
      - `artifact_exists`: 산출물 조사노트가 workspace 안에 실재.
      - `no_child_cards`: 부수 child 카드를 만들지 않음(side-effect 0).

    두 check 타입 모두 라이브 `_evaluate_gate_recipe` 가 지원하며
    `_parse_gate_recipe` 검증을 통과한다. 반환 dict 를
    ``create_task(..., gate_recipe=<this>)`` 로 넘기면 배선된다(ARM 단계).
    """
    rel = (deliverable_relpath or "").strip()
    if not rel:
        raise ValueError("deliverable_relpath is required for read-only gate recipe")
    return {
        "checks": [
            # ② 계획 게이트(실행 전 제출, 완료 시 결정적 재실행). 우회 불가.
            {"type": "plan_gate", "policy": "read-only"},
            # ① 산출물 게이트.
            {"type": "artifact_exists", "path": rel},
            {"type": "no_child_cards"},
        ]
    }
