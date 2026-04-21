# Orbi Romance Webtoon — Spec + Continuity Contract Hardening

## Goal
`docs/plans/orbi-romance-webtoon-20260421`의 live fal 웹툰 파이프라인에서,
**사양(spec) 계약**과 **연속성(continuity) 계약**을 느슨한 관행이 아니라
검증 가능한 하드 계약으로 바꾸는 실행 계획을 만든다.

이번 Codex 작업은 구현이 아니라 **하드닝 계획 수립**이다.
필요하면 후속 구현용 PRD / test-spec까지 구체화한다.

## Current baseline
대표 렌더러:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`

현재 구조적 문제:
1. 패널마다 fresh text-to-image 호출만 함
   - continuity anchor / previous_panel / location_state / outfit_state 계약 없음
2. `panel_prompts.yaml`가 장면 요약 위주라 directed shot spec이 아님
3. `render_overlays()`는 고정형 caption/balloon placement만 사용
4. manifest는 생성 기록만 남기고 continuity/QC 선택 근거가 없음
5. live fal-only 계약은 생겼지만, quality hard gate는 약함

## What already exists
- `.omx/plans/prd-commercial-webtoon-quality-gap-improvement-20260421.md`
- `.omx/plans/test-spec-commercial-webtoon-quality-gap-improvement-20260421.md`

이전 계획은 넓은 품질 개선 로드맵이다.
이번에는 그중에서도 특히 **spec / continuity contract hardening**만 좁혀서,
실제 구현자가 바로 건드릴 수 있을 정도로 파일/스키마/검증 기준을 빡빡하게 정의해달라.

## What should be hardened
Codex should plan hardening for these contracts:

### A. Shot-spec contract
현재 `panel_prompts.yaml`를 대체 또는 v2 확장하는 계약
필수 후보 필드:
- `panel_id`
- `scene_id`
- `beat_purpose`
- `camera`
- `framing`
- `blocking`
- `gesture`
- `micro_expression`
- `prop_focus`
- `background_continuity`
- `negative_space_for_lettering`
- `must_show`
- `must_not_show`
- `continuity_refs`

중요:
- 더 이상 vague storyboard prose만으로는 통과하면 안 된다.
- missing required field면 validator에서 fail 나야 한다.

### B. Continuity contract
에피소드/시리즈 전반에서 캐릭터/공간 연속성을 강제하는 계약
필수 후보:
- `webtoon/continuity_bible.yaml`
- character invariants
- outfit states
- location states
- scene linkage
- previous_panel / next_panel relation
- continuity reference priorities
- allowed drift vs forbidden drift

중요:
- continuity는 prompt hint가 아니라 검증 가능한 데이터 계약이어야 한다.
- 후속으로 image-edit/reference chaining을 붙일 수 있게 설계되어야 한다.

### C. QC manifest contract
현재 live manifest는 너무 얇다.
하드닝해야 할 필드 후보:
- `candidate_count`
- `selected_candidate`
- `rejected_candidates`
- `identity_score`
- `continuity_score`
- `acting_score`
- `lettering_safety_score`
- `selection_reason`
- `rerender_reason`
- `policy_sanitized`
- `final_prompt_changed`

중요:
- first-pass output을 자동 채택하는 구조가 아니어야 한다.
- 최소한 선택 근거와 reject 근거가 남아야 한다.

### D. Validation contract
필수 validator가 체크해야 할 것:
- shot-spec required fields
- continuity_bible required fields
- scene/panel linkage consistency
- prompt anti-pattern (`storyboard` wording 등)
- visible characters completeness
- lettering safe zone presence
- manifest completeness
- longscroll/rendered panel existence
- schema version migration safety

## Deliverable requested from Codex
1. **좁혀진 hardening PRD**
   - spec hardening
   - continuity hardening
   - QC manifest hardening
   - validator hardening
2. **test-spec**
   - 구체적으로 어떤 테스트가 fail/pass를 가를지
3. **우선순위 실행 순서**
   - 무엇부터 구현해야 downstream churn이 적은지
4. **정확한 파일/경로 제안**
   - 예: 어떤 yaml/json/schema/test 파일을 어디에 둘지

## Constraints
- live fal-only 계약은 유지
- tail-less balloon contract는 건드리지 않음
- generic 개선안 말고 이 repo 경로 기준으로 구체적으로 써야 함
- shot-spec/continuity는 “있으면 좋다”가 아니라 “없으면 실패” 수준의 hard contract로 다뤄야 함

## Key question
Codex should answer:
- 어떤 스키마를 먼저 고정해야 renderer 변경이 덜 흔들리는가?
- continuity를 단순 prompt prose가 아니라 data contract로 만들려면 최소 필수 필드는 무엇인가?
- validator와 manifest를 어디까지 강제해야 실제 상용 품질 개선 루프가 돌아가기 시작하는가?
- 가장 안전한 구현 순서는 무엇인가?
