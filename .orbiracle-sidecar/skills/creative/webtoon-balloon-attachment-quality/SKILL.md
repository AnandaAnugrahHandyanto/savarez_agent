---
name: webtoon-balloon-attachment-quality
description: Improve balloon-to-character attachment quality in a split AI-webtoon pipeline by moving from zone-first placement to speaker-local, anchor-aware ranking with tail policies and override contracts.
triggers:
  - User says balloons feel detached from characters
  - Split analyzer/render pipeline exists, but tails still look bolted-on
  - Mixed-mode panels (speech + chat_ui + caption) are readable but compositionally awkward
  - Existing overlay is technically safe but emotionally wrong
---

# Webtoon Balloon Attachment Quality

Use when AI-generated webtoon art already exists and a separate balloon-render pipeline exists, but the remaining failure mode is **attachment quality** rather than architecture.

## Core diagnosis
If the balloon system:
1. finds a safe empty zone first
2. then adds a tail afterward

it will often produce balloons that are collision-safe but still look like **floating boxes with pointers**.

The fix is to move from **zone-first** to **attachment-aware** placement.

## Working pattern that succeeded

### 1. Keep the split pipeline
Do **not** collapse back into one monolithic overlay script.
Keep:
- analyzer
- analysis artifact
- renderer
- generated output manifest

This preserves editability and debugging.

### 2. Add speaker-local attachment data to analysis output
Generic panel-level `safe_zones` are not enough.
Add panel fields such as:
- `speaker_anchors[]`
- `speaker_local_zones[]`
- `panel_overrides`
- `render_hints.item_overrides`
- `render_hints.tail_policy`
- `render_hints.tail_overrides`

Useful shapes:
- `speaker_anchors[]`: mouth/head/priority/preferred side
- `speaker_local_zones[]`: candidate regions near the specific speaker or item
- `item_overrides`: preferred/disallowed zones, forced anchor
- `tail_overrides`: entry edge, anchor override, optional bend behavior

### 3. Replace first-fit selection with ranked candidate evaluation
The renderer should evaluate **all** viable speech candidates, not stop at the first acceptable one.
Score inputs that mattered:
- zone confidence
- forbidden overlap penalty
- collision penalty
- anchor distance penalty
- preferred side bonus
- speaker-local bonus
- local priority bonus
- tail-cross penalty
- generic-fallback penalty
- line-count and line-balance penalties

This is what changed the behavior from “safe” to “attached”.

### 4. Treat speech differently from chat_ui/caption
Do not let mixed-mode panels flatten everything into generic speech logic.
Keep routing separate:
- `chat_ui`
- `caption`
- `screen_note`
- `speech`

For mixed-mode panels like `p08`, preserve chat/caption placement while improving only the spoken line’s attachment.

### 5. Tail routing must be edge-aware
A simple triangular tail from a clamped center point is not enough.
Use:
- resolved speaker anchor
- derived or overridden tail entry edge
- forbidden-region crossing check
- fallback / review reasons when the route is weak

Useful manifest fields:
- `resolved_anchor_id`
- `resolved_anchor_role`
- `tail_entry_edge`
- `tail_cross_ratio`
- `fallback_reason`
- `review_reasons`
- `score_breakdown`

### 6. Manual overrides are a bounded escape hatch
Do not let overrides become the whole system.
Rule that worked:
- generic heuristics first
- speaker-local guidance second
- overrides only for persistent hard panels

Good hard-panel targets were:
- `p02`
- `p06`
- `p08`

## Concrete file pattern that worked
Episode-local implementation under:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_layout_utils.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_analysis_schema.md`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/README_balloon_pipeline.md`
- `tests/test_balloon_pipeline_ep001.py`

Generated outputs:
- `balloon_analysis_ep001.yaml`
- `generated_fal_v3_ballooned/placement_manifest.json`
- `generated_fal_v3_ballooned/ep001_ballooned_longscroll.png`
- later tuned iterations like `generated_fal_v3_ballooned_attach2/`

## Verification that mattered
### Automated
Run:
```bash
source .venv/bin/activate
python -m py_compile docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py tests/test_balloon_pipeline_ep001.py
python -m pytest tests/test_balloon_pipeline_ep001.py -q
```

What tests should cover:
- schema fields exist
- normalized geometry is valid
- mixed-mode routing remains correct
- p02 / p06 / p08 attachment assertions exist
- manifest contains attachment diagnostics
- boxes remain in bounds and overlap budgets hold
- speech `lines` are persisted in the manifest so fit-time decisions are auditable
- speech text fits inside the same safe box used at draw time, not a looser fit-time proxy
- speech tails are validated at the pixel level, not only through manifest metadata

### Overflow-specific lesson learned later
A common late-stage failure is: text technically "fit" during candidate measurement, but still visibly protrudes outside the rendered speech balloon.

In practice this came from a **fit-time vs draw-time contract mismatch**:
- fit logic used one width/height assumption
- final draw logic centered the text into a smaller effective safe area
- tests only checked geometry indirectly, so the mismatch slipped through until visual review

The robust fix pattern was:
1. define one shared speech safe-area contract
2. use it consistently in both candidate measurement and final drawing
3. persist wrapped `lines` in the placement manifest
4. test the measured multiline bbox against the same `speech_text_safe_box(...)` used for rendering

If the user reports text sticking out of balloons, check this contract mismatch before tweaking fonts, wrap widths, or panel overrides.

### Tail-rendering regression that appeared later
Another failure mode: attachment metadata can be correct while the rendered panel is still wrong.

Example that actually happened:
- manifest showed `tail_points`, `tail_entry_edge`, and good anchor routing
- tests passed on metadata
- but the renderer used an inverted `should_draw_tail(...)` predicate, so speech tails were not painted at all

So for speech balloons, do **not** stop at metadata assertions.
Add a regression that:
- replays the same panel render from source art + manifest placements
- compares the real rendered image against a no-tail control render
- checks that the tail polygon area has non-zero changed pixels

This catches "metadata says tail exists, pixels say it does not" bugs.
### Visual
Check:
- does the balloon body read as near the speaker?
- does the tail look routed rather than bolted on?
- in mixed-mode panels, does speech still feel tied to the character rather than drifting into generic empty space?

Practical ranking from this run:
- `p06` improved the most
- `p02` improved but could still feel conservative
- `p08` stayed the hardest mixed-mode case

## Codex / OMX workflow that worked
When the problem changed from architecture to residual visual awkwardness, use **replanning** instead of blindly tweaking.

Good sequence:
1. write a detailed context markdown summarizing:
   - current pipeline
   - what was already improved
   - exact remaining failure mode
   - constraints
2. run Codex with `$ralplan` against that context
3. inspect generated PRD + test-spec under `.omx/plans/`
4. run Codex `$ralph` against the approved PRD/test-spec
5. if the result is improved but still weak, run another bounded Ralph iteration with a new context focused only on the residual problem

This worked well for:
- first broad attachment-quality implementation
- second bounded iteration focused on residual mixed-mode weakness
- later continuation runs where the big Ralph pass had already fixed most of the pipeline and only one regression remained

### Narrow continuation rule for Codex Ralph
If a broad Ralph run improves most of the pipeline but leaves one explicit blocker (for example `RuntimeError: No placement candidate available for item l01`), do **not** restart from the original broad prompt.

Instead:
- keep the current repo state
- verify which parts are already green yourself
- kill any lingering/stuck Codex process once the partial work is safely on disk
- launch a new Ralph run that says it is continuing from the current tree
- name the exact remaining regression and explicitly say not to undo the already-verified fixes

This reduced drift and worked much better than re-running the whole attachment task from scratch.

## Pitfalls
- Do not assume better tail styling alone fixes attachment.
- Do not overfit by hand-tuning every panel from the start.
- Do not let `safe_zones` ordering act as hidden placement policy.
- Do not regress chat_ui/caption behavior when improving speech attachment.
- Do not claim success from passing geometry tests alone; visual review still matters.

## User-directed no-pointer mode
Sometimes the user does not want a "better attached" tail at all — they want the speech-balloon pointer removed.

When that happens:
- keep the attachment analysis and manifest fields intact
- keep `tail_points`, `tail_entry_edge`, and routing diagnostics for provenance/debugging
- suppress only the final tail drawing for `speech` templates at render time
- avoid rewriting the analyzer or deleting tail metadata unless the user explicitly asks for schema changes

Why this is the right default:
- it is a low-risk visual change
- it preserves the attachment pipeline for future re-enable/tuning
- it avoids breaking tests or downstream diagnostics that expect tail-routing metadata

Practical implementation pattern that worked:
- add a small renderer helper such as `should_draw_tail(placement)`
- return `False` for `placement.template == "speech"`
- leave chat/caption/note rendering behavior unchanged unless the user asks otherwise
- regenerate the output artifact in a new directory and visually verify the longscroll for any visible residual pointers

## Good stopping rule
Stop iterating when:
- tests are green
- output artifacts regenerate cleanly
- the worst panels are materially better
- remaining flaws are localized and explicitly identified rather than systemic

If one panel is still noticeably weaker (for example a mixed-mode panel like `p08`), record that as the next bounded iteration target instead of pretending the whole problem is solved.
