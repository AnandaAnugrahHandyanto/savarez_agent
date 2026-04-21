---
name: awesome-novel-studio-fal-webtoon-mvp
description: Add an initial webtoon adaptation/render lane to `workspace/awesome-novel-studio` using fal + FLUX.2, while keeping the existing novel pipeline intact.
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [webtoon, fal, flux2, awesome-novel-studio, pipeline, adaptation]
---

# Awesome Novel Studio — fal + FLUX.2 Webtoon MVP

Use when the user wants to extend the existing `awesome-novel-studio` novel workflow into a webtoon-production lane, without replacing the current novel pipeline.

## When to use
- The repo already has the novel pipeline (`/propose`, `/design-big`, `/design-small`, `/create`, `/polish`)
- The user wants webtoon adaptation as a downstream workflow
- The user prefers cloud image generation via **fal** and **FLUX.2**
- Orchestration/runtime will be handled locally rather than by ComfyUI

## Core decision
Do **not** build a new standalone webtoon system first.
Attach a thin downstream lane to the existing novel flow:
- `/adapt-webtoon`
- `/webtoon-render`

That preserves all existing novel design/writing assets and adds only the webtoon-specific packaging + render handoff.

## Working model choice
Default image-generation choice:
- **fal + FLUX.2 Pro** for main generation
- Optionally mention FLUX.2 Flex / klein as faster secondary variants, but keep the MVP default on **FLUX.2 Pro**

Why:
- Better fit for repeated scene generation than generic one-off image tools
- Stronger for cloud API integration
- Supports text-to-image + editing-style workflows better than treating the problem as a pure prompt-only generator

## Files to create
Inside `workspace/awesome-novel-studio/` create:

### Skills
- `skills/adapt-webtoon/SKILL.md`
- `skills/webtoon-render/SKILL.md`

### References
- `references/webtoon-scroll-rhythm.md`
- `references/webtoon-lettering-rules-ko.md`

### Templates
- `templates/webtoon-episode-package.yaml`

### Docs
- `docs/fal-flux2-webtoon-setup.md`

## README updates
Patch both:
- `README.md`
- `README_KO.md`

Add:
- `/adapt-webtoon`
- `/webtoon-render`

Update both the quick-start block and command table.

## What each file should do

### 1. `skills/adapt-webtoon/SKILL.md`
Purpose:
- Convert a finished novel episode into structured webtoon production assets

Must define outputs such as:
- `webtoon/epNNN/scroll_plan.yaml`
- `webtoon/epNNN/panel_prompts.yaml`
- `webtoon/epNNN/lettering_script.yaml`
- `webtoon/epNNN/adaptation_notes.md`

Must enforce:
- webtoon is modeled as **scroll blocks**, not page-comic panels
- prose should be compressed into visual beats + short dialogue
- every block needs a purpose like `setup`, `pressure`, `reveal`, `reaction`, `payoff`, `cliff`, `spacer`
- prompts must be written for downstream model execution, not for human-only ideation
- admissions/Orbi works must preserve realism constraints

### 2. `skills/webtoon-render/SKILL.md`
Purpose:
- Define the handoff layer from adaptation assets into fal/FLUX.2 render requests

Must include:
- default model = `FLUX.2 [pro]`
- render queue concept
- JSON/payload design guidance for local scripts
- seed handling rules
- when to use generate vs edit vs outpaint
- explicit instruction to keep long dialogue out of generated images and handle lettering later
- **continuity contract** for same-scene chains: anchor refs for main character/location, scene_id, previous_panel linkage, and a rule that consecutive same-scene cuts should prefer image-edit/img2img chaining over unrelated fresh text-to-image jobs
- a separate `consistency_plan.yaml` (or equivalent) when the episode depends on strong cut-to-cut continuity

### 3. `references/webtoon-scroll-rhythm.md`
Purpose:
- Describe mobile-first scroll pacing
- Define block types and spacing/reveal rules
- Include special notes for Orbi/admissions emotional pacing

### 4. `references/webtoon-lettering-rules-ko.md`
Purpose:
- Korean lettering rules for postprocess placement
- Line-break, emphasis, balloon tone, placement-hint basics
- Explicitly discourage relying on image generation for long Korean text

### 5. `templates/webtoon-episode-package.yaml`
Purpose:
- A single starter schema bundling:
  - episode metadata
  - source design refs
  - adaptation profile
  - refs
  - blocks
  - balloons
  - render jobs

### 6. `docs/fal-flux2-webtoon-setup.md`
Purpose:
- Document the MVP lane
- Show exact workflow order:
  1. `/orbi-topic-selection`
  2. `/propose`
  3. `/design-big`
  4. `/design-small`
  5. `/create`
  6. `/polish`
  7. `/adapt-webtoon`
  8. `/webtoon-render`
  9. local fal call
  10. lettering/export

## Naming and modeling conventions
- Use `webtoon/epNNN/...` under project scope for outputs
- Treat image generation as a **render handoff**, not as the orchestration engine
- Separate:
  - adaptation structure
  - image-generation queue
  - lettering data
- Keep room for local scripts like `scripts/render_webtoon_fal.py` later, but don’t implement them in the MVP setup unless asked

## Key practical lessons
- The user may explicitly reject ComfyUI framing if they want **image generation**, not workflow building
- In that situation, answer with the actual cloud image product, then build the repo lane around that product
- Don’t overclaim image counts from dollar amounts unless directly verified for the exact endpoint/model
- For webtoon work, text rendering inside the generated image is fragile; postprocess lettering is safer
- In live fal runs for this repo, the practical production routes were:
  - text-to-image: `fal-ai/flux-2-pro`
  - image edit / continuity chaining: `fal-ai/flux-2-pro/edit`
- For continuity-sensitive webtoon cuts, generate anchors first, upload them to fal storage, then prefer `flux-2-pro/edit` with `image_urls=[previous_panel, character_anchor, location_anchor]` instead of fresh text-to-image for every cut
- Real-world finding: this chaining improves same-character / same-room continuity, but does **not** automatically create good panel differentiation. The adaptation layer still needs aggressively distinct shot goals (`opening`, `extreme close-up`, `phone hesitation`, `message pressure`) or the rendered cuts collapse into near-duplicates
- On fal, the practical JS client route for this repo used **actual endpoint IDs**:
  - text-to-image: `fal-ai/flux-2-pro`
  - image edit / chained continuity: `fal-ai/flux-2-pro/edit`
- The `@fal-ai/client` package can upload local anchor PNGs with `fal.storage.upload(...)`, which is useful when the render manifest stores local paths but the edit endpoint requires image URLs.
- For continuity-heavy webtoon tests, generate **location anchor first**, then **main character anchor**, upload both, and use `image_edit` with `[previous_panel_url, character_anchor_url, location_anchor_url]` for chained cuts.
- In practice, continuity can look decent even before a second character anchor exists, but cut-to-cut **shot differentiation** can still be weak; preserving identity and preserving storytelling beats are separate problems.
- Even aggressive negatives like `absolutely no text`, `no speech balloons`, `no dialogue bubbles`, `no readable monitor text`, and `no gibberish text` do **not** guarantee clean panels. Some rerenders still produce clipped white bubbles or pseudo-text.
- When one panel remains stubbornly contaminated, switch from full-episode rerendering to a **targeted candidate rerender lane**:
  1. keep the current best full-episode rerender as baseline
  2. generate 2-3 alternates for the bad panel only
  3. mix one fresh generate with one or more anchor-based edit variants
  4. add explicit negatives such as `no bubble-shaped white objects`, `no oval white shapes`, `no empty callout areas`
  5. use vision to score each candidate for residual bubble/text artifacts
  6. replace only that panel in the longscroll if a clean candidate wins
- This worked well on a stubborn over-shoulder panel: one candidate still had a clipped white bubble near the top edge, while two alternates were clean; swapping only the clean panel was faster and better than rerendering the whole episode again.
- Earlier repo testing used Node/npm, but this environment also had a usable Python `fal_client` installed even when `@fal-ai/client` was missing. Before assuming the JS route, check which client is actually available.
- In this environment, a practical secure credential location that worked was `~/.config/environment.d/fal.conf` with `chmod 600`, exporting `FAL_KEY='...'`. Source it in the render command (`set -a && source ~/.config/environment.d/fal.conf && set +a`) before calling fal.
- For Python execution, `fal_client.subscribe()` worked directly with:
  - `fal-ai/flux-2-pro` for fresh generation
  - `fal-ai/flux-2-pro/edit` for chained same-scene continuation
- A reusable render pattern that worked here:
  1. generate location / protagonist / mother anchors first
  2. for `p01` use fresh generate
  3. for later panels use edit with `[previous_panel_url, location_anchor_url, protagonist_anchor_url, mother_anchor_url?]`
  4. download each PNG locally
  5. add captions / balloons afterward with Pillow using Noto Sans CJK KR
  6. stitch to one long-scroll PNG with spacing derived from `scroll_plan.yaml`
- `fc-match 'Noto Sans CJK KR'` confirmed an installed Korean font in this environment, so Pillow post-lettering was viable without extra font installs.
- **Continuity is not guaranteed just because prompts mention the same scene.** For same-scene chains, require:
  - a `scene_id`
  - anchor refs for main character / secondary character / location
  - `previous_panel` linkage across consecutive cuts
  - `image_edit`/img2img continuation for same-subject same-scene cuts instead of unrelated fresh text-to-image calls
- Add a validation step before claiming continuity is solved:
  - confirm `render_queue.yaml` and JSON payloads include anchor refs + previous-panel chaining
  - confirm the declared anchor files actually exist on disk
  - if anchor PNGs are still missing, report the state as structurally ready but **not yet guaranteed in real renders**
- When anchor PNGs are missing, create an `anchor_generation_pack.md` plus per-anchor spec files so the next step is concretely executable rather than vague
- If the environment has **no usable image-generation credentials/backend** (for example no fal key, no native image tool route, or browser/image stack limitations), do not pretend a polished render succeeded. Produce a **storyboard-grade fallback webtoon package** instead:
  - render consistent local panel images from the existing `scroll_plan.yaml`, `panel_prompts.yaml`, and `lettering_script.yaml`
  - keep continuity on room / protagonist / parent / laptop motifs across panels
  - export both per-panel PNGs and one combined long-scroll PNG
  - save a `manifest.yaml` clearly labeling the output as `storyboard_fallback`
  - verify dimensions and inspect at least the combined long-scroll image with vision before reporting success
- If fal renders are available **but still look too AI-generated** because on-image text is broken, balloon placement overlaps, or captions spill awkwardly, add a **post-render heuristic UI overlay pass** instead of trying to solve everything in the generation prompt.
  - Build or use a reusable PIL-based overlay tool that reads `lettering_script.yaml` and panel PNGs from an input directory.
  - Required heuristics that proved useful:
    - speaker-aware safe zones (`mother`, `teacher_chat`, `friend_chat`, `internal_note`, `caption`)
    - measured-width Korean wrapping using font metrics, not fixed character counts alone
    - overlap avoidance against previously placed boxes
    - in-bounds clamping with explicit outer padding
    - balloon tails for spoken dialogue, no tails for captions/internal notes
    - soft rounded masking over likely on-image text/UI regions before placing overlays
  - Make the tool reusable with CLI flags such as `--input-dir`, `--output-dir`, `--lettering`, `--scroll-plan`, `--mode`, and `--mask-strength`.
  - Emit a placement/debug manifest (for example `placement_manifest.json`) recording chosen zones, box coordinates, mask regions, and font sizes.
  - Rebuild the longscroll from the postprocessed panel outputs so the delivered artifact reflects the improved overlays, not the raw fal render.
  - Practical finding: this pass reliably reduces off-canvas text and box-on-box collisions, but a purely heuristic system can still over-mask or cover important art. The next improvement after this stage should be saliency-aware avoidance (faces / hands / laptop / key props), not more hardcoded coordinates.

## Live rendering lessons from this run

### 1. fal credentials: save them somewhere the runtime can actually source
If the user gives a raw fal key and asks you to save it in the correct place for this environment, a practical working location was:
- `~/.config/environment.d/fal.conf`

Recommended content:
- `export FAL_KEY='...'`

Recommended permissions:
- `chmod 600 ~/.config/environment.d/fal.conf`

Verification that mattered here:
- source the file in the same shell before rendering
- run a tiny Python check with `fal_client.auth.fetch_auth_credentials()`
- do **not** assume that just because the skill mentions fal, the active session already has credentials loaded

Important note:
- this path is environment-specific and should be treated as a working runtime credential file for this setup, not a universal standard for every machine

### 2. For cleaner webtoon outputs, aggressively ban text generation inside the image model
A major failure mode was letting the model invent Korean/English text inside screens or speech areas.
Even when the main composition looked good, the result still felt AI-generated because:
- on-screen UI text became gibberish
- Korean inside the image broke
- prompt/meta fragments visually leaked into the result

What worked better in prompts:
- `absolutely no text`
- `no letters`
- `no Korean characters`
- `no English characters`
- `no subtitles`
- `no visible screen text`

Do **not** rely on the model to render readable Korean dialogue or readable UI.
Generate art only, then add Korean text in post.

### 3. Cartoon / manhwa style reads more naturally than semi-realistic photo-ish style for this workflow
The user explicitly rejected the earlier result as too AI-looking.
A useful correction was moving from realistic/cinematic phrasing to a cleaner webtoon/cartoon prompt family:
- `clean Korean webtoon cartoon illustration`
- `2D cel shading`
- `expressive line art`
- `softened shapes`
- `polished digital manhwa style`

This reduced the uncanny feel and made the final output read more like a webtoon panel instead of a photoreal AI composite.

### 4. Speech balloons should be post-processed as actual comic balloons, not generic rounded UI boxes
Another strong improvement was replacing generic rounded text boxes with:
- oval speech balloons
- explicit tails pointing toward the speaker
- panel-specific manual placement instead of a one-size-fits-all top-right stack

Practical lesson:
- if a panel has multiple speakers or a tense confrontation, place balloons manually per panel
- use post-processing to create the balloons; do not ask the model to draw the dialogue itself

### 5. Mask problem regions before adding lettering
For panels containing monitor/chat/UI elements, a good repair tactic was:
- draw a soft rounded mask over the area where broken text appears
- then add the intended caption / balloon / narration on top

This is especially useful for:
- monitor close-ups
- chat bubbles
- text-focus props
- panels where the model keeps hallucinating readable-looking but broken text

### 6. Two-pass improvement loop that worked
A reusable correction loop from this run:
1. generate anchors + first render pass with fal
2. inspect representative panels with vision
3. identify whether the main failures are:
   - too realistic / uncanny
   - broken internal text
   - unnatural speech balloon layout
4. revise the prompt family toward cleaner cartoon/manhwa language
5. remove all model-generated text from the target image
6. re-render into a new output directory (for example `generated_fal_v2/`)
7. re-run vision on key panels plus the full long-scroll output before reporting success

### 7. Good user-facing framing
If the first real fal render is visually weak, do not defend it.
State the specific failure modes plainly, then regenerate with:
- more webtoon-like style constraints
- post-processed Korean lettering
- masked UI/text regions where needed

That matched the user's expectation better than claiming the first render was good enough.

## Simulation-only delivery pattern
When the user explicitly wants to **simulate the fal call only** and inspect the prompt payloads without hitting the real API:
- generate the normal adaptation outputs first (`scroll_plan.yaml`, `panel_prompts.yaml`, `lettering_script.yaml`, `adaptation_notes.md`)
- generate the render handoff files next (`render_queue.yaml`)
- set an explicit simulation flag such as `simulation_mode: true`
- write a machine-readable request bundle such as `webtoon/epNNN/fal_requests/manifest.json`
- write a human-readable summary such as `webtoon/epNNN/render_notes.md` listing the exact prompts and negative prompts that would be sent
- preserve user-facing output conventions, such as **1 PNG per episode by default** after later lettering/assembly if that is the established project preference
- verify the files actually exist by reading them back before reporting success

## Verification checklist
Before reporting success:
- [ ] `skills/adapt-webtoon/SKILL.md` exists
- [ ] `skills/webtoon-render/SKILL.md` exists
- [ ] webtoon references/templates/docs exist
- [ ] README.md mentions both new commands
- [ ] README_KO.md mentions both new commands
- [ ] docs clearly state **fal + FLUX.2 Pro** as the MVP default
- [ ] if simulation-only was requested, `render_queue.yaml`, `fal_requests/manifest.json`, and `render_notes.md` exist and were read back successfully

## Good final report shape
When done, summarize:
- files added
- README changes
- fixed model choice (`fal + FLUX.2 Pro`)
- resulting workflow order
- next concrete step: generate one real `webtoon/ep001/*` package for an existing project
