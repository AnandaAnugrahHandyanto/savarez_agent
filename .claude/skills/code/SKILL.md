<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/code/SKILL.md
Original purpose: Deep source-code verification — confirms code is actually connected, reachable, and executing.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: code
description: Use PROACTIVELY during active development when user says "check this code I'm working on", "quick review of this WIP", "is this actually executing", "confirm the wire", or needs fast execution verification on work-in-progress. Deep source-code verification — file inventory, line-by-line reading, wire trace across boundaries, explicit WIRING CONFIRMED vs EXECUTION PROVEN split. DO NOT USE for submitted diffs, PRs, or committed changes presented for review — that is the code-reviewer sub-agent. Distinct from chen sub-agent (latent-defect audit on existing code) and grep-verifier sub-agent (textual claim check).
disable-model-invocation: true
context: fork
argument-hint: "[file, function, or subsystem to verify]"
effort: max
allowed-tools: Bash(grep *) Bash(rg *) Bash(cat *) Bash(head *) Bash(tail *) Bash(wc *) Bash(find *) Bash(npx tsc *) Read Grep Glob
---

# CODE — Deep Source Code Verification

Confirm with 100% certainty that this code is connected and executing.

**Target**: $ARGUMENTS

## This Is Not Import Tracing

"This function is imported" is not proof it executes.
"This event is emitted" is not proof it's consumed.
"This write exists" is not proof the downstream reader finds it.

You must answer ALL of these for every critical path in scope:
1. **Is the code connected?** (import chain exists)
2. **Is it reachable?** (no dead branches, no unreachable conditions)
3. **Is it executing?** (the trigger actually fires in production scenarios)
4. **Is the output consumed?** (something reads what this writes)
5. **Is the state written where the downstream code actually reads it?** (same table, same column, same format)
6. **On partial success, what does downstream do?** (half-written state)
7. **On failure, what state remains behind?** (orphaned records, stale flags)

## Protocol

### Step 1: File Inventory
List every file in scope. For each:
```bash
wc -l {file}
head -5 {file}  # confirm it's the right file
```

### Step 2: Read Every Line
For each file in scope, read the FULL file. Not targeted sections. Every line. For files over 500 lines, read in chunks but cover 100%.

Note as you read:
- Every function definition
- Every export
- Every import
- Every DB read/write
- Every external call
- Every error/catch handler
- Every conditional branch
- Every return path

### Step 3: Wire Trace Every Connection
For every function that calls another or writes to a DB:
```bash
# Who calls this function?
grep -rn '{function_name}' --include="*.ts" src/

# What does this function call?
grep -n 'await\|\.then\|import' {file} | head -30

# Where does this write go?
grep -n 'insert\|update\|upsert\|\.set\|\.save' {file}
```

Trace the full chain: caller → function → callee → persistence → reader

### Step 4: Execution Proof
For each connection, explicitly answer:
- **WIRING CONFIRMED** — the import/call exists
- **EXECUTION PROVEN** — I can prove this runs in production (called from live orchestrator, triggered by live event, etc.)
- **EXECUTION NOT PROVEN** — wired but I can't confirm it actually runs without runtime evidence

Never collapse WIRING CONFIRMED and EXECUTION PROVEN into one answer.

### Step 5: Protocol-Violation Sweep
For every catch/error handler found in Step 2, check the project's highest-severity-protocol-violation patterns (see your project's inviolable-decisions list). Example: no catch block may return a "verified success" status with maximum confidence. Any match = P0. Stop everything else and report.

## Output Format

```
╔══════════════════════════════════════════════════╗
  DEEP CODE VERIFICATION
  Target: {subsystem}
  Files: {N} | Lines: {N total}
╚══════════════════════════════════════════════════╝

FILE INVENTORY:
  {file} — {lines} lines — {purpose}
  ...

WIRE TRACES:
  {caller} → {function} → {callee}
    Wiring: CONFIRMED
    Execution: PROVEN / NOT PROVEN
    Data shape: MATCHED / MISMATCHED at {point}

  ...

PROTOCOL SWEEP: {CLEAN / ⚠️ VIOLATION at {file}:{line}}

EXECUTION PROOF SUMMARY:
  PROVEN: {N} connections
  NOT PROVEN: {N} connections (list each with what runtime evidence is needed)

VERDICT: {ALL EXECUTING / PARTIALLY PROVEN / CANNOT CONFIRM}
```
