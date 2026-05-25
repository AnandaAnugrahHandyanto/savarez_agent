# Learning Foundry Seed Kanban

This is a seed board model, not a live Kanban mutation.

## Board

Recommended board name:

```text
hermes-learning-foundry
```

Recommended owner:

```text
default
```

Do not create a dedicated profile until the first manual batch and weekly review prove that a recurring specialist identity is useful.

## Columns

| Column | Purpose | WIP |
| --- | --- | --- |
| Sources to Inventory | Candidate source batches waiting to be scoped | 10 |
| Ready for Extraction | Small source batches ready for one run | 3 |
| Claims Extracted | Candidate claims with at least one evidence pointer | 20 |
| Needs Evidence | Claims that sound useful but lack enough proof | 10 |
| Verified Learnings | Claims that survived verifier review | 10 |
| Framework Draft | Teachable model drafts | 3 |
| Teaching Asset | Human-review-ready assets | 5 |
| Rejected or Parked | Weak, unsafe, too-specific, or premature claims | No limit |

## Seed Cards

### Card 1: Confirm Learning Foundry live paths

Owner: `default`

Scope:

- Confirm Hermes home.
- Confirm session search/state DB access.
- Confirm Obsidian vault path.
- Confirm repo path.
- Confirm no live mutation is needed for the first pass.

Done when:

- A setup report lists each confirmed path and command/source used.

### Card 2: Create private Obsidian folder structure

Owner: `default`

Approval boundary:

- Allowed only after Gabriel approves the Hermes-side setup prompt or explicitly asks Hermes to proceed.

Folders:

- `Hermes/Learning Foundry/00 Inbox/`
- `Hermes/Learning Foundry/01 Source Inventories/`
- `Hermes/Learning Foundry/02 Extracted Claims/`
- `Hermes/Learning Foundry/03 Verified Learnings/`
- `Hermes/Learning Foundry/04 Framework Drafts/`
- `Hermes/Learning Foundry/05 Teaching Assets/`
- `Hermes/Learning Foundry/90 Rejected or Parked/`

Done when:

- Folder structure exists.
- A readback verifies the headings in the first index note.

### Card 3: Run first manual extraction batch

Owner: `default`

Batch:

- 2026-05-20 Hermes operating-model and memory/Obsidian lane.

Inputs:

- `docs/refactor-plans/hermes-learning-foundry-2026-05-22.md`
- `docs/handoffs/hermes-learning-foundry-kickoff-2026-05-22.md`
- `schemas/learning-foundry-extraction.schema.json`
- `docs/refactor-plans/hermes-memory-obsidian-architecture-handoff-2026-05-20.md`
- `docs/refactor-plans/hermes-kanban-operating-model-2026-05-20.md`

Done when:

- Extraction output follows the schema.
- At least one claim is verified.
- At least one weak claim is rejected or parked.
- Setup report recommends whether recurring cron is ready.

### Card 4: Weekly review packet

Owner: `default`

Trigger:

- Only after at least five bounded batches have been processed.

Done when:

- A private review packet lists the strongest learnings, weakest recurring false positives, and top framework candidates.
- Gabriel can approve, reject, or redirect the next month of extraction.

## Anti-Overload Rules

- One card equals one bounded source batch or one review packet.
- Never combine unrelated domains just because they share a date.
- Never ask an agent to read all session history in one task.
- Never promote a framework from memory summary alone.
- Prefer one strong teaching asset over many thin notes.
