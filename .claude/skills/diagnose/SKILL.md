<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/diagnose/SKILL.md
Original purpose: Structured 4-phase bug investigation (LOCATE / CONTEXT / ROOT CAUSE / FIX PROPOSAL).
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: diagnose
description: Use PROACTIVELY when user reports an error, stack trace, unexpected behavior, test failure, or "why isn't this working". Runs a 4-phase investigation — LOCATE (live code not dead-code twin), CONTEXT (pipeline stage and affected decisions), ROOT CAUSE (bug vs. symptom vs. upstream data issue), FIX PROPOSAL (exact file:line with downstream impact, risk classification, verification command). Distinct from chen sub-agent (latent-defect audit without an active bug) and /code (execution verification without an active bug report).
disable-model-invocation: true
context: fork
argument-hint: "[error-description]"
allowed-tools: Bash(grep *) Bash(rg *) Bash(npx tsc *) Bash(find *) Bash(wc *) Bash(cat *) Bash(head *) Bash(tail *) Read Grep Glob
---

# Diagnose — Structured Bug Investigation

You are investigating a bug or error.

**Error description**: $ARGUMENTS

> **If no error description was provided**, ask: "What error or bug should I investigate? Provide an error message, stack trace, identifier, or description of the unexpected behavior."

Follow all four phases IN ORDER. Do not skip phases. Do not propose a fix until Phase 3.

---

## Phase 0: LOCATE — Find the Live Code

**Goal**: Identify exactly which file and line is involved, confirming it's on the LIVE execution path.

1. **Parse the error**: Extract file names, function names, line numbers, error messages, and stack traces from the description.

2. **Grep for the error site**:
   ```
   grep -rn "{error_string}" --include="*.ts" --include="*.tsx" src/
   ```

3. **DEAD CODE TRAP CHECK** — mature projects accumulate dead-code twins of live modules. Maintain a project-specific dead-code map and consult it before accepting any grep hit as the real site:

   | If you land in... | The live path is... |
   |---|---|
   | {deprecated module A} | {current module A} |
   | {legacy pipeline} | {current pipeline} |
   | Any file not imported by the orchestrator | Trace imports from the orchestrator entry point |

   **Verify the file is live**: grep for imports of the suspect file:
   ```
   grep -rn "from.*{suspect-filename}" --include="*.ts" src/
   ```
   If nothing imports it (or only dead code imports it), you're in the wrong file.

4. **Confirm the execution path**: Starting from the entry point, trace the call chain to the error site. Document each hop.

**Output**: "The error originates at `{file}:{line}` in function `{name}`. Confirmed LIVE — imported by `{parent}` via `{chain}`."

---

## Phase 1: CONTEXT — Understand Where You Are

**Goal**: Map the error to the pipeline architecture so you understand blast radius.

1. **Which pipeline stage?** (or which subsystem, if not a linear pipeline)
2. **Which tier / tenant / variant affected?** (if applicable)
3. **Related project-specific decisions**: grep the error site for decision IDs or binding-rule references. Also check `CLAUDE.md` for relevant inviolable rules.
4. **Downstream consumers**: What reads the output of this code?
5. **Upstream producers**: What feeds data INTO this code? A bug here might actually be a data-quality issue from upstream.

**Output**: "Stage {N}, variant {X}, governed by decisions {list}. Downstream: {consumers}. Upstream: {producers}."

---

## Phase 2: ROOT CAUSE — Bug vs. Symptom

**Goal**: Determine whether the error site IS the bug, or just where a deeper bug surfaces.

Apply these diagnostic patterns:

1. **Handoff issue check**: Is the data arriving at this function malformed?
   - Does the input field contain what the producer should have written?
   - Are IDs in the expected namespace/format?
   - Is JSON intact, or did a repair/truncation step silently cut it?

2. **Schema mismatch check**: Does the code expect a column/field that doesn't exist, or has a different type?
   ```
   grep -n "{field_name}" src/types/ --include="*.ts"
   ```

3. **Protocol-violation check**: If this involves a catch/error path, apply your project's highest-severity-protocol-violation rule (see your project's `.claude/rules/` or inviolable-decisions list).

4. **Config-drift check**: Is the right config value being used? Cross-reference against the project's config module.

5. **External-identifier check**: If an external API or service is involved, verify identifiers against the project's reference map (API ID registries, court codes, region IDs, etc.).

**Output**: "ROOT CAUSE: {description}. This is a {BUG / UPSTREAM DATA ISSUE / SCHEMA MISMATCH / PROTOCOL VIOLATION}. The error at {site} is {the bug itself / a symptom of {deeper issue}}."

---

## Phase 3: FIX PROPOSAL

**Goal**: Propose an exact fix with full awareness of downstream impact.

For each proposed change:

1. **Exact location**: `{file}:{line}` — quote the current code
2. **Proposed change**: Show the replacement code
3. **Why this fixes it**: Connect back to root cause from Phase 2
4. **Downstream impact**: List every consumer identified in Phase 1 and confirm they're unaffected (or describe required cascading changes)
5. **Protocol audit**: Confirm the fix does not introduce any violation of the project's inviolable rules
6. **Dead-code check**: Confirm the fix targets the LIVE file, not the dead-code twin
7. **Test strategy**: How to verify the fix works (SQL query, curl command, specific identifier to re-run, etc.)

### Fix Classification

- **SAFE**: Isolated change, no downstream impact, no protocol risk
- **MODERATE**: Downstream consumers exist but change is additive
- **HIGH RISK**: Changes scoring, routing, verdicts, or handoff format — requires stress testing
- **PROTOCOL RISK**: Touches error/catch paths or inviolable-rule surfaces — requires explicit audit of all catch blocks in the modified function

---

## Reporting

```
╔══════════════════════════════════════════╗
  DIAGNOSIS: {one-line summary}
╚══════════════════════════════════════════╝

PHASE 0 — LOCATE
  File: {path}:{line}
  Function: {name}
  Live path: CONFIRMED / ⚠️ DEAD CODE

PHASE 1 — CONTEXT
  Stage: {identifier}
  Variants: {affected}
  Decisions: {list}
  Downstream: {consumers}

PHASE 2 — ROOT CAUSE
  {description}
  Type: BUG / UPSTREAM / SCHEMA / PROTOCOL

PHASE 3 — FIX PROPOSAL
  Risk: SAFE / MODERATE / HIGH / PROTOCOL RISK
  Location: {file}:{line}
  Change: {summary}
  Protocol: CLEAN / ⚠️ VIOLATION
```

---

## Historical Note

AI-assisted audit history shows a **38-54% false positive rate** in AI-generated findings. Before presenting any finding as confirmed, grep-verify the actual source code. If you cannot find grep evidence for a bug, say so — do not present unverified claims. Intellectual honesty is worth more than a confident-sounding diagnosis.
