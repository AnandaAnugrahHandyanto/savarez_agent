# Session retention and context budget operations

Hermes production instances can accumulate many non-human sessions when scheduled
jobs or proof loops run through the normal conversation store. Treat `state.db`
as a conversation database, not as a bulk run ledger.

## Default retention policy

- Human channels (`discord`, `telegram`, `cli`) stay in the primary session DB
  unless an operator explicitly exports or archives them.
- `cron` sessions are operational run records. Keep recent ended cron sessions in
  the primary DB for short-term debugging; archive older ended sessions before
  pruning them.
- Never raw-copy or publish `state.db`, archive DBs, OAuth/session stores, or
  auth files. Evidence reports should contain aggregate counts and file paths,
  not raw message bodies or secrets.

## Audit

Run a non-mutating health report:

```bash
hermes sessions doctor --output ~/.hermes/archives/session-doctor-$(date +%Y%m%d-%H%M%S).json
```

The report includes aggregate counts by source, active-session counts, recent
source/day growth, message storage by role, and risk flags such as
`CRON_DOMINATES_SESSION_STORE` and `STATE_DB_LARGE`.

## Archive-before-prune

Use dry-run first:

```bash
hermes sessions archive-prune --source cron --older-than 7 --dry-run
```

Then archive, back up, prune, and vacuum:

```bash
hermes sessions archive-prune --source cron --older-than 7 --yes
```

The command writes three artifacts under `~/.hermes` by default:

- `backups/state-before-cron-archive-prune-*.db`
- `archives/state-cron-archive-*.sqlite`
- `archives/state-cron-archive-prune-*.json`

The delete step is refused unless the archive row count matches the candidate
session count. Parent pointers from retained sessions to archived sessions are
nulled before delete.

## Context budget rule of thumb

For long Factory/Intelligence work:

1. Put long command output, DB audits, and proof logs in evidence files.
2. Report only compact aggregate facts plus evidence paths in chat.
3. Route repetitive worker runs to file/Kanban/Obsidian ledgers instead of
   keeping raw transcripts in one long Discord session.
4. Use `sessions doctor` before changing compression thresholds. Raising the
   threshold hides pressure; reducing raw context and cron-session growth fixes
   it.
