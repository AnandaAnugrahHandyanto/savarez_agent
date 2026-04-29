<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/session-end/SKILL.md
Original purpose: End-of-session handoff document generator — captures git state, changes, blockers, next steps.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: session-end
description: Use PROACTIVELY at end of a working session — when user says "wrap up", "end session", "write handoff", "close out", or before a long break. Generates structured handoff capturing git state, changes made, decisions reached, outstanding work, blockers, and next steps, formatted as pasteable for the next session. Also invokable as /end (alias).
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(grep *) Bash(wc *) Bash(cat *) Bash(find *) Read Grep Glob
---

# Session End — Handoff Document

> Also invokable as `/end` (alias).

Generate a structured handoff document that captures everything needed for the next session (whether that's the operator pasting into a chat, or the next Claude Code session picking up).

## Step 1: Capture Git State

Run and capture:

```
git branch --show-current
git log --oneline -10
git status
git diff --name-only
git diff --stat
```

## Step 2: Summarize Changes Made This Session

For each file modified since session start (use `git diff --name-only` against the starting commit):

1. **File path** — full path from project root
2. **What changed** — 1-2 sentence summary of the modification
3. **Why** — which bug, decision ID, or task motivated it
4. **Risk level** — LOW (cosmetic/logging), MEDIUM (logic change), HIGH (pipeline flow, routing, scoring)

If you don't know the starting commit, use the oldest commit from `git log --oneline -10` that was created during this session (check timestamps if needed, or use all uncommitted changes).

## Step 3: Decisions / Work Items Implemented

Search through the session's changes and conversation history for any decision IDs or tracked work-item references. For each one touched:

- **ID** (e.g., `D-HANDOFF-2`, `TASK-42`, `INCIDENT-7`)
- **Status**: IMPLEMENTED / PARTIALLY IMPLEMENTED / DIAGNOSED ONLY
- **Files affected**

## Step 4: What's Left To Do

List incomplete work, organized by priority:

- **P0 — Must fix before merge**: anything that would break production or violate inviolable rules
- **P1 — Should fix soon**: bugs, incomplete implementations, tech debt created
- **P2 — Can defer**: nice-to-haves, optimizations, non-blocking improvements

## Step 5: Blockers

List anything that prevents forward progress:

- Waiting on a human (migrations, production merges, approvals)
- Waiting on external data (API changes, vendor response, etc.)
- Architectural decisions needed
- Branch conflicts or dependency issues

## Step 6: Next Logical Step

State clearly: "The next session should start by doing X" — a single, concrete action. If there are multiple threads of work, list them in priority order.

## Step 7: Format as Handoff Document

```
═══════════════════════════════════════════════════════════════
  SESSION HANDOFF — {date} {time}
  Branch: {branch} | Commits this session: {count}
═══════════════════════════════════════════════════════════════

## Changes Made
{for each file: path — summary — decision ID — risk}

## Decisions / Work Items Touched
{table}

## Remaining Work
### P0 (Merge blockers)
{items}
### P1 (Should fix)
{items}
### P2 (Deferrable)
{items}

## Blockers
{items, or "None"}

## Next Step
{concrete action for next session}

## Session Stats
- Files modified: {count}
- Lines added: {count} | Lines removed: {count}
- Commits: {count}
═══════════════════════════════════════════════════════════════
```

## Important

- Be honest about incomplete work. Do not mark something IMPLEMENTED if it's only partially done.
- If a fix was applied to a known dead-code file by mistake, flag it as P0.
- If any error/catch path was modified, explicitly confirm inviolable-rule compliance.
- The handoff must be self-contained — a reader with no session context should understand what happened and what to do next.
