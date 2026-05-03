# BusinessOS Open Questions

## Active restoration / design questions

### 1. Downstream rebuild restoration
What is the exact desired end state for:
- feedback cluster rebuilds
- bug/feature candidate regeneration
- reply-draft export
- approval/send workflow

Current state:
- core live intake, tasking, finance summaries, health/readiness reporting, operator updates, and Dropbox mirroring are present
- the richer downstream rebuild chain is still only partially restored

### 2. Outbound workflow activation
When outbound flows are restored, what should the precise human approval UX be for:
- support email drafts
- billing/legal/privacy approvals
- Telegram support replies

### 3. Lane expansion
Should BusinessOS add more dedicated lanes or source accounts beyond the current Helix + Steady setup?
Examples:
- app store review import
- additional support/community channels
- more granular operator/admin lanes

### 4. Hindsight timing
When, if ever, should Hindsight replace Holographic as the external Hermes memory provider?

Current constraint:
- Hermes currently supports built-in memory plus only one external provider at a time

### 5. Backfill strategy for Holographic
How much existing repo truth should be seeded into Holographic beyond the initial curated facts?

Potential future options:
- keep Holographic small and curated
- add a one-shot importer for selected docs
- add a periodic sync from canonical markdown docs into structured facts

## Maintenance rule

If one of these questions is resolved, move the answer into:
- `docs/decisions.md` if it becomes a stable decision
- `docs/architecture.md` if it changes system shape
- `docs/runbook.md` if it changes operations
