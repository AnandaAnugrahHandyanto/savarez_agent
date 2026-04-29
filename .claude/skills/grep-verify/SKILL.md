<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/grep-verify/SKILL.md
Original purpose: Fact-checks claims about the codebase with grep evidence, rating each CONFIRMED / LIKELY / INDETERMINATE / FALSE POSITIVE.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: grep-verify
description: >
  Fact-checks claims about the codebase against actual source code using grep evidence.
  For each claim, searches the codebase and rates it CONFIRMED (grep evidence found),
  LIKELY (indirect evidence), INDETERMINATE (can't prove from static analysis), or FALSE
  POSITIVE (no evidence). Essential for auditing AI-generated findings, which historically
  have a 38-54% false positive rate. Manual invocation only — use /grep-verify [claim].
disable-model-invocation: true
context: fork
argument-hint: "[claim-to-verify]"
allowed-tools: Bash(grep *) Bash(rg *) Bash(find *) Bash(cat *) Bash(head *) Bash(tail *) Bash(wc *) Read Grep Glob
---

# Grep-Verify — Codebase Claim Verification

> Also invokable as `/gv` (alias). Preloaded in the `grep-verifier` sub-agent.

You are verifying a claim about the codebase against actual source code.

**Claim to verify**: $ARGUMENTS

> **If no claim was provided**, ask: "What claim should I verify? Provide an assertion about the code, a finding from an audit, or a suspected bug."

---

## The Problem This Solves

AI-generated audit findings have historically had a **38-54% false positive rate**. That means roughly half of all "bugs found" by AI audits don't actually exist in the code. This skill exists to enforce intellectual honesty: no claim ships without grep evidence.

---

## Verification Protocol

### 1. Decompose the Claim

Break the claim into individual, testable assertions. A single claim like "service A doesn't populate field X before passing to service B" contains multiple checkable facts:
- Does service A write to `field X`?
- Where does it write?
- What value does it write?
- Does service B read `field X`?
- Is there a code path where it could be empty?

### 2. Search for Evidence

For each assertion, run targeted grep commands:

```bash
# Exact string match
grep -rn "field_X" --include="*.ts" --include="*.tsx" src/

# Function definitions
grep -rn "function {functionName}\|const {functionName}" --include="*.ts" src/

# Assignments / writes
grep -rn "field_X\s*=" --include="*.ts" src/

# Imports / usage chain
grep -rn "from.*{module}" --include="*.ts" src/
```

**Search tips:**
- Always scope by file extension — other files will pollute results.
- Search source directories — never `node_modules/`, build output, or cache dirs.
- Maintain a project-specific list of known dead-code paths (old modules kept for compat, deprecated layers). Findings in those paths are automatically FALSE POSITIVE for live-system impact.

### 3. Rate Each Assertion

| Rating | Criteria | Action |
|--------|----------|--------|
| **CONFIRMED** | Grep output directly proves or disproves the assertion. You can cite file:line. | Report with evidence |
| **LIKELY** | Indirect evidence supports the assertion but you can't trace the full flow without runtime data. | Report with caveats |
| **INDETERMINATE** | Can't prove or disprove from static analysis alone. Would need runtime data. | Report honestly — do NOT upgrade to CONFIRMED |
| **FALSE POSITIVE** | Grep evidence directly contradicts the assertion. The code does the opposite of what was claimed. | Report with counter-evidence |

### 4. Check for Dead Code Traps

For every file referenced in your grep results, verify it's on the live execution path:

```bash
# Is this file imported by anything?
grep -rn "from.*{filename}" --include="*.ts" src/
```

If a file has zero importers — or only dead code imports it — findings in that file are automatically **FALSE POSITIVE** for live-system claims (they may still be valid cleanup items).

### 5. Cross-Reference Project Decisions

If the claim references a project-specific decision ID, rule code, or binding decision, verify its implementation:
```bash
grep -rn "{decision-id}" --include="*.ts" --include="*.md" .
```

---

## Output Format

```
╔══════════════════════════════════════════════════╗
  GREP-VERIFY REPORT
╚══════════════════════════════════════════════════╝

CLAIM: "{original claim}"

ASSERTION 1: {decomposed assertion}
  VERDICT: CONFIRMED / LIKELY / INDETERMINATE / FALSE POSITIVE
  EVIDENCE:
    {file}:{line} — {relevant code snippet}
    {file}:{line} — {relevant code snippet}

ASSERTION 2: {decomposed assertion}
  VERDICT: ...
  EVIDENCE: ...

────────────────────────────────────────────────────
OVERALL: {CONFIRMED / PARTIALLY CONFIRMED / FALSE POSITIVE}

{If FALSE POSITIVE: explain what the code actually does}
{If CONFIRMED: summarize the verified finding}
────────────────────────────────────────────────────
```

---

## Rules

1. **Only report CONFIRMED findings as definitive.** Everything else gets caveats.
2. **Show your grep commands.** The human should be able to reproduce your search.
3. **Quote actual code.** Don't paraphrase — show the exact line from the file.
4. **If you can't find evidence, say so.** "I could not find grep evidence for this claim" is a valid and valuable result.
5. **Dead code findings are not live-system bugs.** If the only evidence is in a dead-code file, the claim is FALSE POSITIVE for production purposes.
6. **Never upgrade INDETERMINATE to CONFIRMED** just because the claim "sounds right." The entire point of this skill is to combat that instinct.
