<!--
Extracted from: prompts/superprompts/chen-audit-protocol.md § AUDIT MODES — MODE 2 — FINDING EXPANSION / DEBUG DRILL-DOWN
Original purpose: Expansion of a known issue or suspicion — upstream/downstream trace, parallel-instance search, instance-vs-pattern classification, blast-radius, proof-to-close.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: audit-finding-expansion
description: >
  Chen's MODE 2 playbook — debug drill-down for a known defect or suspicion. Use when
  a specific issue is already suspected (reported bug, incident, prior finding) and
  the goal is to determine full scope: instance vs. pattern, blast radius, exact proof
  needed to close. Traces upstream inputs + downstream consequences, searches for
  parallel instances, produces a proof-to-close statement.
disable-model-invocation: true
context: fork
argument-hint: "[suspected defect or finding to drill down on]"
effort: max
allowed-tools: Read Grep Glob Bash(grep *) Bash(rg *) Bash(find *) Bash(git *)
---

# Audit — Finding Expansion / Debug Drill-Down (Chen MODE 2)

Expand a known defect or suspicion to its full scope. This skill encodes Chen's MODE 2 playbook. The full discipline — same-brain problem, authority resolution, CM-1 through CM-10 countermeasures, deep wire trace, full-file pattern census, and report format — lives in [prompts/superprompts/chen-audit-protocol.md](../../prompts/superprompts/chen-audit-protocol.md) and is treated as binding context.

## When to Invoke

- "We saw `<symptom>` in production. Find everywhere else this pattern could bite."
- "A prior audit flagged `<finding>`. Is it an isolated instance or a pattern-level problem?"
- "Something's off with `<function|flow>`. Trace upstream and downstream, find all parallel cases."
- "We have a suspicion that `<claim>`. Determine blast radius and the exact proof needed to close it."

If the audit target is a whole subsystem with no specific suspected defect, use `audit-deep-subsystem` instead. For spec-to-code comparison, use `audit-spec-to-code-delta`. For launch-gate audits, use `audit-pre-launch-failure`.

## Required Sequence

1. **State the suspected defect precisely.** What is claimed to be wrong, where, under what conditions? Vague suspicions become vague findings. Pin it to a file/function/input/state before searching.

2. **Trace all upstream inputs.** Who calls this code? What feeds the inputs? What transforms happen before it? Walk every upstream hop until you reach the entry point that the defect depends on.

3. **Trace all downstream consequences.** What does this code write? Who reads those writes? What state transitions does it trigger? Walk every downstream hop to a user-visible consequence or a persistence boundary.

4. **Search for parallel instances and sibling patterns.** If the defect is `<wrong helper on line 51>`, grep the entire file for every use of that helper. Then search adjacent files for the same pattern family. Then search the whole repo for the sibling pattern. Expand until scope is known — do not stop at a single hit.

5. **Identify whether the issue is instance-level or pattern-level.** An instance-level defect affects one call site; a pattern-level defect is a systematic misuse that replicates across the code. Mis-classifying a pattern-level bug as instance-level is how incidents recur.

6. **State exact blast radius.** Which user flows, revenue paths, trust paths, or data shapes are affected? Under what inputs does the defect fire? What fraction of traffic hits it? If the impact is conditional on a flag, state the flag's current value.

7. **State exact proof needed to close.** What SQL query, log trace, command output, execution record, or live test would make the finding CONFIRMED or DISPROVEN? If the answer requires live verification, provide the copy-paste-ready live-verification bridge: exact query / command, expected passing result, expected failing result, what verdict changes if the result is different.

## Output Contract

Structured finding report. At minimum:

- **Suspected defect** (verbatim restatement, plus precise pin).
- **Upstream trace** with file:line citations at each hop.
- **Downstream trace** with file:line citations at each hop.
- **Parallel instances found** (list with file:line + disposition: CONFIRMED BUG / ACCEPTABLE-INTENTIONAL / NEEDS LIVE VERIFICATION).
- **Instance vs. pattern classification** with explicit rationale.
- **Blast radius** (flows / revenue paths / data shapes / user-facing surfaces affected).
- **Certainty label** (CONFIRMED / HYPOTHESIS / UNVERIFIED / DISPROVEN) per the superprompt § THE SAME-BRAIN PROBLEM.
- **Proof-to-close** with the live-verification bridge if needed.
- **Recommended fix** (surgical — no rewrites when precise fixes are available).

## Rules

1. Audit-only. Chen produces a findings report; the operator decides what to implement.
2. Never close a pattern-level finding from a single hit. Full-file pattern census required.
3. Never upgrade HYPOTHESIS to a finding. Keep them labeled separately.
4. Carry no prior Claude answer forward as proof. The same-brain problem applies — ground truth is the live code, live logs, live command output.
5. "Wired correctly" is not enough. Distinguish WIRING CONFIRMED from EXECUTION NOT YET PROVEN. Never collapse them into one answer.
6. For unresolved P0 or P1 boundaries, the live-verification bridge is mandatory. Do not omit it silently. Do not replace it with general advice.
