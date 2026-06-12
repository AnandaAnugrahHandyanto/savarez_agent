---
title: "Hermes Self Improvement Maintenance"
sidebar_label: "Hermes Self Improvement Maintenance"
description: "Quiet, non-destructive Hermes Agent self-improvement and maintenance for a user environment: audit health, apply reusable lessons to memory/skills, and avoid..."
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Hermes Self Improvement Maintenance

Quiet, non-destructive Hermes Agent self-improvement and maintenance for a user environment: audit health, apply reusable lessons to memory/skills, and avoid noisy or risky changes.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/autonomous-ai-agents/hermes-self-improvement-maintenance` |
| Version | `1.0.0` |
| Author | Mizuki |
| License | MIT |
| Tags | `hermes`, `maintenance`, `self-improvement`, `audit`, `skills`, `memory`, `cron` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Hermes Self-Improvement & Maintenance

Use this skill when the user asks the assistant to "use Hermes features," "make yourself better," review a conversation for memory/skill updates, or run a non-destructive maintenance pass over Hermes Agent itself.

## Principles

- Be useful, quiet, and evidence-driven. Do not create noise to look busy.
- Prefer non-destructive improvements: memory refinement, skill patching, cron prompt improvements, health checks, and better verification routines.
- Do not modify billing, paid providers, credentials, destructive settings, deployments, or external systems unless explicitly requested.
- Treat user style corrections and frustration as first-class learning signals: update memory for who the user is, and update the relevant skill for how future agents should perform that class of task.
- Avoid saving transient failures as durable rules. Capture a reusable fix or pattern, not "tool X is broken."

## Maintenance Pass Workflow

1. Load `hermes-agent` first when the task concerns Hermes Agent configuration, tools, gateway, cron, memory, skills, providers, or docs.
2. Check current state with safe read-only commands when tool use is allowed:
   - `hermes status --all`
   - `hermes memory status`
   - `hermes tools list`
   - `hermes cron list`
   - `hermes doctor`
   - Treat `hermes tools list` as enablement only; use `hermes doctor` / `hermes status --all` to verify whether enabled tools actually have credentials, paid credits, or system dependencies.
   - In cron contexts, prefer `terminal`, `read_file`, `search_files`, and `session_search` for evidence; do not rely on `execute_code`, which may be blocked because scheduled jobs run without a present user to approve arbitrary local Python.
3. For active cron jobs, inspect any local script path before declaring the job harmless. Flag jobs that can launch cloud resources, spend money, deploy, rotate credentials, or message frequently; do not pause or edit them unless explicitly instructed.
4. Identify durable user facts or preferences and save only compact declarative memory entries. In cron contexts, the `memory` tool itself may be unavailable even when `hermes memory status` is healthy; if memory is over budget, compact existing `~/.hermes/memories/USER.md` or `MEMORY.md` with `patch` rather than adding new facts, and only in the active profile. Verify with `wc -c ~/.hermes/memories/USER.md ~/.hermes/memories/MEMORY.md` and leave practical headroom instead of hovering at the limit.
5. Identify procedural lessons and patch the currently loaded relevant skill if it is editable.
6. If the relevant loaded skill is protected, prefer an existing local umbrella. If none exists, create or update this umbrella with the reusable workflow.
7. When auditing gateway/platform readiness, distinguish "configured" from "live": verify both platform config and gateway runtime state. For Discord specifically, use `references/discord-gateway-readiness-check.md` for the safe readiness checklist and Hermes-venv bot login smoke test.
8. For cron-based self-improvement, keep output concise and bounded:
   - health summary
   - what changed, if anything
   - warnings
   - one next useful move
8. Verify any change by reading the tool result: cron update result, memory update result, or skill management result.

## User-Specific Defaults for Hevar

- Hevar wants proactive help, but not noisy automation.
- Keep self-improvement non-destructive and practical.
- Respect low/no-surprise-cost preferences: do not enable paid providers or billing-adjacent features without explicit request.
- Prefer direct PC action and real verification when safe.
- For DevOps learning, preserve Hevar's ownership of the hands-on work.

## What Counts as a Good Improvement

- A memory entry that prevents Hevar repeating a stable preference.
- A skill patch that fixes a recurring bad approach.
- A cron prompt that becomes quieter, safer, or more useful.
- A reusable verification script under `scripts/` or concise session detail under `references/` when needed.
- A recommendation to the user when the next step has risk or cost.

## What Not To Do

- Do not install or enable optional paid/external providers just because docs mention them.
- Do not create one-off skills named after today's project, error, PR, or conversation.
- Do not save completed task progress, commit IDs, PR numbers, temporary bugs, or resolved setup failures to memory.
- Do not edit protected bundled or hub-installed skills.
