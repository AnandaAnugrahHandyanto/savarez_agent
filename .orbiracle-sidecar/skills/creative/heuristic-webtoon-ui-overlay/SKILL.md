---
name: heuristic-webtoon-ui-overlay
description: Rebuild Korean webtoon speech balloons/UI heuristically over generated panels when model-rendered text is broken or balloon placement is awkward.
triggers:
  - User says webtoon text is broken, overlapping, sticking out, or too AI-looking
  - Generated Korean text inside images is unreadable
  - Need to replace model-rendered lettering with cleaner overlay UI
---

# Heuristic Webtoon UI Overlay

Use this when generated webtoon panels have decent art but bad Korean text, awkward balloon placement, or broken UI elements.

## Goal
Replace in-image text and rough lettering with a post-process overlay system that:
1. Reads a separate lettering script
2. Places balloons/captions heuristically in safe zones
3. Avoids overlap and out-of-bounds placement
4. Composes a final longscroll output

## Inputs
- Panel image directory
- `lettering_script.yaml`
- `scroll_plan.yaml`

## Proven file layout
- Script: `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/heuristic_webtoon_ui.py`
- README: `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/README_heuristic_ui.md`
- Example output dir: `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_ui/`
- Example manifest: `generated_fal_ui/placement_manifest.json`

## Core heuristics
- Speaker-type preferred zones:
  - `mother`
  - `teacher_chat`
  - `friend_chat`
  - `internal_note`
  - `caption`
- Collision avoidance against previously placed boxes
- Canvas clamping so balloons never leave frame
- Font-width based Korean line wrapping, not fixed character count
- Balloon tail for dialogue, no tail for caption
- Optional soft rounded mask over image regions likely to contain broken text
- Save final placements to a manifest JSON

## Execution
Example:
```bash
python3 docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/heuristic_webtoon_ui.py \
  --input-dir docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v2 \
  --output-dir docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_ui \
  --lettering docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script.yaml \
  --scroll-plan docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/scroll_plan.yaml \
  --compose-longscroll \
  --mode balanced \
  --mask-strength 0.45
```

## Verification
- `python -m py_compile <script>`
- Confirm per-panel outputs and longscroll exist
- Inspect `placement_manifest.json`
- Manually verify that balloons do not overlap, clip, or cover key facial/hand focal areas more than necessary

## Later reliability upgrades from the split analyzer -> renderer pipeline
When the heuristic overlay evolves into an analysis-first pipeline (`analyze_balloon_zones.py` -> `render_balloons.py`), two reliability checks become mandatory.

### 1. Shared speech safe-box contract
If speech text looks like it should fit but still pokes outside the balloon, the likely problem is not "font too big" by itself.
It is usually a **contract mismatch**:
- fit-time measurement uses one effective text box
- draw-time centering uses a smaller speech-safe area

What proved reliable:
- define one shared helper such as `speech_text_safe_box(...)`
- use the same contract in both fit logic and final drawing
- store wrapped `lines` in the placement manifest
- in tests, measure the multiline bbox and assert it fits inside that same safe box

Without this, you can get a false green state where the manifest looks plausible but the rendered Korean text still overflows.

### 2. Pixel-level tail verification
Manifest metadata is not enough to prove the rendered panel is correct.
A real regression that happened later was:
- `tail_points` existed in the manifest
- anchor routing metadata looked correct
- but speech tails were not actually painted because the renderer-side predicate was inverted

So when speech tails matter, add a regression that:
- reconstructs the panel render from source art + manifest placements
- compares the real render against a no-tail control render
- checks that the expected tail polygon region has non-zero changed pixels

That catches cases where diagnostics are right but the image is still wrong.

## Current limitations
- This improves safety more than aesthetics on first pass
- Large white boxes may still cover important art
- Messenger/UI panels often need a specialized chat layout instead of generic balloon logic

## Recommended next improvements
1. Add saliency-aware avoidance for faces/hands/laptops
2. Use smaller caption variants when white boxes are too intrusive
3. Add dedicated messenger/chat UI templates
4. Add panel-specific importance penalties for focal regions
5. Add a dedicated **analysis layer** before balloon rendering that decides *where balloons are allowed* rather than placing them directly

## Analysis layer recommendation
For AI-generated webtoon panels, balloon rendering should be split into two stages:

### Stage 1 — panel analysis
Generate a per-panel placement guide such as `balloon_analysis.yaml` or `panel_safezones.json`.
This layer should identify:
- safe zones where balloons can sit
- protected zones that should not be covered
- likely speaker anchor points for tail direction
- panel reading order and balloon priority
- special panel mode such as `dialogue`, `caption`, `chat_ui`, `screen_ui`, `reaction`, `silent`

Minimum protected zones:
- faces / eyes
- hands doing meaningful actions
- laptop / phone screen when it is a story-critical prop
- key evidence props / documents / score sheets
- emotional focal points near the center of the panel

### Stage 2 — balloon rendering
Only after analysis should the renderer choose balloon geometry, tail direction, and text wrapping.

Why this matters:
- direct heuristic placement often covers the exact thing the scene is trying to show
- webtoon readability depends on preserving focal acting beats, not just avoiding overlap with previous boxes
- messenger and screen panels need different treatment from normal dialogue panels

### Practical pipeline shape
1. `generated_fal_v3/*.png`
2. `analyze_balloon_zones.py` → emits `balloon_analysis.yaml`
3. `lettering_script.yaml`
4. `render_balloons.py` reads both analysis + lettering
5. compose longscroll

## Attachment-quality lesson learned later
If the user says the balloon **exists** but still feels unnaturally attached to the character, the problem is usually no longer text rendering or box shape alone. It is an **attachment model** problem.

### Failure pattern that appeared in practice
A split pipeline can still look wrong when it stays **zone-first**:
- choose a globally safe empty rectangle first
- place the balloon body there
- only then add a generic triangular tail toward one speaker point

This often produces:
- balloon body too far from the speaker
- long diagonal tails that feel bolted on
- technically safe placement that is emotionally wrong
- multi-character panels where the balloon sits in panel whitespace instead of in actor-local composition

### Better model: attachment-first hybrid
Keep the split analysis/render architecture, but upgrade the contract so speech placement is driven by **speaker-local attachment intent** before generic safe-zone fallback.

### Schema additions that proved worth planning for
Additive fields that help:
- `speaker_anchors[]`
  - richer than legacy `speaker_points[]`
  - can represent mouth/head role, priority, preferred tail side
- `speaker_local_zones[]`
  - candidate balloon regions tied to a speaker or specific lettering item
  - used before generic `safe_zones[]` for speech
- `panel_overrides`
  - panel-level attachment policy such as ranking mode / default speaker / review threshold
- `render_hints.item_overrides`
  - per-line override contract (`preferred_zone_ids`, `disallowed_zone_ids`, `force_anchor_id`, etc.)
- `render_hints.tail_policy`
  - panel-level tail mode and anchor preference
- `render_hints.tail_overrides`
  - per-item tail entry edge / anchor override / bend behavior

### Precedence that should be explicit
For placement:
1. per-item overrides
2. `speaker_local_zones[]`
3. panel-level policy
4. generic `safe_zones[]`

For anchors:
1. per-item tail override
2. best matching `speaker_anchors[]`
3. legacy `speaker_points[]`
4. no tail + manual review reason

### Renderer change that matters most
Do **not** accept the first compatible safe zone.
Evaluate all viable candidates and rank them using:
- overlap penalty
- collision penalty
- distance from balloon body to target speaker anchor
- side/orientation preference relative to speaker
- tail-path crossing penalty against forbidden zones / other balloons
- penalty when speech falls back from speaker-local to generic global zones

### Verification upgrades that matter
Collision checks are not enough. Add manifest/test evidence for:
- chosen candidate class (`speaker_local` vs `generic`)
- resolved anchor id / role
- tail entry edge
- fallback reason when generic placement wins
- mixed-mode conflict reasons for panels with chat + speech + caption

### Practical takeaway
When the user says "the balloon is still awkward on the character," do not spend another full round only tweaking font, line breaks, or ellipse shape.
Replan around:
- actor-local zones
- anchor quality
- tail routing
- override precedence
- attachment-first ranking

### Good first-pass outputs from the analysis layer
Per panel:
- `safe_zones`: list of candidate rectangles with scores
- `forbidden_zones`: face / hand / prop boxes
- `speaker_points`: approximate mouth/head anchors
- `panel_mode`: one of `dialogue`, `caption`, `chat_ui`, `screen_ui`, `silent`
- `recommended_order`: balloon ordering for reading flow

This analysis-first structure is the right next step when the user says the fal art is better than the overlay, because the failure is usually *where* the balloon sits, not only *how* it is drawn.
5. Move balloon generation to a vector/SVG layer so text and balloon geometry can be revised without repainting raster art

## Best-practice findings for webtoon balloon postprocess
For fal-generated Korean webtoons, the most reliable production approach is:
1. generate **art only**
2. keep dialogue in a separate lettering data file
3. generate balloons/captions/chat UI as a separate postprocess layer
4. compose to final PNG only at the end

Why this worked better than image-native balloons:
- models frequently hallucinate bubble-like white shapes and unreadable pseudo-text
- once those are baked into the art, cleanup is more expensive than post-lettering
- a separate balloon layer preserves the stronger fal art and reduces AI-looking text failures

Recommended layer split:
- art layer: `generated_fal_v3/*.png`
- lettering source: `lettering_script.yaml`
- layout source: `balloon_layout.yaml` or equivalent
- render stage: vector/SVG balloon + text generation
- final stage: raster composite + longscroll assembly

Balloon classes must be handled separately:
- normal dialogue: ellipse / rounded speech bubble + tail
- caption / internal note: tail-less caption box, often dark or semi-transparent
- messenger / monitor / phone UI: **do not** use generic speech bubbles; use dedicated chat/notification templates

Typography rules that mattered in practice:
- use a body/readability-oriented dialogue font, not a decorative display font
- fix widows/orphans by rewriting or rewrapping before shrinking the type
- prefer reflow/recomposition over aggressive text scaling
- long confrontation lines should usually be shortened or split, not forced into a huge bubble

Placement rules that map well to automation:
- preserve reading flow top-to-bottom first
- define exclusion zones for faces, hands, laptop screens, and key props
- keep tails short and unambiguous
- treat monitor-heavy panels as UI overlays, not speech-balloon panels

## Practical correction learned later
When the user says the heuristic overlay made the result worse and the **fal render is still the better base**, do not keep iterating on the same dense-overlay settings.

Instead:
1. Treat the raw fal output (often `generated_fal_v2`) as the primary artifact
2. Create a separate minimal lettering file, for example `lettering_script_minimal.yaml`
3. Keep only the indispensable lines for readability:
   - one short opening caption
   - one key confrontation line
   - one end-turn caption if needed
4. Re-render with:
   - `--mode compact`
   - `--mask-strength 0.0`
5. Prefer 2-4 total overlay items for the whole episode before adding more
6. Avoid generic balloon overlays on messenger / monitor / screen-heavy panels unless a dedicated chat UI template exists

What this fixed:
- reduced the sense that postprocessing was damaging the better fal art
- reduced large intrusive white overlays
- preserved the fal mood better than the previous balanced + masked overlay pass

What it did **not** fully fix:
- some panels may still feel empty or awkward because the underlying fal art already contains bright text-like regions
- a long final confrontation line can still create a visually heavy box even in minimal mode
- this produces a conservative readable pass, not a polished final lettering result

## Practical variant: pointerless speech mode
When the user says the balloon tail/pointer itself feels awkward and wants it removed, do **not** replan the whole attachment system first.

Use a minimal renderer-side change:
1. keep anchor resolution, attachment scoring, and manifest diagnostics intact
2. keep `tail_points` generation for provenance/debugging if useful
3. suppress drawing of speech tails at render time
4. regenerate the output directory as a separate variant (for example `generated_fal_v3_ballooned_notail/`)
5. run compile/tests and do a quick visual verification on the longscroll

Why this is the right first move:
- the user may only dislike the visible pointer shape, not the ranking/placement logic
- removing rendered tails is cheaper and safer than rewriting attachment analysis
- diagnostics remain available in the manifest if you later want to restore or restyle tails

Practical implementation pattern that worked:
- add a small helper like `should_draw_tail(placement)`
- return `False` for `placement.template == "speech"`
- leave caption/chat behavior unchanged unless the user explicitly asks for those too

Verification pattern that worked:
- `python -m py_compile <renderer>`
- rerender to a new output dir
- inspect the longscroll visually to confirm no obvious speech-tail pointers remain
- keep the manifest so attachment metadata still exists even when tails are hidden

## Important follow-up from later runs
If the user later re-enables attachment-quality work after a no-pointer phase, do **not** assume speech-tail rendering is correct just because tail metadata survived in the manifest.

What actually happened in practice:
- no-pointer mode intentionally suppressed visible speech tails
- a later attachment/overflow patch reintroduced tail logic
- renderer predicate drift caused speech tails to remain missing even though manifest routing looked valid

So when moving back from pointerless mode to attached speech mode:
1. verify the renderer predicate actually draws speech tails again
2. rerender outputs instead of trusting old artifact dirs
3. use an image-level regression, not only manifest assertions

## Notes
- For Korean webtoon quality, do not rely on the image model to render readable Korean text.
- Generate art separately; overlay Korean text/UI afterward.
- Prefer cartoon/manhwa art direction if the user says the result feels too AI-like.
- Do not present storyboard fallback renders as the representative output when the user clearly judges fal outputs as the real baseline.
