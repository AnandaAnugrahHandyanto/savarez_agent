---
name: orbi-novel-studio-rebase
description: Archive a legacy Orbi webnovel pipeline, fork awesome-novel-studio into a private repo, add an Orbi MCP-based topic-selection preflight, and verify the new proposal lane with live Orbi evidence.
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [orbi, webnovel, github, mcp, pipeline-migration, topic-selection]
    category: creative
---

# Orbi Novel Studio Rebase

Use when the user wants to stop maintaining a custom Orbi webnovel pipeline and instead rebuild on top of `MJbae/awesome-novel-studio` while preserving Orbi-specific topic selection and admissions realism.

## When to use
- User says to archive/remove the current webnovel pipeline or skills
- User wants to fork `awesome-novel-studio` and use it as the new base
- User wants Orbi MCP + Move/Orbi domain knowledge injected into the front of the pipeline
- User wants evidence that the new flow actually produces better topic selection

## Core approach
Do **not** port the old giant pipeline wholesale.
Instead:
1. archive the legacy assets
2. fork the upstream repo
3. add a thin Orbi-specific preflight layer before `/propose`
4. pass that signal forward into `/design-big`
5. run a real evidence-backed demo and commit/push it

## Workflow

### 1. Archive the old pipeline first
- Search for all local webnovel assets: skills, render docs, scripts, tests, deliverables
- Move them into a timestamped archive directory under `workspace/archive/`
- Save a manifest (`ARCHIVE_MANIFEST.json`) listing moved files
- If global Hermes skills are being retired, back up their contents into the archive before deleting them
- Remove old references from local docs such as `workspace/TOOLS.md`

Recommended archive shape:
- `workspace/archive/webnovel-pipeline-<timestamp>/global-skills/`
- `workspace/archive/webnovel-pipeline-<timestamp>/workspace-assets/`
- `workspace/archive/webnovel-pipeline-<timestamp>/ARCHIVE_MANIFEST.json`

### 2. Fork and privatize the new base repo
- Verify GitHub auth with `gh auth status`
- Fork `MJbae/awesome-novel-studio`
- Clone to `workspace/awesome-novel-studio`
- Add `upstream` remote pointing to MJbae repo
- If the user wants privacy, run:
  - `gh repo edit bellman-move/awesome-novel-studio --visibility private`
- Verify the repo is private afterward with `gh repo view ... --json isPrivate`

### 3. Inspect the proposal/design entry points before editing
Read at least:
- `skills/propose/SKILL.md`
- `skills/design-big/SKILL.md`
- `skills/create/SKILL.md`
- `agents/proposal-generator.md`
- `README.md`
- `README_KO.md`

Goal: identify where to inject Orbi-specific signal with minimal surface-area change.

### 4. Add a dedicated Orbi topic-selection skill
Create a new skill file:
- `skills/orbi-topic-selection/SKILL.md`

The skill should enforce:
- Orbi MCP retrieval first
- topic selection based on current student anxiety, not generic school-story vibes
- Move/Orbi standards: admissions realism + serialization engine + 1-episode hook pressure
- required outputs:
  - current emotional market
  - 3 topic candidates
  - 1 recommended lane
  - handoff to `/propose`

### 5. Add a domain-principles reference file
Create:
- `orbi/references/move-orbi-domain-principles.md`

Put the stable rules there:
- realism is necessary but not sufficient
- the real center is comparison disadvantage / position shift
- recurring conflict matters more than a neat realistic vignette
- include canonical admissions factuality failure modes

This keeps the Orbi layer thin and reusable instead of rewriting the entire upstream pipeline.

### 6. Patch `/propose` to support Orbi preflight
In `skills/propose/SKILL.md`, add a conditional phase before normal research:
- if the work is Orbi / Korean admissions / student-market fiction, run an Orbi signal preflight
- read `skills/orbi-topic-selection/SKILL.md`
- read `orbi/references/move-orbi-domain-principles.md`
- collect:
  - `mcp_orbi_get_trending_searches`
  - `mcp_orbi_get_hot_posts(page=1)`
  - `mcp_orbi_get_hot_posts(page=2)`
  - 3-6 strong keyword searches via `mcp_orbi_search_posts`
  - representative posts via `mcp_orbi_get_post`
- store the result in:
  - `_workspace/00_research/R0_오르비신호.md`

Also patch the proposal-generator handoff so it must read `R0_오르비신호.md` when present.

### 7. Patch `/design-big` to carry the signal forward
In `skills/design-big/SKILL.md`:
- note that Orbi/admissions projects should check for `_workspace/00_research/R0_오르비신호.md`
- include that file in the concept-builder research inputs
- explicitly map it to:
  - current student emotional market
  - topic priority
  - banned realism errors

### 8. Update README surfaces
Update `README.md` and `README_KO.md` to reflect:
- one extra skill count if applicable
- `/orbi-topic-selection` in Quick Start
- `/orbi-topic-selection` in the command table

### 9. Run a real demo, not just code edits
Use live Orbi MCP evidence and produce:
- `_workspace/00_research/R0_오르비신호.md`
- `_workspace/01_orbi_topic_candidates.md`
- `_workspace/01_proposals.md`
- example markdown files under `examples/`

A good demo proves the lane works with current signal.

### 10. If the user asks you to actually run the rebuilt pipeline and bring back a novel
Don’t stop at topic-selection or proposal notes. Build a concrete project under the fork and produce real fiction.

Recommended minimal project shape:
- `projects/<slug>/novel-config.md`
- `projects/<slug>/*_제안서.md`
- `projects/<slug>/design/*.md`
- `projects/<slug>/episode/ep001.md ...`
- `projects/<slug>/revision/*.md`
- `projects/<slug>/deliverables/*.md`

What worked here:
1. Use the Orbi signal to pick one strong lane
2. Write the proposal / bootstrap / character sheet / plot-hook guide manually or with subagents
3. Create a valid `novel-config.md`
4. Write EP001 first, then continue in batches with subagents
5. For a practical "완결본" deliverable, a novella-scale 12-episode first-arc completion is acceptable when the user wants an end-to-end run now rather than a true 100+ episode serialization
6. Update `revision/fix_plan.md` so the run looks like an actually completed project state
7. Commit and push the generated project back into the fork

Useful subagent split that worked:
- child 1: EP002~EP004
- child 2: EP005~EP008
- child 3: EP009~EP012

Important warning:
- child subagents may continue from assumptions if intermediate episode files don’t exist yet; after parallel writing, verify continuity by reading the produced files before finalizing
- if continuity risk is high, prefer sequential batching instead of parallel batching

### 11. Render long PNG deliverables pragmatically
If the user asks for "길게 PNG 렌더링해서 보내" after generating a completed project:

1. First create a single markdown concat, e.g.
   - `projects/<slug>/deliverables/<name>_complete.md`
2. Try rendering with `bin/render_md_long_png.js`
3. Expect a Sharp limit failure for very tall images:
   - `Input SVG image exceeds 32767x32767 pixel limit`
4. When that happens, do **not** stall and do **not** claim full single-image output succeeded.
   Instead:
   - split the markdown into multiple sequential parts
   - create a small cover markdown
   - render `cover + part1 + part2 + ...` as separate long PNGs
5. Verify at least the cover visually (Korean text, layout intact)
6. Deliver the PNG set explicitly as a split long-scroll package

Recommended split pattern that worked here:
- `deliverables/render_parts/cover.md`
- `deliverables/render_parts/part_001_004.md`
- `deliverables/render_parts/part_005_008.md`
- `deliverables/render_parts/part_009_012.md`
- render to matching `.png` files

Practical note:
- `bin/render_md_long_png.js` from the archived legacy workspace can still be useful as a renderer even after the old pipeline is retired
- if one ultra-long PNG exceeds Sharp’s size ceiling, splitting is the correct operational fallback, not a failure of the whole render route

## Recommended live-signal query set
Start broad, then deepen.

Broad:
- trending searches
- hot posts page 1
- hot posts page 2

Good deepen defaults:
- `반수`
- `삼수 실패 이야기`
- `약대`
- `입결`
- `과탐`

Read representative posts that show:
- route-choice pressure
- target-lowering shame
- rank-table obsession
- time-budget collapse

## What worked well here
A strong current Orbi lane emerged from these signals:
- `00078195574` 반수생 부산/울경 지역인재 직1 vs 직2
- `00078183906` 의대말고 약대 목표라고 생각하니까
- `00078181657` 2026 입결표라는데 이거 맞음?
- `00078195804` 반수

These supported a high-quality recommended topic:
- **반수생의 하방 계약**
- engine: regional-med upper route vs contract-department floor, with 과탐/입결/parent pressure

## Pitfalls
- Don’t answer Orbi topic selection from memory; retrieval is mandatory
- Don’t copy the whole old pipeline into the new repo; keep the adapter layer thin
- Don’t stop at “skill added” — run a real evidence-backed demo and save examples
- Don’t forget to privatize the fork if the user asks; verify after changing visibility
- Don’t leave local archived webnovel references in `TOOLS.md` or similar docs after migration

## Verification checklist
Before declaring success:
- [ ] legacy pipeline archived with manifest
- [ ] upstream repo forked and cloned
- [ ] repo privacy matches user request
- [ ] `skills/orbi-topic-selection/SKILL.md` exists
- [ ] `orbi/references/move-orbi-domain-principles.md` exists
- [ ] `skills/propose/SKILL.md` reads/writes `R0_오르비신호.md`
- [ ] `skills/design-big/SKILL.md` consumes `R0_오르비신호.md`
- [ ] README surfaces mention the new command
- [ ] live Orbi MCP demo files exist
- [ ] changes committed and pushed

## Useful commit message
- `feat: add Orbi topic-selection preflight`
