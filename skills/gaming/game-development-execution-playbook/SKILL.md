---
name: game-development-execution-playbook
description: Use when moving from game design documents into actual AI-assisted implementation with Claude Code/Codex; creates source-of-truth docs, MVP locks, phase packets, test gates, and anti-scope-creep rules.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [games, game-dev, claude-code, execution, mvp, planning]
    related_skills: [claude-code, writing-plans, test-driven-development, requesting-code-review]
---

# Game Development Execution Playbook

## Overview

Use this when a game already has ideas, a GDD, mockups, or many planning documents and the next question is: **"How do we actually start building without getting lost?"**

The core rule is:

```text
Do not implement from the whole design archive.
Implement from one locked work packet at a time.
```

A large game document set is a map. Claude Code needs a route segment. Convert the map into:

```text
CLAUDE.md → GAME_SSoT.md → MVP_LOCK.md → BUILD_PLAN.md → FEATURE_SPEC_INDEX.md → one phase packet
```

Then run a tight loop:

```text
Plan → approve → implement → test → review → update docs → next packet
```

## When to Use

Use this when the user says things like:

- "게임 문서가 많은데 실제 작업을 어떻게 들어가지?"
- "Claude Code로 게임 개발 시작하게 정리해줘"
- "GDD를 기반으로 MVP부터 만들고 싶어"
- "문서가 너무 많아서 뭐부터 구현해야 할지 모르겠어"
- "CLAUDE.md 절대 규칙이 필요해"

Do not use this to invent new game features. Use it to turn already-decided game material into an execution system.

## Required Project Control Files

Before implementation, create or verify these files at the project root:

```text
CLAUDE.md                  # absolute rules for AI agents
PROJECT_INDEX.md           # map of documents and priority
GAME_SSoT.md               # single source of truth for the game
MVP_LOCK.md                # what is in/out for the current build
BUILD_PLAN.md              # phase order and completion gates
FEATURE_SPEC_INDEX.md      # feature packet list
QA_CHECKLIST.md            # done criteria and manual tests
```

For asset-heavy games also require:

```text
ASSET_MANIFEST.json        # approved/placeholder resource list
```

## Document Authority Order

Put this rule in `CLAUDE.md` exactly or with project-specific names:

```md
## Source of Truth Priority

If documents conflict, follow this order:

1. CLAUDE.md
2. GAME_SSoT.md
3. MVP_LOCK.md
4. BUILD_PLAN.md
5. docs/features/*.md
6. docs/reference/**
7. old notes, brainstorms, archived docs

Never implement from lower-priority documents when they conflict with a higher-priority file.
```

## Recommended Project Structure

```text
GameProject/
├── CLAUDE.md
├── PROJECT_INDEX.md
├── GAME_SSoT.md
├── MVP_LOCK.md
├── BUILD_PLAN.md
├── FEATURE_SPEC_INDEX.md
├── QA_CHECKLIST.md
├── ASSET_MANIFEST.json
│
├── docs/
│   ├── 00_control/
│   │   ├── decision_log.md
│   │   ├── change_request_log.md
│   │   └── terminology.md
│   ├── 01_product/
│   │   ├── game_concept.md
│   │   ├── player_promise.md
│   │   ├── target_player.md
│   │   └── non_goals.md
│   ├── 02_gameplay/
│   │   ├── core_loop.md
│   │   ├── combat_system.md
│   │   ├── progression.md
│   │   └── balance_rules.md
│   ├── 03_content/
│   │   ├── cards.md
│   │   ├── enemies.md
│   │   ├── bosses.md
│   │   └── rewards.md
│   ├── 04_ui_ux/
│   │   ├── screen_flow.md
│   │   ├── wireframes.md
│   │   ├── component_spec.md
│   │   └── first_5_minutes.md
│   ├── 05_art_audio/
│   │   ├── art_direction.md
│   │   ├── image_prompt_bank.md
│   │   ├── sound_manifest.md
│   │   └── font_rules.md
│   ├── 06_tech/
│   │   ├── architecture.md
│   │   ├── data_schema.md
│   │   ├── save_system.md
│   │   └── coding_conventions.md
│   ├── 07_features/
│   │   ├── F001_project_skeleton.md
│   │   ├── F002_core_loop.md
│   │   ├── F003_combat_or_action_system.md
│   │   └── F004_reward_or_progression.md
│   ├── 08_testing/
│   │   ├── manual_test_script.md
│   │   └── acceptance_criteria.md
│   └── 09_release/
│       ├── roadmap.md
│       └── demo_plan.md
```

## CLAUDE.md Absolute Rules for Games

Add these rules before the first implementation task:

```md
# CLAUDE.md — Game Project Absolute Rules

## Source of Truth
Follow this priority when documents conflict:
1. CLAUDE.md
2. GAME_SSoT.md
3. MVP_LOCK.md
4. BUILD_PLAN.md
5. FEATURE_SPEC_INDEX.md and docs/features/*.md
6. docs/reference/**
7. archived notes and brainstorms

## MVP First
The current target is the MVP or vertical slice defined in MVP_LOCK.md. Do not implement v1.0, DLC, live ops, backend, monetization, meta progression, extra characters, extra stages, or extra systems unless they are explicitly included in MVP_LOCK.md.

## No Scope Invention
Do not add new screens, currencies, systems, enemies, cards, quests, shops, gacha, achievements, accounts, ranking, ads, IAP, analytics, localization, cloud save, or server features unless the active work packet explicitly asks for them.

## Work Packet Only
For each task, implement only the current phase packet. If a related improvement is found, write it as TODO or change request instead of implementing it silently.

## Asset Usage
Use only assets listed in ASSET_MANIFEST.json with status `approved` or `placeholder`. Do not use generated assets marked `candidate`, `needs_regen`, `rejected`, or `failed`.

## Runtime Text
Do not bake runtime text, numbers, labels, localization strings, item names, or Korean text into images. Render text in the game/app.

## No Silent Refactor
Do not perform broad architecture rewrites or cleanup outside the requested work packet. Propose them separately.

## Completion Rule
A feature is complete only when implementation, acceptance criteria, manual test path, and build/test verification are all done.
```

## First Development Tasks

Use this order for a new game implementation:

### Task 0 — Control Docs Extraction

Goal: convert all design material into execution docs.

Output:

```text
CLAUDE.md
PROJECT_INDEX.md
GAME_SSoT.md
MVP_LOCK.md
BUILD_PLAN.md
FEATURE_SPEC_INDEX.md
QA_CHECKLIST.md
```

Prompt:

```text
Read the existing game documents and create implementation control docs only.
Do not implement code.
Do not invent new features.
Separate MVP scope from future-version ideas.
Identify conflicts and make the source-of-truth decision explicit.
```

### Task 1 — Project Skeleton

Goal: make the project runnable with a blank or placeholder title screen.

Include:

- project setup;
- folder structure;
- routing/scene shell;
- basic state store;
- placeholder data loading if needed.

Exclude:

- real combat/action logic;
- rewards;
- persistence;
- meta progression;
- online features.

### Task 2 — Screen Flow Skeleton

Goal: implement dummy navigation for the core run:

```text
Title → Start → Gameplay/Combat → Reward/Result → Restart
```

No real balance yet. Prove the loop path first.

### Task 3 — Core Data Model

Define minimum types/entities:

- player;
- run state;
- card/skill/item if relevant;
- enemy/obstacle;
- encounter;
- reward;
- result.

### Task 4 — Core Loop Logic

Implement only the smallest playable loop:

- player action;
- enemy/world response;
- win/loss condition;
- reward or result transition.

### Task 5 — Content Pass

Add the minimum locked content from `MVP_LOCK.md` only.

## Work Packet Template

Use this for every Claude Code task:

```text
Task name:
[Phase name]

Goal:
[Concrete one-phase outcome]

Must read:
- CLAUDE.md
- GAME_SSoT.md
- MVP_LOCK.md
- BUILD_PLAN.md
- FEATURE_SPEC_INDEX.md
- [relevant feature spec]

May edit:
- [paths]

Must not edit:
- [paths]

Absolute no-go:
- Do not add features outside MVP_LOCK.md.
- Do not invent systems, screens, currencies, server, monetization, or meta progression.
- Do not perform broad refactors.
- Do not bake runtime/Korean text into images.

Completion criteria:
- [criterion 1]
- [criterion 2]
- Build/test command passes: [command]
- Manual test path works: [path]

First respond with an implementation plan only. Do not edit files yet.
```

After reviewing the plan, send:

```text
Proceed with the approved plan only.
Stay inside the task scope.
Run the build/tests when finished.
Report changed files, test result, MVP_LOCK violations if any, and remaining TODOs.
```

## Phase Completion Report Template

Ask Claude Code to report in this shape:

```md
## Phase Result

### Implemented
- ...

### Changed Files
- ...

### Verification
- Build: pass/fail
- Tests: pass/fail
- Manual loop: pass/fail

### MVP_LOCK Check
- No violations / violations listed

### Deferred TODOs
- ...

### Next Recommended Packet
- ...
```

## Practical Operating Loop

```text
1. Select one phase from BUILD_PLAN.md.
2. Create a work packet.
3. Ask Claude Code for a plan only.
4. Approve or trim the plan.
5. Let it implement.
6. Run build/tests/manual test.
7. Ask for code review focused on scope creep and broken behavior.
8. Fix only blocking issues.
9. Update control docs and work log.
10. Move to the next phase.
```

## Stop Signals

Pause and correct the agent if it says or does any of these:

- "This extra system would be useful."
- "I added a shop/meta/currency/server for extensibility."
- "I changed the architecture broadly while I was here."
- "I used the future roadmap as the implementation target."
- "The document did not specify it, but games usually need it."

Correction:

```text
Stop. MVP_LOCK.md is the boundary. Remove or defer anything outside the active work packet. Keep it as TODO/change request only.
```

## Common Pitfalls

1. **Feeding all documents at once.** This causes scope explosion. Feed one work packet.
2. **No MVP_LOCK.** Without a lock, every cool idea becomes implementation scope.
3. **Skipping plan mode.** Always plan first, implement second.
4. **Letting reference docs outrank control docs.** Reference docs are not commands.
5. **Building systems before proving the loop.** First prove title → play → result.
6. **Using final art too early.** Placeholder assets are often safer until layout is stable.
7. **Silent refactors.** They destroy velocity and make bugs harder to isolate.

## Verification Checklist

- [ ] Root control docs exist.
- [ ] `CLAUDE.md` has document priority and no-scope-invention rules.
- [ ] `MVP_LOCK.md` has explicit included and excluded lists.
- [ ] `BUILD_PLAN.md` is split into small phases.
- [ ] Each feature has purpose, rules, data model, acceptance criteria, manual test, and non-goals.
- [ ] Every Claude Code task starts with plan-only mode.
- [ ] Every completed phase runs build/test/manual loop.
- [ ] Every phase report includes MVP_LOCK violation check.
