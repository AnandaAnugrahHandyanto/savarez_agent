# HANDOFF STATUS — NexusOS V1.5 Miya-mediated 1:1 prep

## What this is
Product/architecture handoff for the next iteration of NexusOS 1:1 prep.

Goal: move from **service directly sends prep note to Michael** to **service deterministically decides due-ness, then Miya authors/sends the note, with deterministic fallback only if Miya misses SLA**.

## Why this change
Current V1 deterministic layer is good on recurrence math and timing, but architecturally wrong for the desired product boundary if it authors/sends the normal founder-facing prep note itself.

Desired boundary:
- **NexusOS deterministic layer = clock / scheduler / dedupe / fallback / audit**
- **Miya = author / founder-facing voice / normal delivery path**

## Current implementation state
Implemented in repo now:
- deterministic recurrence engine preserved
- file-backed schedule registry preserved
- file-backed occurrence queue under `HERMES_HOME/projects/people-manager/prep-queue/`
- due occurrence lifecycle states persisted with history + reminder-log events
- Miya bridge worker added as an explicit transitional path
- deterministic fallback direct-send retained as safety net only

Current operator CLI surface:
```bash
python scripts/one_on_one_prep.py --help
# commands:
# list, show, preview, due-now, enqueue-due, miya-claim-next, miya-mark-sent,
# run-fallback, run-once, add, update, set-style, enable, disable, remove, log, audit

python scripts/miya_one_on_one_bridge.py --help
# command:
# run-once
```

Current seeded Miya registry confirms active schedules for:
- Thomas
- Fiona
- Hoekit
- Jeffrey
- Alex
- Steve

## Product decision now handed to Jack3
Implement **V1.5 Miya-mediated flow**:
- scheduler/service still computes due occurrences deterministically
- scheduler/service should queue an internal `one_on_one_prep_due` event instead of directly sending the normal prep note
- Miya should consume the event and send the actual prep note via the normal Telegram assistant path
- if Miya does not complete within a short SLA, service sends a minimal deterministic fallback note directly

## Files to inspect first
- `docs/plans/2026-04-20-nexusos-v1-5-miya-mediated-1o1-prep-design.md`
- `scripts/one_on_one_prep.py`
- `people_manager/schedule_store.py`
- `people_manager/reminder_log.py`
- `people_manager/prep_renderer.py`
- existing tests under `tests/scripts/test_one_on_one_prep.py`

## Likely files to modify
- `scripts/one_on_one_prep.py`
- `people_manager/reminder_log.py`
- `people_manager/` new queue/event helper module(s)
- gateway/agent-side internal task handling path for Miya
- tests for queueing, SLA timeout, fallback suppression, stale completion suppression

## Recommended implementation shape
### Core behavior
1. detect due occurrence deterministically
2. create a queued event with deterministic dedupe key
3. Miya claims and processes event
4. Miya sends founder-facing note
5. mark `sent_by_miya`
6. if no completion by deadline, fallback sends minimal note and marks `fallback_sent`

### Occurrence key
- `<profile_slug>::<meeting_at_iso>`

### Suggested state machine
- `due_detected`
- `queued_for_miya`
- `claimed_by_miya`
- `sent_by_miya`
- `fallback_sent`
- `failed`
- `cancelled`
- `stale_completion_suppressed`

## Constraints
- keep report-specific state under people-manager project storage; do **not** move this into global memory
- preserve `/people` boundary discipline
- do not let scheduler impersonate Miya in steady state
- fallback direct-send is allowed only as reliability safety net
- prefer deterministic queue/event state over prompt-cron orchestration hacks
- preserve exact 5-minute-before recurrence semantics

## Verification target
Need proof for all of the below:
1. due occurrence queues correctly
2. Miya-path send marks success and suppresses fallback
3. missed SLA triggers fallback exactly once
4. late Miya completion does not create duplicate send
5. audit/log surfaces occurrence state clearly
6. no regression to recurrence math across weekly/biweekly/monthly schedules

## Current verification facts gathered by Miya
- `python scripts/one_on_one_prep.py --help` succeeds
- `python scripts/one_on_one_prep.py list` succeeds
- seeded Miya schedule store currently shows correct next due times for all six known reports

## Test status
Verified after implementation:
- `source venv/bin/activate && pytest tests/scripts/test_one_on_one_prep.py tests/scripts/test_miya_one_on_one_bridge.py tests/people_manager/test_schedule_store.py tests/people_manager -q`
- Result: `62 passed`

Coverage now includes:
- recurrence regression protection across weekly / biweekly / monthly schedules
- due event queue creation
- Miya success suppressing fallback
- fallback firing once after SLA miss
- stale Miya completion suppression after fallback
- audit/log state visibility
- transitional Miya bridge worker success + failure behavior

## Ownership transfer
From here:
- **Jack3 owns engineering design + implementation + tests**
- **Miya retains product/operator intent and will use the resulting system**

## Immediate next engineering priorities
1. choose event transport: internal file-backed queue preferred
2. define exact queue + claim + ack data model
3. wire Miya consumption path
4. implement SLA watchdog + fallback send path
5. add audit/log visibility for queued/claimed/fallback/stale states
6. write regression tests before/alongside implementation
