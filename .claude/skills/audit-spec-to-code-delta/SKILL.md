<!--
Extracted from: prompts/superprompts/chen-audit-protocol.md § AUDIT MODES — MODE 3 — SPEC-TO-CODE DELTA AUDIT
Original purpose: Compare implementation against architecture doc, handoff notes, binding decisions, or prior outputs — produce a delta table ranked by risk.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: audit-spec-to-code-delta
description: >
  Chen's MODE 3 playbook — spec-to-code delta audit. Use when comparing a system's
  implementation against a spec, architecture document, handoff notes, binding
  decisions, task list, or prior Claude outputs. Reads code first (no spec in
  context), states actual behavior in plain English, loads the comparison doc,
  then produces a delta table classified as CODE MATCHES SPEC / CODE EXCEEDS SPEC /
  CODE MISSING FROM SPEC / SPEC CLAIMS NOT IMPLEMENTED / SPEC-CODE CONFLICT, ranked
  by production, trust-and-safety, and operational risk.
disable-model-invocation: true
context: fork
argument-hint: "[subsystem] against [spec-path-or-description]"
effort: max
allowed-tools: Read Grep Glob Bash(grep *) Bash(rg *) Bash(find *) Bash(git *)
---

# Audit — Spec-to-Code Delta (Chen MODE 3)

Compare implementation to a spec and enumerate every delta. This skill encodes Chen's MODE 3 playbook. The full discipline — same-brain problem, authority resolution, CM-1 (code before specs) and CM-4 (never trust summaries), and report format — lives in [prompts/superprompts/chen-audit-protocol.md](../../prompts/superprompts/chen-audit-protocol.md) and is treated as binding context.

## When to Invoke

- "Does the implementation match the architecture doc?"
- "Are the binding decisions in `<doc>` actually reflected in the code?"
- "The handoff notes claim `<behavior>`. Is the code doing that?"
- "After rapid iteration the spec and the code have diverged — tell me where."
- "A prior Claude session said `<claim>`. Verify against the actual implementation."

If no spec exists and the task is a broad audit, use `audit-deep-subsystem`. If a defect is already suspected, use `audit-finding-expansion`. If the goal is a launch-gate review, use `audit-pre-launch-failure`.

## Required Sequence

1. **Read code first with no spec in context.** Load the implementation files first and understand what they actually do. If you load the spec first, the spec will prime your reading of the code and you will see what the spec told you to see, not what the code does. This is CM-1 — Code Before Specs. If spec was already loaded before this skill was invoked, state that the session was spec-primed and reduce confidence accordingly.

2. **State actual behavior in plain English.** Describe what the code does end-to-end: inputs accepted, transformations applied, outputs produced, state transitions triggered, failure modes, edge behavior. This is the ground truth the spec gets compared against. If this paragraph is vague, the audit will be wrong.

3. **Load the comparison document.** Read the spec, architecture doc, handoff notes, binding decisions, task list, or prior Claude output. Treat it as a claim, not as truth. Per the authority resolution rule, live code outranks documents — if they disagree, the document is wrong on that point unless it names a binding decision that overrides.

4. **Produce a delta table.** Classify every difference into one of:

   | Classification | Meaning |
   |---|---|
   | **CODE MATCHES SPEC** | Implementation and spec agree; noted for completeness |
   | **CODE EXCEEDS SPEC** | Code does more than the spec specifies (may be intentional enhancement or silent scope creep) |
   | **CODE MISSING FROM SPEC** | Code implements behavior the spec does not document (spec is stale or incomplete) |
   | **SPEC CLAIMS NOT IMPLEMENTED** | Spec promises a behavior the code does not provide (gap — prioritize for fix) |
   | **SPEC-CODE CONFLICT** | Spec and code disagree on behavior (either one is wrong — resolve via authority hierarchy) |

   Each row cites file:line on the code side and section/line on the spec side.

5. **Rank deltas by risk.** Use the combined axis of production impact, trust-and-safety impact, and operational impact. A low-probability catastrophic delta outranks a high-probability cosmetic delta. Rank explicitly — do not present a flat list.

## Output Contract

- **Actual behavior** section (plain English, authored before reading the spec).
- **Delta table** with classification, spec reference, code reference, severity.
- **Risk ranking** of deltas.
- **Resolution recommendations**: for each delta, which side should change (code to match spec, spec to match code, or true conflict requiring operator decision). Identify any BINDING DECISION DRIFT / ARCHITECTURE DRIFT / CODE DRIFT / DOCUMENT CONFLICT explicitly.
- **Missing evidence** where the comparison could not be completed.
- **Verdict**: on the spec-to-code relationship — aligned / drift-only / material conflict / spec-stale.

## Rules

1. Code read first, spec second. Non-negotiable. If the ordering is reversed, declare the session spec-primed and reduce confidence.
2. Never silently reconcile conflicts. Label each delta explicitly with classification.
3. Live code outranks a spec. A spec outranks a summary. Apply the authority resolution hierarchy from the superprompt.
4. Do not treat prior Claude outputs or handoffs as truth. Treat them as claims to verify against live code.
5. The delta table must cite file:line for code and section/line for the spec. "The code doesn't do X" with no citation is not a finding.
