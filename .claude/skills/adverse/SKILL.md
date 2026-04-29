<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/adverse/SKILL.md
Original purpose: Adversarial completeness check (security / business-logic / integration coverage).
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: adverse
description: Use PROACTIVELY when user asks "what am I missing", "edge cases", "what could go wrong", or after any plan/draft/audit is complete. Runs adversarial-completeness pass scoring security surface, business logic, and integration wiring coverage with explicit "what could still hide a false negative" analysis. Do not use for routine code review (that is the code-reviewer sub-agent) or for active bug investigation (use /diagnose).
disable-model-invocation: true
context: fork
argument-hint: "[subsystem or area to check]"
effort: max
allowed-tools: Bash(grep *) Bash(rg *) Bash(cat *) Bash(head *) Bash(tail *) Bash(wc *) Bash(find *) Read Grep Glob
---

# ADVERSARIAL COMPLETENESS CHECK

Perform an adversarial completeness check on this subsystem.

**Target**: $ARGUMENTS

Do not ask "what did I find?" Ask "what would I still be missing if I were wrong?"

## Dimension 1: Security Surface Coverage

Score: [__]%

For this subsystem, enumerate:
- **Actually verified**: What security properties did you confirm with code evidence?
  - Auth checks (who can call this? grep for auth middleware, RLS policies, ownership checks)
  - Input validation (what schemas validate input? are there bypass paths?)
  - Secrets handling (are API keys, tokens, PII properly scoped? grep for env vars, hardcoded strings)
  - Output sanitization (can user input reach HTML, SQL, or shell without escaping?)
  - Tenant isolation (can one user's data leak to another? check RLS, WHERE clauses, query scoping)

- **Only inferred**: What did you assume without direct proof?
  - "RLS is probably enabled" — did you verify the policy exists AND is correct?
  - "Auth middleware covers this route" — did you trace the middleware chain?

- **Could still hide a false negative**: What wasn't checked?
  - Admin routes with different auth paths
  - Background jobs that bypass user-scoped auth
  - Webhook endpoints with shared secrets
  - Error responses that leak internal details

## Dimension 2: Business Logic Coverage

Score: [__]%

For this subsystem, enumerate:
- **Actually deep-read and behaviorally traced**:
  - Every code path that produces a user-visible output or state change
  - Every conditional branch (if/else, switch, ternary) — what triggers each?
  - Every loop — what are the bounds? Can it run zero times? Infinite times?
  - Every error/catch — what state is left behind on failure?

- **Only partially verified**:
  - Functions you read but didn't trace callers/callees
  - Branches you noted but didn't test with edge-case inputs
  - State machines where you verified transitions but not the full state space

- **Assumptions that remain**:
  - "This function is only called from one place" — did you grep all callers?
  - "This value is never null here" — what guarantees that?
  - "This enum covers all cases" — what happens with an unexpected value?

## Dimension 3: Integration Wiring Coverage

Score: [__]%

**This is NOT just import tracing.** A connection existing is not the same as the connection working.

For each boundary in the subsystem:
- **Traced to both ends**: You read the producer AND the consumer and confirmed:
  - Data shape matches (types, nullability, field names)
  - Error handling on both sides is compatible
  - Failure in producer doesn't leave consumer in corrupt state
  - Retry/duplicate behavior is handled

- **Only presence-checked**: You confirmed the import/call exists but did NOT:
  - Verify the data shape at both ends
  - Test with null/malformed/partial input
  - Trace what happens on timeout or partial success

- **Require live execution evidence**: Things you can't prove from code alone:
  - DB writes actually land in the right table with the right values
  - Events actually fire and are consumed
  - External API calls return the expected shape in production
  - Race conditions that only manifest under load

## Final Assessment

```
╔══════════════════════════════════════════════════╗
  ADVERSARIAL COMPLETENESS CHECK
  Target: {subsystem}
╚══════════════════════════════════════════════════╝

Security Surface:    {N}% — {what's missing}
Business Logic:      {N}% — {what's missing}
Integration Wiring:  {N}% — {what's missing}

CAN THIS SUBSYSTEM BE MARKED CLEAN?
{YES / NO / PARTIALLY}

{If NO: what exact evidence is still missing?}
{If PARTIALLY: what's clean and what isn't?}

TOP 3 THINGS MOST LIKELY TO HIDE A BUG:
1. {specific area and why}
2. {specific area and why}
3. {specific area and why}
```

Be honest. Low percentages are valuable information. High percentages with hidden assumptions are dangerous.
