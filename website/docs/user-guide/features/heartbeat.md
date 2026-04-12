---
sidebar_position: 6
title: "Autonomous Heartbeat"
description: "Give Hermes a periodic wake-up loop so it can keep making useful progress between messages"
---

# Autonomous Heartbeat

Hermes can now run a first-class autonomous heartbeat: a recurring wake-up loop built on top of cron jobs, but specialized for proactive usefulness.

Instead of waiting passively for the next user message, the heartbeat wakes up on a schedule and asks:

- what recent work is still unfinished?
- what follow-ups can I advance autonomously?
- what useful maintenance, research, drafting, or implementation can I do right now?
- do I actually need to interrupt the user, or can I quietly make progress first?

If there is genuinely nothing useful to do, the heartbeat responds with `[SILENT]` and nothing is delivered.

## What makes it different from normal cron jobs?

A normal cron job runs a specific prompt on a schedule.

A heartbeat is optimized for open-ended autonomy:

- it uses a built-in prompt oriented around proactive progress
- it checks recent sessions with `session_search()` to find unfinished threads
- it opts into Hermes memory injection so the run can use the same frozen user/memory snapshot as regular chat sessions
- it encourages quiet progress first, user interruption second

## Enable it

### Standalone CLI

```bash
hermes heartbeat enable
hermes heartbeat enable --schedule "every 1h"
hermes heartbeat enable --schedule "every 3h" --mission "Advance my active coding and research threads without being noisy"
```

### In chat

```text
/heartbeat status
/heartbeat enable --schedule "every 2h"
/heartbeat enable --schedule "every 1h" --mission "Look for unfinished work and keep making progress"
/heartbeat disable
/heartbeat resume
/heartbeat run
```

## Inspect status

```bash
hermes heartbeat status
```

This shows whether the heartbeat exists, whether it is enabled, its next run time, and whether memory is enabled for those runs.

## Pause or trigger manually

```bash
hermes heartbeat disable
hermes heartbeat resume
hermes heartbeat run
```

`run` triggers the heartbeat on the next scheduler tick.

## How heartbeat runs behave

Each heartbeat run is instructed to:

1. inspect recent sessions with `session_search()`
2. identify unfinished or high-value follow-up work
3. use tools to make concrete progress
4. avoid interrupting the user unless a short blocking question would unlock meaningful work
5. return `[SILENT]` if nothing useful can be done right now

## Scheduling and delivery

The heartbeat uses the same scheduler as cron jobs, so the gateway must be running:

```bash
hermes gateway install
# or
sudo hermes gateway install --system
```

By default, the heartbeat uses the normal cron delivery behavior for wherever it was configured. If you only want local audit logs, point delivery to `local`. If you want proactive pings, use `origin` or a specific platform target.

## Relationship to OpenClaw-style heartbeats

If you're familiar with OpenClaw's heartbeat concept, this feature is Hermes' equivalent primitive:

- periodic wake-up
- recent-context review
- autonomous action
- selective reporting

The main difference is that Hermes implements it as a first-class workflow on top of its cron scheduler rather than as a separate always-running inner loop process.
