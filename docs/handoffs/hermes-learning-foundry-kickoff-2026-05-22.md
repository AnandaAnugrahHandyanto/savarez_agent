# Hermes Learning Foundry Kickoff - 2026-05-22

## Purpose

Use this handoff to start the Hermes-side Learning Foundry setup on Atlas.

The goal is to continuously turn Hermes build history, session history, repo work, Obsidian notes, failures, and decisions into evidence-backed lessons and teachable frameworks for other businesses.

## Read First

- `docs/refactor-plans/hermes-learning-foundry-2026-05-22.md`
- `schemas/learning-foundry-extraction.schema.json`
- `artifacts/learning-foundry/seed-kanban.md`
- `docs/refactor-plans/hermes-memory-obsidian-architecture-handoff-2026-05-20.md`
- `docs/refactor-plans/hermes-kanban-operating-model-2026-05-20.md`
- `docs/refactor-plans/hermes-cron-profile-approval-fix-2026-05-21.md`

## Non-Negotiables

- Do not load all session history at once.
- Do not load the whole Obsidian vault at once.
- Do not create a new live profile yet.
- Do not edit live cron jobs until the first manual batch proves quality.
- Do not edit `USER.md`, `SOUL.md`, built-in memory, or memory provider config.
- Do not copy raw session dumps into Obsidian.
- Do not publish anything externally.
- Every lesson must point to concrete evidence.

## Recommended First Hermes Session Prompt

```text
You are setting up the Hermes Learning Foundry on Atlas.

Goal:
Create the first private, evidence-backed learning extraction lane for Hermes. The lane should progressively convert Hermes session history, repo artifacts, Obsidian notes, decisions, failures, and implementation outcomes into verified learnings, frameworks, case studies, and teaching assets that could help another business implement practical AI operating systems.

Read these repo files first:
- docs/refactor-plans/hermes-learning-foundry-2026-05-22.md
- docs/handoffs/hermes-learning-foundry-kickoff-2026-05-22.md
- schemas/learning-foundry-extraction.schema.json
- artifacts/learning-foundry/seed-kanban.md
- docs/refactor-plans/hermes-memory-obsidian-architecture-handoff-2026-05-20.md

Constraints:
- Work read-only against session history and existing Hermes/Obsidian sources unless explicitly approved.
- Do not create or change live cron jobs in this first pass.
- Do not create new profiles.
- Do not mutate USER.md, SOUL.md, built-in memory, provider config, Blue/GHL state, customer data, or public publishing surfaces.
- Do not load all sessions or the full vault into one prompt.
- Use small source batches only.
- Treat memory summaries as routing indexes, not final truth.
- Every extracted claim must include evidence pointers.
- Weak or clever-sounding claims should be rejected or parked, not promoted.

First-pass tasks:
1. Confirm the live Atlas paths for Hermes home, session search/state DB, and Obsidian vault.
2. Create the private Obsidian folder structure under:
   /home/atlas/Documents/Obsidian Vault/Hermes/Learning Foundry/
3. Create a first source inventory note for one bounded source batch. Recommended seed batch: the Hermes operating-model and memory/Obsidian work from 2026-05-20, because it already has clear rollout summaries and repo docs.
4. Run one manual extraction batch using schemas/learning-foundry-extraction.schema.json as the shape.
5. Verify the candidate claims against at least two source types when possible, such as MEMORY.md plus repo docs or raw session snippets.
6. Promote only the strongest findings to a verified-learning note.
7. Reject or park at least one weak claim, with the reason, to prove the quality gate is real.
8. Write a short setup report with:
   - paths confirmed;
   - files created;
   - batch processed;
   - claims extracted;
   - claims verified;
   - claims rejected;
   - recommended cron/Kanban next step;
   - whether a dedicated profile is justified yet.

Success criteria:
- The first batch is small and traceable.
- The output is useful to Gabriel as future teaching material.
- No live cron/profile/memory/customer mutations occur.
- The setup report gives a clear approval boundary for enabling recurring runs later.
```

## First Batch Recommendation

Start with the 2026-05-20 Hermes operating-model and memory/Obsidian lane because it is rich but bounded.

Useful source files:

- `docs/refactor-plans/hermes-update-operating-model-session-plan-2026-05-20.md`
- `docs/refactor-plans/hermes-memory-obsidian-architecture-handoff-2026-05-20.md`
- `docs/refactor-plans/hermes-kanban-operating-model-2026-05-20.md`
- `docs/refactor-plans/hermes-profile-strategy-and-eval-coverage-2026-05-20.md`
- Codex memory entries for Hermes operating-model planning and memory hygiene.
- Raw session snippets only when a claim needs stronger evidence.

Why this batch:

- It already contains explicit lessons about memory pressure, durable knowledge layers, read-only sessions, profile boundaries, and Kanban.
- It is directly relevant to teaching others how to avoid AI operating-system drift.
- It does not require touching Blue/GHL customer state.

## Suggested First Framework Candidates

These are candidates only. Hermes must verify them before promotion.

1. **Hot Index, Cold Library**
   - Built-in memory should stay tiny and injected.
   - Obsidian/repo docs should hold durable explanation.
   - Session search should recover evidence.

2. **Read-Only Does Not Mean Low-Value**
   - A read-only agent can still produce recommendations, next actions, approval boundaries, and handoff prompts.

3. **Evidence Before Automation**
   - Do not create profiles, cron jobs, or memory changes until a manual path proves quality.

4. **Small Batch, Strong Claim**
   - Avoid huge-context synthesis. Use bounded batches, evidence pointers, and promotion gates.

## Recurring Run Prompt Template

```text
You are running one Hermes Learning Foundry batch.

Use only the assigned batch and the Learning Foundry schema. Do not broaden into unrelated sessions, repo areas, or Obsidian folders.

Batch:
- batch_id: <fill>
- source theme: <fill>
- source paths/session IDs: <fill>
- date range: <fill>

Tasks:
1. Inventory the source batch.
2. Extract candidate claims using schemas/learning-foundry-extraction.schema.json.
3. Verify each claim against evidence.
4. Reject weak claims.
5. Promote only proven or teachable claims into a verified-learning note.
6. If appropriate, draft one framework candidate.
7. End with a short review packet: what changed, what is strong, what is weak, and what should be processed next.

Quality rules:
- Every claim needs evidence.
- Memory summaries route you to evidence; they are not final proof.
- Do not infer from unrelated context.
- Do not mutate live cron/profile/memory/customer systems.
- Prefer one excellent framework over ten shallow lessons.
```

## Approval Request For Later

After the first manual batch, ask Gabriel before:

- enabling a daily cron;
- creating a Kanban board/card set;
- adding Mission Control UI surfaces;
- creating a dedicated Learning Foundry profile;
- promoting any output as canonical teaching doctrine.
