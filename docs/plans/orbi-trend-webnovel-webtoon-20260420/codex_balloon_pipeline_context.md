# Codex Context — Balloon Analysis + Postprocess Pipeline

## Goal
Implement a robust postprocess pipeline for **speech balloon placement and rendering** on top of fal-generated webtoon panels.

The immediate user request is:
1. Use Codex with the installed **`$ralplan`** skill and give it this context in as much detail as possible
2. When the plan is produced, execute it via **`$ralph`**

## Current repo / working directory
- Repo: `/home/orbibot/.zeroclaw/workspace/hermes-agent`
- Active asset directory:
  - `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/`

## Current state of the webtoon pipeline
We already have:
- source novel / adaptation assets
- fal generation scripts
- heuristic balloon overlay script
- regenerated fal panels with reduced text artifacts

Important current files:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_webtoon_fal_v3.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/heuristic_webtoon_ui.py`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/README_heuristic_ui.md`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/panel_prompts.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/scroll_plan.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script.yaml`
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script_minimal.yaml`

Current best fal artifact:
- `docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3/ep001_fal_longscroll.png`

## What has already been learned
### 1. The storyboard fallback is not the quality baseline
The user explicitly considers the fal-generated version the real baseline and does **not** want the storyboard fallback treated as the representative output.

### 2. Model-generated text / speech bubbles are a major failure mode
The fal-generated images repeatedly produced:
- fake speech bubbles
- unreadable text fragments
- empty bubble-like white shapes
- garbage monitor text / pseudo-UI text

We improved this by adding stronger no-text constraints in `render_webtoon_fal_v3.py`:
- no speech balloons
- no dialogue bubbles
- no chat bubbles
- no readable monitor text
- no gibberish text
- no numbers / captions / logos

But even with that, quality is still not production-grade.

### 3. Dense heuristic overlay made the result worse
The previous heuristic postprocess (`heuristic_webtoon_ui.py`) placed large white boxes and made the fal art feel worse.
This is why the user now prefers:
- fal art first
- speech balloons attached **separately** afterward

### 4. The next missing layer is not only a balloon renderer
It is an **analysis layer** that decides:
- where balloons are safe to place
- which regions must not be covered
- where the tail should point
- whether the panel should use dialogue, caption, chat UI, screen UI, or no balloon at all

## User-approved direction
The user agreed that:
- balloons should be attached separately
- there likely needs to be an **image analysis layer** that determines where balloons should go on fal-generated cuts

## Best-practice synthesis already established
We already researched and concluded:
1. art and lettering should be split
2. balloons should be a separate layer from the generated art
3. chat / messenger / monitor / screen-heavy panels should not use generic speech balloons
4. vector or parameterized balloon rendering is preferable to baking raster white blobs directly
5. a panel analysis stage should happen before balloon rendering

## Proposed implementation target
Design and implement a pipeline roughly like this:

1. `generated_fal_v3/*.png` (art)
2. `analyze_balloon_zones.py`
3. `balloon_analysis.yaml` or `panel_safezones.json`
4. `lettering_script.yaml`
5. `render_balloons.py` (or equivalent)
6. compose longscroll

## Analysis layer requirements
At minimum, the analysis output should include per panel:
- `panel_mode`: one of
  - `dialogue`
  - `caption`
  - `chat_ui`
  - `screen_ui`
  - `silent`
- `safe_zones`: candidate rectangles / regions where balloons can be placed
- `forbidden_zones`: protected regions that should not be covered
- `speaker_points`: approximate head / mouth anchor points for tails
- `recommended_order`: reading-order-aware balloon ordering

### Minimum forbidden zone detection targets
The analysis layer should protect:
- faces / eyes
- meaningful hands
- laptop / phone screens when story-critical
- score sheets, contract sheets, or key evidence props
- emotional focal area near the center of the panel

## Important UX / quality constraints
- Do **not** regress to dense white-box overlays
- Favor conservative readable placement over aggressive “fully automatic” lettering
- Keep the fal art as the primary artifact
- Prefer compact overlays and specialized UI templates for chat panels
- Avoid covering faces, hands, key props, or important acting beats
- Maintain mobile vertical webtoon readability

## Likely deliverables from this implementation
At least some combination of:
- `analyze_balloon_zones.py`
- `balloon_analysis_schema.md` or similar schema reference
- `balloon_analysis.yaml` generated for ep001
- `render_balloons.py` or improved successor to `heuristic_webtoon_ui.py`
- chat / caption / dialogue differentiated handling
- updated README or usage doc for the new pipeline
- verification artifacts showing the new system works on `generated_fal_v3`

## Suggested execution preferences
- Plan should be concrete, file-specific, and verification-oriented
- Use the current ep001 assets as the proving ground
- Keep diffs small and reviewable
- Reuse existing files where reasonable, but do not be afraid to introduce a cleaner successor instead of overfitting the old heuristic overlay script
- The output should be something the user can actually run on the existing fal-generated panels

## Verification expectations
A strong implementation should include some or all of:
- generated analysis file(s) for ep001
- generated balloon-rendered output from v3 art
- visual verification that obvious face/hand/prop collisions are reduced
- checks that messenger/screen panels do not use generic balloon logic
- scripts runnable from the current repo without hand-wavy missing steps

## Additional note
There is an installed Codex OMX skill environment under `~/.codex/skills/`, including:
- `ralplan`
- `ralph`

The task should explicitly use those skills rather than generic planning language.
