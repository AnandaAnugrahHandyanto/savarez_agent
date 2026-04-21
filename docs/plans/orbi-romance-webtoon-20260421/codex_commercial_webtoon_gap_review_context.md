# Orbi Romance Webtoon — Commercial Quality Gap Review Context

## Goal
최근 생성한 `docs/plans/orbi-romance-webtoon-20260421` live fal 웹툰 패키지를 기준으로,
왜 실제 상용 한국 웹툰보다 어색하게 보이는지 분석하고,
그 격차를 줄이기 위한 **실행 가능한 개선 계획**을 만든다.

이번 Codex 작업의 목적은 **구현이 아니라 분석 + 개선 계획 수립**이다.
필요하면 후속 구현용 PRD / test-spec 형태까지 정리해도 된다.

## Review target
대표 산출물:
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep001/ep001_longscroll.png`
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep003/ep003_longscroll.png`
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep005/ep005_longscroll.png`

전체 패키지:
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep001~ep005/*.png`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep001~ep005/generated_fal_live_manifest_ep00N.json`

## What already changed
- EP001~EP005는 이제 live fal 결과 기준으로 렌더됨.
- e2e 파이프라인은 live fal-only 계약으로 정렬됨.
- speech balloon tails는 tail-less 계약으로 고정됨.

## Hard evidence from current pipeline

### 1. 실제 렌더러가 패널마다 fresh text-to-image만 호출함
File:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`

Relevant facts:
- `86-106`: `fal_generate()`는 `fal-ai/flux-2-pro` 1회 호출만 수행
- continuity anchor / previous_panel / image_edit chaining 없음
- `235-252`: 패널 루프 안에서 매 패널 fresh generate 후 저장

Implication:
- 캐릭터 동일성, 의상, 얼굴, 배경 continuity가 컷마다 흔들릴 가능성이 높음
- 같은 장면 내 shot variation보다 “매번 새 그림”에 가까움

### 2. overlay가 매우 단순한 고정형 후처리임
Same file:
- `151-183`: `render_overlays()`
- caption은 상단 고정 박스
- balloon은 하단 고정 스택형 rounded rectangle
- saliency-aware placement, speaker-aware placement, panel-specific choreography 없음

Implication:
- 텍스트가 장면 연기에 붙지 않고 UI가 위아래에 얹힌 느낌이 남
- 상용 웹툰처럼 컷마다 감정 포인트를 비켜가는 정교한 식자가 아님

### 3. prompt 자체가 아직 storyboard 언어를 많이 품고 있음
Files:
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep003/panel_prompts.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep005/panel_prompts.yaml`

Observed pattern:
- `style_preset: clean_korean_webtoon_storyboard`
- positive anchor도 `clean Korean webtoon storyboard` 포함
- 다수 패널 prompt가 매우 요약형이고 generic함
- visible_characters가 장면 요구에 비해 빈약한 컷이 있음

Implication:
- 상용 웹툰 컷 설계가 아니라 “스토리보드적으로 설명된 장면”에서 멈출 가능성이 큼
- 포즈/카메라/행동 디테일이 부족해 모션과 acting이 밋밋해질 수 있음

### 4. episode당 컷 수와 컷 설계 밀도가 낮음
- 각 화는 8패널 정도
- scroll_plan도 큰 block 중심 구조

Implication:
- 상용 웹툰의 미세한 감정 분해, 리듬 조절, 리액션 삽입, 클로즈업-와이드-인서트 교차에 비해 밀도가 약함
- 장면이 “요약본”처럼 보일 가능성이 있음

### 5. content policy sanitize가 품질 손실을 만들 수 있음
Same renderer file:
- `58-83`: `sanitize_prompt_for_policy()`

Observed:
- 캐릭터명 / 약대 / 반수생 / 지방 국립대 등을 일반화
- EP004에선 실제로 sanitized prompt fallback이 사용됨

Implication:
- 민감 표현 회피는 되지만, 오르비 특유의 구체성·디테일·소품 정합성이 옅어질 수 있음
- 결과물이 generic campus romance처럼 흐려질 가능성 있음

## Likely commercial-quality failure modes to assess
Codex should explicitly assess these:
1. 캐릭터 동일성 부족
2. 컷 간 배경/공간 continuity 부족
3. acting/pose 다양성 부족
4. 카메라 프레이밍이 너무 비슷함
5. 컷별 정보량이 너무 균등해서 리듬이 밋밋함
6. overlay text가 장면에 붙지 않고 UI처럼 뜸
7. prompt가 장면 요약 수준이라 상용 연출 디테일이 약함
8. 오르비/입시 소품이 generic하게 표현되어 세계관 밀도가 떨어짐
9. 8컷 구조가 장면 분해에 비해 너무 거칠 수 있음
10. live fal-only로 바꿨지만 quality-control loop가 부족함

## Required output from Codex
Please produce:
1. **냉정한 품질 진단**
   - 상용 웹툰 대비 어색한 지점을 우선순위로 정리
   - “fact / inference / recommendation”을 구분해도 좋음
2. **개선 계획**
   - quick wins (1~2일)
   - medium fixes (이번 repo에서 바로 할 수 있는 구조개선)
   - bigger bets (anchor/edit chain, shot-spec IR, overlay upgrade 등)
3. 가능하면 `.omx/plans/`에
   - PRD 형식 개선안
   - test-spec 형식 검증안

## Constraints
- 지금 단계는 분석/계획이 목적이다. 대규모 코드 변경은 하지 말 것.
- 단, 계획 수립에 필요한 파일 스캔/검토는 적극적으로 해도 됨.
- 보고서는 이 repo와 현재 산출물 기준으로 구체적이어야 함.
- generic AI art criticism 말고, 이 파이프라인 구조와 산출물 계약에 연결된 지적이어야 함.

## Extra guidance
특히 아래 질문에 답해주면 좋다:
- 왜 이 결과가 “실제 상용 웹툰”보다 “잘 만든 AI 스토리보드”처럼 느껴지는가?
- 가장 ROI 높은 개선은 무엇인가?
- continuity, acting, shot variety, lettering 중 어디를 먼저 손대야 체감 개선폭이 큰가?
- 지금의 live fal-only 계약을 유지하면서도 품질을 올리는 가장 현실적인 다음 단계는 무엇인가?
