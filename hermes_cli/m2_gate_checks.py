"""m2_gate_checks — write-role 완료 gate 신규 check 3종 (M2-3, DESIGN_v4 §6 / DESIGN_M2 §3)

마일스톤1 role_gate/_evaluate_gate_recipe 패턴의 standalone 확장. 라이브 kanban_db 무수정.
M1 gate(plan_gate·artifact_exists·no_child_cards)에 더해 write-role에 다음 3종을 추가한다.

1. writes_match_manifest (결정적)  — M2-2 phase2 산출물 소비. 선언 밖 변경·삭제 0이어야 pass.
2. codex_review_passed (advisory)  — verdict∈{PASS,CONDITIONAL_PASS} ∧ High 0. **PASS 단독 done 금지.**
3. proposal_inert (안전망, 1차 아님) — staged 파일이 자동실행/부수효과/권한상승 마커를 포함하지 않아야.

각 check = (ok: bool, detail). 합성은 evaluate_m2_done(): 결정적 2종 필수 + advisory 동반.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from hermes_cli import m2_manifest_validate as mv  # noqa: E402  (FORBIDDEN_CORE_FRAGMENTS 재사용)


# --------------------------------------------------------------------------
# 1. writes_match_manifest (결정적)
# --------------------------------------------------------------------------
def writes_match_manifest(phase2_result: dict):
    """M2-2 phase2_verify 결과 소비. 선언 밖 변경·삭제 0일 때만 pass."""
    if not isinstance(phase2_result, dict):
        return False, "phase2 결과 없음"
    if phase2_result.get("ok"):
        return True, f"changed={len(phase2_result.get('changed', []))} 전부 선언 내"
    return False, "; ".join(phase2_result.get("reasons") or ["manifest 불일치"])


# --------------------------------------------------------------------------
# 2. codex_review_passed (advisory — 단독 done 금지)
# --------------------------------------------------------------------------
def codex_review_passed(verdict: dict):
    """verdict = {"verdict": "PASS"|"CONDITIONAL_PASS"|"BLOCKED", "high": int}.
    advisory: 이 check가 pass해도 결정적 check 없이 done 불가(evaluate_m2_done이 강제).

    Codex M2 #6: malformed high는 **fail-closed**(0으로 뭉개지 않음). verdict 미상도 거부.
    provenance 계약: verdict는 **부모가 Codex를 직접 실행해 산출**해야 하며 워커가 못 만든다(M2-6 배선 규약)."""
    if not isinstance(verdict, dict):
        return False, "codex verdict 없음/형식오류"
    v = verdict.get("verdict")
    raw_high = verdict.get("high", 0)
    try:
        high = int(raw_high if raw_high is not None else 0)
    except (TypeError, ValueError):
        return False, f"codex high 파싱불가({raw_high!r}) → fail-closed"
    if v not in ("PASS", "CONDITIONAL_PASS"):
        return False, f"codex verdict={v!r} (PASS/CONDITIONAL 아님)"
    if high > 0:
        return False, f"codex High {high}건 미해소"
    return True, f"advisory-pass(verdict={v}, high=0)"


# --------------------------------------------------------------------------
# 3. proposal_inert (안전망) — 자동실행/부수효과/권한상승 마커 스캔
# --------------------------------------------------------------------------
# import/실행 시 부수효과 파일 (manifest basename 거부의 2차 방어)
_SIDE_EFFECT_NAMES = frozenset({
    "conftest.py", "sitecustomize.py", "usercustomize.py", "__init__.py",
    ".pth", "setup.py", "manage.py", ".envrc", "makefile",
})
_SIDE_EFFECT_SUFFIXES = (".pth",)
_SHEBANG = re.compile(r'^\s*#!\s*/')
# HARD(차단): inert 제안에 있을 이유 없는 동적 코드실행/빌트인 조작 마커.
#   Codex M2 #1: subprocess만 flag로 두고 evaluate가 무시 → done_eligible 통과 + 난독화
#   (globals()['__builtins__']…getattr) 전혀 미탐지 사고. 강한 exec-injection 마커를 hard로.
_HARD_TOKENS = [
    ("eval(", re.compile(r'\beval\s*\(')),
    ("exec(", re.compile(r'\bexec\s*\(')),
    ("__import__(", re.compile(r'\b__import__\s*\(')),
    ("compile(", re.compile(r'\bcompile\s*\(')),
    ("__builtins__", re.compile(r'__builtins__')),       # 난독 import 우회 마커
    ("base64-decode", re.compile(r'\bbase64\.\w*decode')),
    ("codecs-decode", re.compile(r'\bcodecs\.decode')),
    # Codex M2 r2 #High1: importlib.import_module(...).system / 내성(introspection) 우회
    ("importlib", re.compile(r'\bimportlib\b')),
    ("import_module(", re.compile(r'\bimport_module\s*\(')),
    (".system(", re.compile(r'\.system\s*\(')),          # 임의 객체.system(
    (".popen(", re.compile(r'\.popen\s*\(')),
    ("__class__", re.compile(r'__class__')),
    ("__subclasses__", re.compile(r'__subclasses__')),
    ("__bases__", re.compile(r'__bases__')),
    ("__globals__", re.compile(r'__globals__')),
    ("vars(", re.compile(r'\bvars\s*\(')),
    ("marshal", re.compile(r'\bmarshal\b')),
]
# 검토 플래그(soft): 정상 코드에도 등장 가능 → 차단 아니나 **반드시 사람검토 표시**(evaluate가 surface).
_SOFT_TOKENS = [
    ("os.system", re.compile(r'\bos\.system\s*\(')),
    ("subprocess", re.compile(r'\bsubprocess\.')),
    ("os.popen", re.compile(r'\bos\.popen\s*\(')),
    ("ctypes", re.compile(r'\bctypes\b')),
    ("pickle.loads", re.compile(r'\bpickle\.loads?\s*\(')),
    ("marshal.loads", re.compile(r'\bmarshal\.loads?\s*\(')),
    ("getattr(", re.compile(r'\bgetattr\s*\(')),         # 난독 속성접근
    ("globals()", re.compile(r'\bglobals\s*\(\s*\)')),
    ("setattr(", re.compile(r'\bsetattr\s*\(')),
]


def proposal_inert(staged_files):
    """staged_files = 검증할 절대경로 리스트(권장: 부모 capture 본; M2-5 High2 참조). 각 파일 스캔.
    hard_violations(차단): 부수효과 파일명·exec-bit·shebang·forbidden core fragment·동적실행 마커·하드링크.
    review_flags(보고): 위험 토큰. ok = hard_violations 없음.
    ⚠️ 정적 스캔은 완전한 난독화 방어 불가 → 최종 안전망은 마일3 사람 merge 게이트. 본 scanner는 그 입력."""
    hard, flags = [], []
    for p in staged_files or []:
        name = os.path.basename(p)
        ncf = name.casefold()
        if ncf in _SIDE_EFFECT_NAMES or ncf.endswith(_SIDE_EFFECT_SUFFIXES):
            hard.append(f"부수효과 파일명: {name}")
        try:
            st = os.lstat(p)
            if st.st_nlink > 1:                          # Codex M2 #3: 하드링크 산출물 거부
                hard.append(f"하드링크(st_nlink={st.st_nlink}): {name}")
            if st.st_mode & 0o111:
                hard.append(f"exec-bit: {name}")
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _SHEBANG.search(text):
            hard.append(f"shebang 주입: {name}")
        low = text.casefold()
        for frag in mv.FORBIDDEN_CORE_FRAGMENTS:
            if frag in low:
                hard.append(f"위험경로 fragment '{frag}': {name}")
        for label, pat in _HARD_TOKENS:
            if pat.search(text):
                hard.append(f"동적실행 마커 {label}: {name}")
        for label, pat in _SOFT_TOKENS:
            if pat.search(text):
                flags.append(f"{label}: {name}")
    return {"ok": not hard, "hard_violations": sorted(set(hard)),
            "review_flags": sorted(set(flags))}


# --------------------------------------------------------------------------
# 합성 — write-role done 판정 (결정적 2종 필수 + advisory 동반)
# --------------------------------------------------------------------------
def evaluate_m2_done(*, phase2_result: dict, codex_verdict: dict, staged_files):
    """3종 종합. **codex는 advisory라 단독 done 불가** — writes_match_manifest∧proposal_inert(결정적)가
    먼저 통과해야 하고, codex_review_passed까지 모두 pass일 때만 done_eligible(=MERGE_PROPOSAL 생성).
    실제 merge·배포는 마일스톤3 사람 게이트(본 함수 범위 밖)."""
    wmm_ok, wmm_d = writes_match_manifest(phase2_result)
    crp_ok, crp_d = codex_review_passed(codex_verdict)
    pi = proposal_inert(staged_files)
    # Codex M2 #7: 변경 0건은 done 아님(빈 MERGE_PROPOSAL 차단). 실제 staged 변경 ≥1 필수.
    changed = (phase2_result or {}).get("changed") or []
    has_change = len(changed) >= 1 and len(list(staged_files or [])) >= 1
    deterministic_ok = wmm_ok and pi["ok"] and has_change
    done_eligible = deterministic_ok and crp_ok
    # Codex M2 #1 + r2: review_flags를 숨기지 않고 surface.
    # **write-role 제안은 정적 스캔이 코드 안전을 보증 못 함**(importlib 등 우회 무한) →
    # staged 코드가 있으면 needs_human_review는 **항상 True**(merge는 마일3 사람 게이트).
    # proposal_inert hard는 done_eligible을 차단, soft flag는 사람이 볼 항목을 enrich.
    review_flags = pi.get("review_flags") or []
    needs_human_review = bool(staged_files) or bool(review_flags) or not crp_ok
    reasons = []
    if not has_change:
        reasons.append("변경 0건(빈 제안) → done 불가")
    if not wmm_ok:
        reasons.append(f"writes_match_manifest 실패: {wmm_d}")
    if not pi["ok"]:
        reasons.append(f"proposal_inert hard: {pi['hard_violations']}")
    if not crp_ok:
        reasons.append(f"codex: {crp_d}")
    return {
        "done_eligible": done_eligible,
        "deterministic_ok": deterministic_ok,
        "needs_human_review": needs_human_review,
        "review_flags": review_flags,
        "reasons": reasons,
        "checks": {
            "writes_match_manifest": (wmm_ok, wmm_d),
            "codex_review_passed": (crp_ok, crp_d),
            "proposal_inert": (pi["ok"], pi),
        },
        "note": ("codex_review_passed=advisory; 결정적 2종(writes_match_manifest·proposal_inert)+변경≥1 "
                 "선통과 필수. review_flags 있으면 needs_human_review. merge는 마일3 사람 게이트."),
    }
