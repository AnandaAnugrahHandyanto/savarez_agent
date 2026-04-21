# Webtoon / Webnovel Pipeline Reordering Roadmap

> 목적: 현재 날짜별로 누적된 실험/산출물 구조를 정리해서, **파이프라인 정의 / 실제 실행 인프라 / 날짜별 실험 / 생성 아티팩트**를 분리한다.

## 1. 왜 지금 구조가 문제인가

현재 `docs/plans/orbi-*` 아래에는 아래 성격이 한 레벨에 섞여 있습니다.

1. **파이프라인 정의**
   - `00_signal.md`
   - `01_series_bible.md`
   - `novel/ep00N.md`
   - `webtoon/ep00N/scroll_plan.yaml`
   - `webtoon/ep00N/panel_prompts.yaml`
   - `webtoon/ep00N/lettering_script.yaml`
   - `webtoon/ep00N/render_queue.yaml`

2. **실행 인프라 / 러너 코드**
   - `render_webtoon_fal_live_episode.py`
   - `render_webtoon_fal_live.py`
   - `render_balloons.py`
   - `analyze_balloon_zones.py`
   - `storyboard_renderer.py`
   - `scripts/render_storyboard.py`

3. **날짜별 실험 메모 / Codex 컨텍스트**
   - `codex_*_context.md`
   - attachment iteration/replan 문서
   - VLM MVP 컨텍스트

4. **생성된 아티팩트**
   - `generated_fal_*`
   - `generated_fal_live_*`
   - `generated_fal_v3_ballooned_*`
   - `renders/ep00N/*.png`
   - `placement_manifest.json`
   - `generated_fal_live_manifest_*.json`

이 4종이 섞여 있어서,
- 어디가 canonical spec인지 흐려지고
- 어떤 러너가 현재 본선인지 모호해지고
- 날짜 폴더가 사실상 제품 라인처럼 보이고
- 실험 결과가 대표 산출물처럼 남습니다.

---

## 2. 목표 분리 원칙

앞으로는 아래 4계층을 분리합니다.

### A. Pipeline Spec
"무엇을 만들어야 하는가"

- 작품/에피소드 정의
- 웹소설 원문
- 웹툰 적응 스펙
- 렌더 큐
- 최종 deliverables manifest

### B. Runtime Infrastructure
"어떻게 실행하는가"

- fal live runner
- balloon analyzer / renderer
- storyboard fallback renderer
- 공통 유틸
- 검증 테스트

### C. Dated Experiments
"어떤 가설을 시험했는가"

- attachment iteration
- notail 정책 실험
- VLM observation MVP
- character consistency 컨텍스트
- Codex용 작업 지시/메모

### D. Generated Artifacts
"실행 결과로 무엇이 나왔는가"

- raw panel PNG
- ballooned PNG
- longscroll PNG
- placement manifest
- generation manifest
- contact sheet / comparison sheet

---

## 3. 목표 디렉터리 구조

```text
workspace/
├── pipeline/
│   ├── runtime/
│   │   ├── renderers/
│   │   │   ├── fal_live_episode.py
│   │   │   ├── storyboard_fallback.py
│   │   │   └── balloon_render.py
│   │   ├── analyzers/
│   │   │   └── balloon_zone_analyzer.py
│   │   ├── overlays/
│   │   │   ├── balloon_layout_utils.py
│   │   │   └── vlm_observation_loader.py
│   │   └── schemas/
│   │       ├── balloon_analysis_schema.md
│   │       └── manifest_contract.md
│   └── tests/
│       ├── test_balloon_pipeline_ep001.py
│       ├── test_balloon_pipeline_ep001_live.py
│       ├── test_tail_less_contracts.py
│       └── test_webtoon_prompt_schema_ep001.py
│
├── projects/
│   └── orbi-romance-20260421/
│       ├── 00_signal.md
│       ├── 01_series_bible.md
│       ├── deliverables/
│       │   ├── manifest.json
│       │   ├── series_pitch.md
│       │   └── webnovel_full.md
│       ├── novel/
│       │   ├── ep001.md
│       │   ├── ep002.md
│       │   ├── ep003.md
│       │   ├── ep004.md
│       │   └── ep005.md
│       └── webtoon/
│           ├── ep001/
│           │   ├── scroll_plan.yaml
│           │   ├── panel_prompts.yaml
│           │   ├── lettering_script.yaml
│           │   ├── adaptation_notes.md
│           │   └── render_queue.yaml
│           └── ep002~ep005/...
│
├── experiments/
│   ├── 20260417-balloon-baseline/
│   ├── 20260420-tail-less-policy/
│   ├── 20260420-codex-contexts/
│   └── 20260421-vlm-observation-mvp/
│
└── artifacts/
    └── orbi-romance-20260421/
        ├── ep001/
        │   ├── raw/
        │   ├── overlay/
        │   ├── final/
        │   └── manifests/
        ├── ep002/
        ├── ep003/
        ├── ep004/
        └── ep005/
```

---

## 4. 현재 폴더를 이 구조에 매핑하면

### Keep as canonical product source
- `docs/plans/orbi-romance-webtoon-20260421/00_signal.md`
- `docs/plans/orbi-romance-webtoon-20260421/01_series_bible.md`
- `docs/plans/orbi-romance-webtoon-20260421/novel/*.md`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/*.yaml`
- `docs/plans/orbi-romance-webtoon-20260421/deliverables/manifest.json`

→ 이 묶음은 장기적으로 `projects/orbi-romance-20260421/`로 들어가야 합니다.

### Keep as runtime baseline
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/render_webtoon_fal_live_episode.py`

→ 이 묶음은 장기적으로 `pipeline/runtime/` 아래로 이동해야 합니다.

### Move to experiments
- `docs/plans/orbi-trend-webnovel-webtoon-20260420/codex_*_context.md`
- `docs/plans/orbi-romance-webtoon-20260421/codex_*_context.md`
- `generated_fal_v3_ballooned_tuned`
- `generated_fal_v3_ballooned_attach2`
- `generated_fal_v3_ballooned_notail`
- `generated_fal_ui`
- `generated_fal_ui_minimal`
- `generated_fal_v3_p02_candidates`
- VLM 전용 산출/메모

### Move to artifacts
- `docs/plans/orbi-romance-webtoon-20260421/renders/ep00N/*`
- `docs/plans/orbi-romance-webtoon-20260421/webtoon/ep00N/generated_fal_live_*`
- `generated_fal_live_manifest_*.json`
- `placement_manifest.json`
- 각종 longscroll PNG

---

## 5. 실행 기준선도 같이 줄여야 함

현재 실행 러너가 겹치는 문제가 있습니다.

### Canonical runners
1. **live render runner**
   - 하나만 canonical 유지
   - 후보: `render_webtoon_fal_live_episode.py`

2. **balloon analyzer**
   - 하나만 canonical 유지
   - 후보: `analyze_balloon_zones.py`

3. **balloon overlay renderer**
   - 하나만 canonical 유지
   - 후보: `render_balloons.py`

4. **storyboard fallback**
   - 하나만 canonical 유지
   - `storyboard_renderer.py` vs `scripts/render_storyboard.py` 중 하나만 남김

### Experimental modes
- tail-less
- VLM-assisted placement
- attachment tuning
- policy workaround variants

이건 canonical runner가 아니라 옵션/실험으로 격리해야 합니다.

---

## 6. 바로 실행할 정리 순서

### Phase 1. 라벨링
- `20260421 romance` = canonical project
- `20260417 trend` = runtime/overlay baseline
- `20260420 live` = policy experiment reference
- `20260420 trend` = archive candidate

### Phase 2. 폴더 분리
- 새 상위 축 생성:
  - `pipeline/`
  - `projects/`
  - `experiments/`
  - `artifacts/`

### Phase 3. 코드 이동
- 실행 코드는 `pipeline/runtime/`
- 테스트는 `pipeline/tests/` 또는 기존 `tests/` 유지 + runtime 기준 참조 명확화
- 프로젝트별 spec은 `projects/<slug>/`

### Phase 4. 산출물 이동
- `renders/`, `generated_fal_*`, `generated_fal_live_*` 등은 `artifacts/<project>/<episode>/`로 이동
- 대표 산출물만 canonical manifest에 남김

### Phase 5. 실험 격리
- `codex_*_context.md`와 실험 산출은 `experiments/<date>-<theme>/`로 이동
- 대표 실행선과 분리

### Phase 6. contract 재작성
- `deliverables/manifest.json`는 project spec만 가리키고
- artifact manifest는 `artifacts/.../manifests/` 아래 별도 관리

---

## 7. verification gate

정리 후에는 아래를 만족해야 합니다.

1. **Project spec gate**
   - `00_signal -> 01_series_bible -> novel -> webtoon spec -> deliverables manifest` 연결

2. **Runtime gate**
   - balloon/live/tail-less 관련 테스트 통과

3. **Artifact gate**
   - episode별 raw / overlay / final / manifest 경로가 분리되어 존재

4. **Experiment gate**
   - 실험 결과는 canonical 산출물 경로를 오염시키지 않음

5. **Canonical uniqueness gate**
   - episode마다 대표 longscroll 1개, 대표 manifest 1개만 canonical

---

## 8. 최종 판단

가장 중요한 구조 변화는 이것입니다.

- `docs/plans/...` 중심의 날짜별 누적 구조를 끝내고
- **pipeline / projects / experiments / artifacts**의 4축으로 재배열한다

이렇게 해야:
- 파이프라인 정의가 다시 source of truth가 되고
- 실행 러너가 실험 메모와 분리되고
- 아티팩트가 제품 spec를 오염시키지 않고
- 날짜별 실험도 보존하면서 canonical lane을 잃지 않습니다.
