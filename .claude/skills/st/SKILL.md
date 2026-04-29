<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/st/SKILL.md
Original purpose: Full stress-test protocol — 5 steps covering boundary, contracts, 9 viewpoints, conflict hunt, pre-mortem.
Genericized: 2026-04-21
Operator: Porter Tanner
Extraction note: per operator decision, framework-only extraction. Project-specific invariants and tier examples left as template slots.
-->

---
name: st
description: Use PROACTIVELY when user says "stress test this", "is this production-ready", "what happens at scale", or "break it before prod". Runs a 5-step protocol — domain boundary + invariants, upstream/downstream contracts, 9-viewpoint stress (functional, data integrity, concurrency, reliability, performance, security, compliance, observability, human factors), conflict hunt, pre-mortem. Distinct from /adverse (completeness audit) and chen MODE 4 sub-agent (revenue/trust path failure analysis).
disable-model-invocation: true
context: fork
argument-hint: "[subsystem or domain to stress test]"
effort: max
allowed-tools: Bash(grep *) Bash(rg *) Bash(cat *) Bash(head *) Bash(tail *) Bash(wc *) Bash(find *) Bash(npx tsc *) Read Grep Glob
---

# STRESS TEST — Full Production Readiness Audit

Stress test this domain for production readiness.

**Target**: $ARGUMENTS

Execute ALL 5 steps in order. Do not skip steps. Do not summarize steps away.

---

## Step 1: Establish Domain Boundary & Invariants

### Boundary
Define what's INSIDE this domain vs OUTSIDE:
- Files in scope (list every file with line count)
- External dependencies consumed (APIs, DBs, services)
- External consumers of this domain's output
- Clear statement: "This domain starts at {entry} and ends at {output}"

### Invariants
List invariants that must NEVER break. Template slot — populate with your project's invariants. Examples by category:

- **Correctness invariants**: no claim of "verified" from error paths; no silent truncation
- **Data invariants**: no cross-tenant leakage; append-only audit log
- **Flow invariants**: no skipping a required gate; no duplicate fulfillment
- **Representation invariants**: user-facing labels never overstate what the system did

For each invariant: state how it's enforced in code (grep evidence) or state that enforcement is MISSING.

### Assumptions
If you must assume something, label it:
**ASSUMPTION**: {statement} — **WOULD NEED**: {what would confirm or deny it}

---

## Step 2: Map Upstream & Downstream Contracts

Create a contract map. For EACH integration edge:

### Upstream Producers (what feeds INTO this domain)
| Producer | Input Schema | Required Fields | Auth Context | Idempotency Key | Ordering Guarantee | Max Payload | Frequency |
|----------|-------------|-----------------|-------------|-----------------|-------------------|-------------|-----------|
| {name} | {shape} | {fields} | {how authed} | {key or NONE} | {ordered/unordered} | {size} | {rate} |

### Downstream Consumers (what reads FROM this domain)
| Consumer | Output Schema | Side Effects | Ordering Expectation | Retry Behavior | Failure Handling |
|----------|-------------|-------------|---------------------|----------------|-----------------|
| {name} | {shape} | {effects} | {expectations} | {who retries} | {what happens} |

### Versioning / Migration
- What breaks if the upstream schema changes?
- What breaks if the downstream consumer expects an old format?
- Is there a compat layer? Is it lossy? (see /lossy skill)

---

## Step 3: Stress Test from 9 Viewpoints

Run ALL of these. Do not skip any viewpoint.

### (a) Functional Correctness & State Transitions
- Map all state transitions in this domain
- For each transition: what triggers it? Can it be triggered twice? Can it be skipped?
- Dead states: are there states with no exit?
- Happy path vs every error path

### (b) Data Integrity
- Schema drift between code types and actual DB columns
- Nullable fields that code assumes are non-null
- Encoding issues (UTF-8, JSON escaping, HTML entities)
- Large payloads (worst-case size)
- PII segregation (is PII in the right tables with the right access control?)

### (c) Concurrency & Idempotency
- What happens if the same request is submitted twice?
- What happens if a step retries mid-execution?
- Race conditions: two writers to the same row?
- At-least-once delivery: does every write handle duplicates?
- Is the concurrency limit enforced everywhere it needs to be?

### (d) Reliability & Resilience
- Timeout behavior (at every layer)
- What happens on partial outage (one dependency down, others up)?
- Dead-letter handling: what happens to failed events?
- Replay safety: can every step be safely replayed?
- Circuit-breaker state: are all breakers functioning?

### (e) Performance & Scale
- Worst-case payload sizes
- Worst-case iteration counts
- Cost blowups (expensive API calls, model inference per request)
- Spike behavior (many requests submitted simultaneously)

### (f) Security & Privacy
- STRIDE threat model for this domain:
  - **S**poofing: can someone impersonate another user?
  - **T**ampering: can data be modified in transit/at rest?
  - **R**epudiation: can actions be denied without audit trail?
  - **I**nformation disclosure: can data leak to wrong user?
  - **D**enial of service: can this domain be overwhelmed?
  - **E**levation of privilege: can a user access admin functions?
- Secrets handling: are API keys in env vars, not code?
- Prompt injection: if AI touches user input, can it be manipulated?
- Access control: is every table properly scoped?

### (g) Compliance & Auditability
- Are all state changes logged immutably?
- Can you trace any output back to its source and every intermediate step?
- Evidentiary defensibility: if a user challenges a result, can you prove the pipeline's work?
- Retention: what gets deleted and when?

### (h) Observability & Operability
- What gets logged? (structured logger or console.log?)
- What's measurable? (stage durations, success rates, cost per request)
- Alerting: what triggers an alert?
- Runbooks: if this breaks at 2 AM, what does someone do?

### (i) Human Factors
- Misconfiguration: what happens if env vars are wrong?
- Unclear UI: can a user submit ambiguous input that breaks the pipeline?
- Unknown unknowns: what failure modes have we not imagined?
- Bad instructions: what if the user's input is incoherent?

---

## Step 4: Upstream/Downstream Conflict Hunt

For EACH integration edge identified in Step 2, answer explicitly:

| Question | Answer |
|----------|--------|
| Who owns retries? | {producer / consumer / both / NOBODY} |
| Who owns backoff? | {producer / consumer / NOBODY} |
| Who owns deduplication? | {producer / consumer / NOBODY} |
| What happens on partial success? | {description} |
| What happens if schemas diverge? | {description} |
| What happens when external services rate-limit? | {description} |
| What happens when the same request is processed twice? | {description} |
| What is the rollback story if a deploy breaks the contract? | {description} |

If any answer is "NOBODY" — that's a finding. Someone must own it.

---

## Step 5: Pre-Mortem

Write this narrative:

> **It's 6 months after launch.** This domain caused a production incident or a user-facing error.

Answer:
1. **What failed?** (specific failure, not generic)
2. **What was the trigger?** (the event or condition that exposed the bug)
3. **What was the blast radius?** (how many users affected, what data corrupted, what trust lost)
4. **How did it escape detection?** (why didn't monitoring/tests/audits catch it)
5. **What fix would have prevented it?** (specific code/config change, not "better testing")

Write at least 2 pre-mortem scenarios. One should be the most likely failure. The other should be the most catastrophic.

---

## Output Format

```
╔══════════════════════════════════════════════════════════════╗
  STRESS TEST REPORT — {domain}
╚══════════════════════════════════════════════════════════════╝

STEP 1: BOUNDARY & INVARIANTS
  Domain: {entry} → {output}
  Files: {N} | Invariants: {N defined, N enforced, N MISSING}
  Assumptions: {N}

STEP 2: CONTRACTS
  Upstream: {N producers}
  Downstream: {N consumers}
  Lossy boundaries: {N found}

STEP 3: VIEWPOINT STRESS TEST
  (a) Functional:    {finding count} findings
  (b) Data:          {finding count}
  (c) Concurrency:   {finding count}
  (d) Reliability:   {finding count}
  (e) Performance:   {finding count}
  (f) Security:      {finding count}
  (g) Compliance:    {finding count}
  (h) Observability: {finding count}
  (i) Human:         {finding count}

STEP 4: CONFLICT HUNT
  {N} edges checked, {N} ownership gaps found

STEP 5: PRE-MORTEM
  Scenario 1 (most likely): {summary}
  Scenario 2 (most catastrophic): {summary}

TOTAL FINDINGS: {N}
  P0: {N} | P1: {N} | P2: {N} | P3: {N}

VERDICT: {READY / NOT READY / CONDITIONALLY READY}
```
