# NexusOS V1.5 Miya bridge runbook

## Purpose
This is the explicit transitional operator flow for Miya-mediated 1:1 prep:
- deterministic service owns timing / dedupe / fallback
- Miya still authors and normally sends the prep note
- fallback direct-send remains a safety net only

## Required Miya profile setting
Set this in the Miya profile env before using the bridge for schedules whose delivery target is `origin` or `telegram`:

```bash
MIYA_ONE_ON_ONE_DELIVERY_TARGET=telegram:546950872
```

Recommended location:
- `/Users/michael.wu/.hermes/profiles/miya/.env`

For manual shell runs outside the Miya profile, also point `HERMES_HOME` at the Miya profile so scheduler/queue state lands in the right project storage:

```bash
export HERMES_HOME=/Users/michael.wu/.hermes/profiles/miya
```

## Scheduler-side commands
Queue due events:

```bash
export HERMES_HOME=/Users/michael.wu/.hermes/profiles/miya
source venv/bin/activate
python scripts/one_on_one_prep.py enqueue-due --now 2026-04-20T13:10:00+08:00
```

Run fallback watchdog:

```bash
export HERMES_HOME=/Users/michael.wu/.hermes/profiles/miya
source venv/bin/activate
python scripts/one_on_one_prep.py run-fallback --now 2026-04-20T13:11:05+08:00
```

## Miya bridge worker command
Claim one queued occurrence, ask Miya to send it, and ack success if confirmed:

```bash
export HERMES_HOME=/Users/michael.wu/.hermes/profiles/miya
source venv/bin/activate
python scripts/miya_one_on_one_bridge.py run-once --profile miya --miya-target telegram:546950872
```

If `MIYA_ONE_ON_ONE_DELIVERY_TARGET` is set in the Miya profile env, `--miya-target` can be omitted.

## Suggested loop shape
Short-interval deterministic loop:
1. `enqueue-due`
2. `scripts/miya_one_on_one_bridge.py run-once`
3. `run-fallback`

This is intentionally explicit and auditable; it is not a hidden cron-prompt workflow.

## Notes
- `run-once` in `scripts/one_on_one_prep.py` still exists as a direct-send operator path, but it should not be used as the normal steady-state path anymore.
- Queue state is stored under `HERMES_HOME/projects/people-manager/prep-queue/`
- Reminder/audit state remains under `HERMES_HOME/projects/people-manager/reminder-log/`
