<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/zero/SKILL.md
Original purpose: Enforces Zero False Positive / Zero False Negative standard.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: zero
description: Use PROACTIVELY when user says "no false positives", "don't miss any", "find all of them", or when missed findings are as costly as false alarms (pre-launch audits, security reviews). Enforces Zero False Positive AND Zero False Negative — every finding proven real, every possible finding actively hunted, full-file pattern census on every defect. Lighter than /100 (which also requires deep wire trace to execution proof) but stricter than /soft. Stays active for rest of session.
user-invocable: true
disable-model-invocation: true
---

# ZERO FP / ZERO FN MODE — Active for This Session

From this point forward, every finding and every fix must meet both standards simultaneously.

## Zero False Positives

No finding ships without proof:
- Every finding must cite exact file:line with actual code
- Every finding must be grep-verified against live source
- If you cannot prove it exists, it is not a finding
- "I believe" and "likely" are not findings — they are hypotheses, labeled as such
- Pattern-level findings require full-file census before closing (grep ALL instances, not just the first)

## Zero False Negatives

No clean verdict ships without exhaustive search:
- When you find a broken pattern, search the ENTIRE file and ALL related files for sibling instances
- A finding is not complete until every instance in the file is cataloged
- One correct instance does NOT mean all sibling instances are correct
- Absence of evidence is not evidence of absence — state what you searched and what you didn't
- If a finding references a function, grep for ALL callers and ALL callees
- If a finding references a status value, search for ALL code paths that read or write that status

## The Census Protocol

When any finding identifies a broken pattern:

1. Find the first broken instance
2. `grep -n '{pattern}' {file}` — get ALL instances in that file
3. `grep -rn '{pattern}' --include="*.ts" src/` — get ALL instances across the codebase
4. List every match by line number
5. Disposition each: **CONFIRMED BUG** / **ACCEPTABLE** / **NEEDS VERIFICATION**
6. Only then close the finding

## Required on Every Finding

```
FINDING: {description}
FILE: {path}:{line}
EVIDENCE: {exact code}
PATTERN CENSUS: {N} instances found in {file}, {N} in codebase
  Line {X}: {disposition}
  Line {Y}: {disposition}
  ...
WIRE TRACE: {entry → caller → callee → persistence → consumer → user-visible}
CERTAINTY: CONFIRMED / HYPOTHESIS (state missing proof)
```

No shortcuts. No "same as above." No closing from a single instance.
