# implementer 프로파일 규격 (M2-4, 설계 — 디스크 profile·register 안 함)

> 라이브 `role_gate.py` 구조에 정합. 코드 박제 = `implementer_policy.py`, 인격 = `SOUL_implementer_draft.md`.
> 실제 디스크 profile 생성·gateway register·ROLE_GATE_POLICIES 라이브 등록은 **M2-6 이후 사람 승인**.

## 1. ROLE_GATE_POLICIES 등록 항목 (라이브 추가분)
```python
ROLE_GATE_POLICIES["implementer"] = {"kind": "write", "deliverable": "proposal/MERGE_PROPOSAL.json"}
```
- 기존 read-only 3역할(news-curator·invest-watcher·ops-monitor)과 같은 dict shape. `kind="write"`가 신규.

## 2. gate_recipe (6 checks = M1 3종 + M2 3종)
```json
{"checks": [
  {"type": "plan_gate", "policy": "write"},
  {"type": "artifact_exists", "path": "proposal/MERGE_PROPOSAL.json"},
  {"type": "no_child_cards"},
  {"type": "writes_match_manifest"},
  {"type": "codex_review_passed"},
  {"type": "proposal_inert"}
]}
```
- 완료 판정 = 6종 전부 pass. 단 `codex_review_passed`는 **advisory** → 결정적 2종(writes_match_manifest·
  proposal_inert)이 먼저 통과해야 함(`m2_gate_checks.evaluate_m2_done`이 강제). PASS 단독 done 불가.

## 3. M2-6 라이브 배선 시 필요한 변경 3곳 (이번 범위 밖, 설계만)
1. **`role_gate.py`**: `ROLE_GATE_POLICIES`에 implementer 등록 + `gate_recipe_for_assignee`가
   kind="write" → write recipe(위 §2) 반환 분기.
2. **`role_gate.check_plan`**: `policy="write"` 분기 추가(현재 "read-only"만). write 정책 =
   kill switch + 범위태그 `[write:대상]`이 선언 manifest 안인지 + 의존성 선언 검사.
3. **`kanban_db._evaluate_gate_recipe`**: 신규 check 타입 3종 디스패치 추가
   (`writes_match_manifest`→phase2 결과, `codex_review_passed`→verdict, `proposal_inert`→staged_files).
   디스패치 매핑 = `implementer_policy.M2_CHECK_DISPATCH`. 기존 check·기존 카드 무영향(additive).

## 4. write 경계 (SOUL + OS 샌드박스 이중)
| 경계 | 강제 수단 |
|---|---|
| write = 선언 manifest leaf만 | implementer.sbpl literal MW_n + phase2 writes_match_manifest |
| LLM = 부모 template만 | parent_proxy template-only + credential 격리 |
| 산출물 = 제안서까지(merge·배포·실행 금지) | proposal_inert + 마일3 사람 게이트 |
| 실데이터 read 금지 | implementer.sbpl 실홈 deny + synth allow-back |
| network = 프록시 소켓만 | implementer.sbpl deny network* + unix-socket 1개 |

## 5. 본 범위(M2-4)에서 한 것 / 안 한 것
- 한 것: 정책·recipe·디스패치 코드 박제(`implementer_policy.py`) + SOUL 초안 + 본 규격 + 매핑 검증 테스트.
- 안 한 것: 디스크 `~/.hermes/profiles/implementer/` 생성, gateway register, 라이브 role_gate/kanban_db 수정.
