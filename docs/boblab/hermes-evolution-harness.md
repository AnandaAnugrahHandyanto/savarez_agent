# Hermes Evolution Harness v1

> **Tracked in Linear:** ADR-110 — *BobLab v1 — Hermes evolution harness anchored by Reddit ingestion benchmark*

## Purpose

This document turns the AutoAgent reference into a concrete Hermes/BobLab operating loop.
The goal is not to optimize Hermes in the abstract; it is to make Hermes better at the actual workflows Adrian keeps doing.

The loop is:
1. find a recurring workflow from prior conversations,
2. convert it into a benchmark,
3. score runs with a keep/refine/discard rubric,
4. implement the smallest reusable improvement,
5. verify the result with tests and live evidence,
6. promote durable wins into skills, docs, or benchmarks.

## Why this exists

AutoAgent’s core lesson is that the fastest way to improve an agent harness is to stop hand-waving about "better reasoning" and instead build a repeatable evaluation loop.
Hermes already has the infrastructure that matters:

- `session_search` for cross-session recall
- `memory` for durable facts
- `skill_manage` for procedural memory
- `delegate_task` for parallel diagnosis / implementation / review
- `cronjob` for recurring automation
- Obsidian as the vault / system of record for durable doctrine
- Linear as the execution system of record

What we needed was the missing bridge: a benchmark-driven improvement ritual.

## Operating principles

- **Benchmark real work, not synthetic vibes.**
- **Start from a concrete prior workflow.**
- **Prefer reusable harness improvements over one-off hacks.**
- **Verify with evidence, not just output quality.**
- **Keep the loop small enough to repeat often.**
- **Promote durable wins into skills/docs only after they are proven.**

## Canonical first benchmark: Reddit ingestion playbook

The first benchmark example is the Reddit ingestion workflow discussed in earlier conversations.
It is an ideal first benchmark because it is already grounded in real use and exercises multiple Hermes strengths at once.

Relevant source sessions:
- `20260419_120319_12b8cd7c` — Reddit ingestion playbook and canonicalization work
- `20260421_094459_f74e73fa` — batch ingestion / duplicate-first maintenance workflow

### Benchmark objective
Given a Reddit link or Reddit-derived pointer, Hermes should produce a durable, correct Obsidian bookmark write-back.

### Required behaviors
- Run duplicate-first preflight in the bookmark corpus.
- Resolve the canonical target when the Reddit post is only a discovery pointer.
- Preserve the Reddit URL as provenance / source context.
- Write or update the canonical bookmark note in the proper raw bookmark folder.
- Update index, topic, and log references when counts or graph links change.
- Pass the relevant validators.

### Success criteria
- Canonical URL is chosen correctly.
- Source provenance is preserved.
- No duplicate canonical note is created.
- The bookmark note matches the vault schema.
- Index/topic/log maintenance is complete.
- Validation passes.

### Failure modes
- Treating the Reddit link itself as canonical when it is only a pointer.
- Skipping exact or near-duplicate checks.
- Losing source_context or provenance.
- Writing a note without updating the surrounding graph.
- Failing to verify the result.

### Score rubric
Suggested outcome mapping:

| Outcome | Meaning |
|---------|---------|
| `keep` | Correct canonicalization, complete write-back, validation passes |
| `refine` | Mostly correct but missing one cleanup step or graph update |
| `discard` | Wrong canonical target, duplicate note, or no verification |

## Benchmark template

For any new benchmark, capture:

- **Name**
- **Source workflow / session reference**
- **Purpose**
- **Input shape**
- **Required tools / context**
- **Expected output**
- **Success criteria**
- **Failure modes**
- **Scoring rubric**
- **Verification commands**
- **Durable promotions**

The reusable template lives in the evolution-harness skill reference:
`~/.hermes/skills/operational/hermes-evolution-harness/references/benchmark-template.md`

## Implementation loop

### 1. Research
Use `session_search`, the vault, and existing docs to identify repeated workflows and failure modes.

### 2. Shape the benchmark
Write a benchmark spec before changing the harness.
If the benchmark is unclear, the improvement is probably under-shaped.

### 3. Track it in Linear
Use BobLab as the project system of record.
Track the work in a real issue, not just in chat.

### 4. Implement the smallest reusable improvement
Prefer general harness changes over task-specific shortcuts.
If code changes are required, use TDD.
If the improvement is procedural, make it a skill or durable doc.

### 5. Verify
Use the relevant automated checks and live evidence.
For the Reddit ingestion benchmark, that means checking vault write-back and validators.

### 6. Decide
After a run, choose one:
- keep
- refine
- discard

### 7. Promote durable wins
If the improvement is reusable, save it as a skill.
If it is a doctrine pattern, write it into the vault.
If it is a recurring benchmark, keep it in Linear / BobLab.

## Evidence expected for the first run

The first complete benchmark run should capture:

- the exact Reddit link or share link used
- the canonical URL chosen
- the final bookmark path
- validator output
- any index or topic note changes
- the Linear issue / project reference
- the keep/refine/discard decision

## Verification commands

For repository-level verification of this harness document and its companion test, use:

- `pytest tests/docs/test_hermes_evolution_harness_doc.py -q`
- `git diff --check`

For the real bookmark workflow itself, use the vault validators that already protect the bookmark corpus.

## Why this should compound

If Hermes can repeatedly convert real prior workflows into benchmarked improvements, then every conversation becomes input to the next generation of the harness.
That is the AutoAgent lesson applied to Hermes:
- the system learns from itself,
- the learning is measurable,
- and the wins get packaged back into durable memory.
