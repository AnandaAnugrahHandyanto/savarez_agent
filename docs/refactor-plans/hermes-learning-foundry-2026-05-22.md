# Hermes Learning Foundry - 2026-05-22

## Purpose

Create a lightweight, recurring Hermes lane that turns the full Hermes build history into evidence-backed business lessons, frameworks, playbooks, and teaching assets.

This is a planning and handoff artifact only. It does not change live Hermes cron jobs, profiles, memory files, Obsidian notes, Kanban boards, or Atlas services.

## Operating Principle

Do not summarize everything into one large context window.

The Learning Foundry works in small evidence batches. Each batch extracts claims from a bounded source set, verifies those claims against concrete evidence, then promotes only the strongest lessons into durable teaching material.

The goal is not a complete archive. The goal is a trustworthy body of transferable lessons from building Hermes.

## Source Scope

Allowed sources:

- Codex memory registry and rollout summaries.
- Local Codex raw session logs when present and readable.
- Hermes repo docs, plans, handoffs, scripts, tests, artifacts, and git history.
- Atlas Hermes session database through approved read-only tools such as `session_search`.
- Obsidian vault notes under approved Hermes and project paths.
- Atlas filesystem evidence reachable through approved read-only bridge or SSH checks.

Excluded by default:

- Secrets, tokens, OAuth files, `.env` files, private customer payloads, and raw CRM data.
- Raw chat dumps copied wholesale into Obsidian.
- Live customer, publishing, CRM, cron, profile, memory, or service mutations.
- Lessons that cannot point to evidence.

## Output Locations

Recommended Atlas durable root:

```text
/home/atlas/Documents/Obsidian Vault/Hermes/Learning Foundry/
```

Recommended subfolders:

```text
00 Inbox/
01 Source Inventories/
02 Extracted Claims/
03 Verified Learnings/
04 Framework Drafts/
05 Teaching Assets/
90 Rejected or Parked/
```

Repo-side planning and schema:

```text
docs/refactor-plans/hermes-learning-foundry-2026-05-22.md
docs/handoffs/hermes-learning-foundry-kickoff-2026-05-22.md
schemas/learning-foundry-extraction.schema.json
artifacts/learning-foundry/seed-kanban.md
```

## Workflow

### 1. Inventory

Build a source batch small enough to reason about without context drift.

Batch limits:

- 3 to 8 related sessions, or
- 1 task group from `MEMORY.md`, or
- 1 repo subsystem plus its adjacent docs/artifacts, or
- 1 Obsidian project folder section.

Every batch records:

- source IDs;
- file paths or session IDs;
- date range;
- topic tags;
- why the batch is being processed now;
- privacy notes.

### 2. Extract

Extract candidate claims, not final lessons.

Claim types:

- decision;
- failure pattern;
- recovery pattern;
- operating principle;
- implementation pattern;
- approval or safety boundary;
- customer/business lesson;
- teaching metaphor or named framework candidate.

Each claim must include at least one evidence pointer before it can leave extraction.

### 3. Verify

A separate pass reviews each candidate claim.

Verifier questions:

- What evidence supports this?
- Did this happen once, repeatedly, or as a proven change in behavior?
- Is it transferable to another business, or only true inside this machine/setup?
- Is it safe to teach without leaking private details?
- What would make this lesson false or misleading?

Claims that cannot survive this pass move to `90 Rejected or Parked/`.

### 4. Distill

Only verified learnings become framework drafts.

Framework drafts should be:

- simple enough to remember;
- grounded in the Hermes story;
- useful to a business owner or operator;
- explicit about when the lesson does not apply;
- supported by examples and evidence IDs.

Use Alex Hormozi-style clarity as a writing standard: named concepts, sharp distinctions, practical steps, and teachable examples. Do not mimic voice, branding, or slogans.

### 5. Publish

Promotion to teaching assets requires:

- at least two evidence pointers, unless the asset is explicitly marked as a single case study;
- a clear audience;
- a practical application step;
- a limitation or anti-pattern;
- a final human-review marker.

## Quality Grades

| Grade | Meaning | Promotion rule |
| --- | --- | --- |
| `observed` | Appears in one source or session | Keep as claim only |
| `repeated` | Appears across multiple sources or sessions | May become verified learning |
| `proven` | Changed a decision, workflow, artifact, or outcome | May become framework draft |
| `teachable` | Transferable beyond Hermes with caveats | May become teaching asset |
| `framework_grade` | Memorable, tested against evidence, and useful to others | Candidate for canonical material |

## Kanban Model

Use Kanban as the operating tracker, not as the knowledge store.

Columns:

- `Sources to Inventory`
- `Ready for Extraction`
- `Claims Extracted`
- `Needs Evidence`
- `Verified Learnings`
- `Framework Draft`
- `Teaching Asset`
- `Rejected or Parked`

WIP limits:

- `Ready for Extraction`: 3 batches.
- `Claims Extracted`: 20 claims.
- `Needs Evidence`: 10 claims.
- `Framework Draft`: 3 drafts.

If the limits are hit, stop ingesting new material and verify or reject what already exists.

## Cron Cadence

Start conservative.

Recommended phase 1:

- Daily inventory refresh for new sessions and changed docs.
- Daily extraction of one small historical batch.
- Weekly synthesis of repeated patterns.
- Weekly human-review packet of the strongest candidates.

Do not run large batch synthesis every few hours. It will create shallow output and context drift.

Recommended phase 2, after review quality is proven:

- Increase historical extraction to two or three batches per day.
- Add a fortnightly framework-promotion pass.
- Add a monthly "Hermes story so far" synthesis.

## Roles

Keep these as workflow roles first. Do not create live profiles until the workflow proves a recurring need.

| Role | Job | Output |
| --- | --- | --- |
| Archivist | Finds and inventories bounded source batches | Source inventory note |
| Extractor | Pulls candidate claims from the batch | Extraction JSON/Markdown |
| Verifier | Tests claims against evidence and transferability | Verified or rejected learning note |
| Framework Builder | Converts verified learnings into teachable models | Framework draft |
| Editor | Turns drafts into practical teaching assets | Final review packet or asset |

## Context Safety

Every job prompt must include:

- the current batch only;
- links or paths to source evidence;
- the extraction schema;
- the quality gate;
- a hard instruction not to infer from unrelated memory unless explicitly asked.

Every job prompt must avoid:

- loading all sessions;
- loading the whole Obsidian vault;
- mixing unrelated business domains in one batch;
- treating memory summaries as final truth without checking source evidence;
- promoting clever but weak lessons.

## First Month Milestones

### Milestone 1: Foundation

- Confirm source paths and read-only access.
- Create the Obsidian folder structure.
- Create the first source inventory.
- Run one manual extraction batch.
- Reject at least one weak claim to prove the quality gate is real.

### Milestone 2: Cadence

- Add a conservative cron or Kanban-driven recurring lane.
- Process five historical batches.
- Produce the first weekly review packet.
- Keep all outputs local/private.

### Milestone 3: Frameworks

- Promote three verified learnings into framework drafts.
- Produce one case study from the Hermes story.
- Produce one "teach this to another business" playbook.
- Review whether a dedicated profile is justified.

## Approval Boundaries

Human approval required before:

- enabling or changing live cron jobs;
- creating new Hermes profiles;
- editing `USER.md`, `SOUL.md`, built-in memory, or provider config;
- writing broad Obsidian indexes that claim canonical authority;
- publishing or sharing material outside the private vault/repo;
- using customer-specific details in teaching assets.

Safe without additional approval:

- repo-side docs and schema changes;
- read-only inventory;
- local/private draft notes;
- rejected-claim logs;
- human-review packets.

## Definition Of Done For Setup

The first setup pass is complete when:

- this operating plan exists;
- the kickoff handoff exists;
- the extraction schema exists and validates as JSON;
- the seed Kanban model exists;
- the handoff includes a ready-to-paste Hermes prompt;
- no live cron/profile/memory/Obsidian mutation has been made without explicit approval.
