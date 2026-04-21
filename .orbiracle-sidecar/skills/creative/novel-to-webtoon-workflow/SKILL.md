---
name: novel-to-webtoon-workflow
description: Integrate webtoon adaptation as a downstream workflow on top of an existing webnovel studio (especially awesome-novel-studio) instead of treating it as a separate end-to-end product.
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [webnovel, webtoon, adaptation, workflow, awesome-novel-studio, orbi]
---

# Novel to Webtoon Workflow

Use when the user wants to make webtoons from an existing webnovel workflow and already has a functioning novel pipeline.

## When to use
- The user already has a webnovel pipeline such as `awesome-novel-studio`
- The user asks for a webtoon workflow "as one of your workflows"
- The user does **not** want a separate standalone product first
- The team already has strong front-end novel stages (topic selection, proposal, design, writing, polish)

## Core decision
Do **not** start by searching for a perfect all-in-one open-source webtoon system.
Do **not** fork the novel workflow into a separate product too early.

Instead, treat webtoon production as a **downstream adaptation layer** attached to the existing novel pipeline.

## Why this approach works
In practice, the strong part of the current system is usually already built:
- topic selection
- proposal generation
- big design
- small design
- episode writing
- polish

The actual missing layer is usually:
- scroll-block adaptation
- shot planning
- dialogue compression
- lettering prep
- rendering handoff
- export slicing for vertical-scroll platforms

So the right move is to preserve the novel workflow and add a webtoon adaptation lane behind it.

## Recommended command chain
Existing novel lane:
1. `/orbi-topic-selection`
2. `/propose`
3. `/design-big`
4. `/design-small`
5. `/create`
6. `/polish`

Then add the webtoon lane:
7. `/adapt-webtoon`
8. `/webtoon-pack`
9. `/webtoon-render`
10. `/webtoon-letter`
11. `/webtoon-export`

## First thing to build
Build `/adapt-webtoon` first.

Reason:
- it reuses all existing novel outputs
- it defines the stable intermediate representation for webtoon production
- it makes later render/letter/export stages much easier to attach

## What `/adapt-webtoon` should do
### Inputs
- proposal
- bootstrap
- character sheet
- plot-hook guide
- target episode text

### Outputs
For each episode, generate:
- scroll-block plan
- cut/shot/emotion breakdown
- dialogue compression draft
- spacing / drop / cliff block plan
- image-generation prompt package
- lettering script draft

## Recommended output files
Under the project directory, store adaptation outputs like:
- `projects/<slug>/webtoon/ep001/scroll_plan.yaml`
- `projects/<slug>/webtoon/ep001/panel_prompts.yaml`
- `projects/<slug>/webtoon/ep001/lettering_script.yaml`

## Modeling rule
Do not model webtoon primarily as page comics or rigid panels.
Model it as:
- scroll block
- sequence
- spacer
- reveal beat
- dialogue block
- SFX block

This matters because Korean-style vertical scroll depends more on rhythm, drop, viewport tension, and pacing than on page-grid layout.

## Implementation phases
### Phase A — MVP
- add `/adapt-webtoon`
- add `references/webtoon-scroll-rhythm.md`
- run one episode adaptation demo

### Phase B — semi-automated production
- add `/webtoon-pack`
- define image-generation backend handoff format
- add structured asset packaging

## Image-generation backend decision
When the user asks for the **image-generation tool itself**, do **not** answer with ComfyUI first.
ComfyUI is primarily a workflow builder / orchestration surface, not the cloud image engine.

For a team that will orchestrate locally and only needs the best cloud image-generation backend for webtoon production, the default recommendation is:
- **BFL FLUX.2 Pro** on **fal** as the confirmed production backend

Why:
- BFL positions FLUX.2 as the recommended model family for text-to-image and image editing
- the docs emphasize **multi-reference image editing** and practical editing-style workflows
- this matches webtoon production better than one-shot aesthetic generators because the real problem is repeated character/control editing across many cuts
- live repo testing confirmed a workable split between:
  - `fal-ai/flux-2-pro` for anchors / fresh scene-establishing frames
  - `fal-ai/flux-2-pro/edit` for same-scene chained continuity work

Secondary recommendation:
- **Recraft API** when the user values style control, design assets, promo art, thumbnails, or strongly guided visual branding
- but for main cut production, fal + FLUX.2 Pro is the stronger default here

Pricing / sourcing heuristic:
- if direct FLUX.2 pricing is not immediately available, check official BFL docs plus provider routes like fal or Replicate
- verified public fal listing for `fal-ai/flux-2-pro` showed image pricing tied to megapixels, but treat live pricing as mutable and re-check before promising cost
- do **not** assume 'free API' availability; in practice, testing may be cheap, but production-free image APIs are not reliable

## Important distinction
If the user says:
- “저건 워크플로우 빌더지 이미지 생성쪽이 아닌데?”

that means they are distinguishing between:
- orchestration/runtime layer
- actual cloud image-generation service/model

In that case, answer with the **generation backend** first (currently FLUX.2 Pro), and only mention ComfyUI or local scripts as the orchestration layer if relevant.

### Phase C — output lane
- add `/webtoon-letter`
- add `/webtoon-export`
- add platform-specific long-image slicing rules

## Suggested supporting files
- `skills/adapt-webtoon/SKILL.md`
- `skills/webtoon-pack/SKILL.md`
- `skills/webtoon-render/SKILL.md`
- `skills/webtoon-letter/SKILL.md`
- `skills/webtoon-export/SKILL.md`
- `references/webtoon-scroll-rhythm.md`
- `references/webtoon-shot-taxonomy.md`
- `references/webtoon-lettering-rules-ko.md`
- `templates/webtoon-scene-plan.yaml`
- `templates/webtoon-episode-package.yaml`

## Orbi / admissions-specific note
For Orbi-grounded work, inherit the same realism constraints from the novel lane.
Do not loosen factuality during adaptation.
Keep:
- admissions timing correctness
- exam / route / department terminology correctness
- pressure from comparison, ranking, and status movement

## Practical production note from later EP001 runs
Once a webtoon lane reaches the split stage of:
- analysis artifact
- lettering script
- renderer
- rendered manifest/output

then bugfixes should usually target the **narrow failing contract**, not restart the whole adaptation stack.

Examples that proved important:
- text overflow in speech balloons was a renderer safe-box contract bug, not a story adaptation bug
- missing speech tails after a later patch was a renderer predicate bug, not an analyzer/schema bug

Operationally, this means:
- keep adaptation outputs stable
- diagnose whether the failing surface is analyzer, renderer, or artifact verification
- prefer narrow Codex continuation runs against the exact remaining regression once the broader webtoon pipeline is already mostly correct

This keeps the adaptation lane from thrashing when the real issue is just one late-stage rendering contract.

## Practical heuristic
If the user says something like:
- “그냥 니 워크플로우 중 하나로 만들고 싶어”
- “이미 웹소설 만드는 스킬 있잖아”

interpret that as:
- preserve the existing novel workflow
- add a webtoon adapter workflow behind it
- start with `/adapt-webtoon`, not a standalone webtoon product
