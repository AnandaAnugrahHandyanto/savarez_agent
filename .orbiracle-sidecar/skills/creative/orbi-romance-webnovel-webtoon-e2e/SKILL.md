---
name: orbi-romance-webnovel-webtoon-e2e
description: Orbi 감성 기반 자극적 연애물을 5화 웹소설과 웹툰 패키지로 end-to-end 생성한다.
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [orbi, romance, webnovel, webtoon, storyboard, admissions]
---

# Orbi Romance Webnovel → Webtoon E2E

## When to use
- 사용자가 최근 오르비 감성을 반영한 연애물/혐관물/입시 로맨스를 요구할 때
- 단순 콘셉트가 아니라 **실제 5화 웹소설 + 웹툰 적응 산출물**을 원할 때
- 오르비 신호, 입결/반수/계약학과 고증, 웹툰 longscroll 산출을 한 번에 묶어야 할 때

## Mandatory retrieval
반드시 오르비 근거를 먼저 모은다.
- trending searches
- hot posts pages 1~2
- search clusters: 연애, 썸, 고백, 반수, 약대, 입결, 공부하면서 연애
- 대표 글 3~6개는 post 단위로 읽어서 신호를 확정한다.

## Emotional market synthesis
확정해야 할 것:
1. 지금 연애가 어떤 열등감과 결합되는지
2. 순애보다 혐관/비교/자존심 게임이 먹히는지
3. 입시·진로 축을 무엇으로 잡을지 (반수/계약학과/약대/입결)

## Story design contract
- 5화는 각각 클릭 훅이 있어야 한다.
- 매 화 엔딩은 들킴, 선긋기, 가짜 연애, 질투, 폭발 중 하나여야 한다.
- 현실 고증 실패 금지: 반수/장학/계약학과/약대 언어를 대충 쓰지 말 것.
- 오르비 톤은 설렘보다 수치심, 비교 우위, 외모/학벌 열등감이 앞서야 한다.

## File contract
프로젝트 패키지 예시:
- `00_signal.md`
- `01_series_bible.md`
- `deliverables/series_pitch.md`
- `novel/ep001.md` ... `ep005.md`
- `deliverables/webnovel_full.md`
- `webtoon/ep00N/scroll_plan.yaml`
- `webtoon/ep00N/panel_prompts.yaml`
- `webtoon/ep00N/lettering_script.yaml`
- `webtoon/ep00N/adaptation_notes.md`
- `webtoon/ep00N/render_queue.yaml`
- `renders/ep00N/ep00N_longscroll.png`
- `deliverables/manifest.json`

## Webtoon adaptation rules
- 페이지 만화가 아니라 세로 스크롤 블록으로 설계한다.
- 대사는 짧게, 독백은 캡션으로 축약한다.
- 학생증, 성적표, 채팅, 과외 프로필, 입결표 등 계급감 소품을 적극 사용한다.
- 생성 이미지 안에 한글 장문을 넣지 말고 후처리 전제 식자를 사용한다.
- 각 화 8~12개 블록 정도로 시작하면 storyboard fallback 검수가 쉽다.

## Render branch
- 기본이자 필수 경로는 fal + FLUX.2 Pro live lane이다.
- 이 e2e 웹툰 파이프라인은 storyboard fallback 없이 live fal 산출을 기준으로 완료 판정한다.
- 각 화는 실제 생성된 패널 PNG, 최종 longscroll PNG, live render manifest를 반드시 남긴다.
- live fal 렌더가 실패하면 작업은 미완료로 보고 원인 해결 후 다시 렌더한다.

## Verification checklist
- [ ] signal/bible/pitch 존재
- [ ] 5화 웹소설 본문 존재
- [ ] 합본 `webnovel_full.md` 존재
- [ ] 각 화의 scroll/prompt/lettering/render queue 존재
- [ ] longscroll PNG 존재
- [ ] 근거 글 ID/키워드가 signal 문서에 남아 있음
- [ ] render manifest 또는 파일 목록으로 산출물 경로를 다시 확인함

## Pitfalls
- 연애만 강조하고 반수/입결 압박을 약하게 쓰면 오르비 감성이 빠진다.
- 외모/자존심 열등감을 피상적으로 쓰면 흔한 캠퍼스물로 떨어진다.
- 웹툰 적응 시 문장을 너무 많이 살리면 스크롤 리듬이 죽는다.
- 계약학과를 막연한 명문 간판으로만 쓰면 현재 학생 감정과 어긋난다. 실제 취업 안정성, 장학 유지, 부모 설득 논리가 같이 보여야 한다.
