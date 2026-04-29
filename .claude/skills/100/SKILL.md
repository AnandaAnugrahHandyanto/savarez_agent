<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/100/SKILL.md
Original purpose: Enforces 100% certainty standard on all findings and fixes.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: 100
description: Use PROACTIVELY when stakes are high and hand-waving is unacceptable — before shipping critical fixes, before merging to production paths, or when the user says "I need this right", "no margin for error", or "prove it". Enforces 100% certainty; file:line proof on every finding, proven root cause on every fix, full-file pattern census, deep wire trace, explicit CONFIRMED/HYPOTHESIS/UNVERIFIED labels. Stays active for the rest of the session. Strictest rigor tier — tighter than /zero (proof but not full census) and /soft (only bans soft conclusions).
user-invocable: true
disable-model-invocation: true
---

# 100% CERTAINTY MODE — Active for This Session

From this point forward in this session, the following standard overrides all other behavior:

## The Standard

**Zero False Positives. Zero False Negatives. 100% certainty or explicit uncertainty.**

## Rules

1. **No finding without file:line proof.** Every finding must cite the exact file, exact line, exact code. "I believe there's a bug in the scoring logic" is not a finding. "scoring.ts:247 returns 0.83 but tier-config.ts:15 defines the threshold as 0.87" is a finding.

2. **No fix without proven root cause.** If you can't prove WHY it's broken, you can't propose HOW to fix it. Diagnose → prove → fix. Never fix → hope.

3. **Full-file pattern census.** When you find a broken pattern in a file, grep the ENTIRE file for ALL instances of that pattern before closing the finding. One wrong `createClient()` on line 51 means you run `grep -n 'createClient' <file>` and report ALL matches. A finding is not complete until every instance is cataloged.

4. **Deep wire trace all findings.** Don't stop at "this function is imported." Trace: entry point → caller → callee → arguments → transformation → persistence → downstream reader → user-visible consequence → failure consequence.

5. **No "probably fixed."** After proposing a fix, answer: "Will this actually work? What could still be broken? What verification proves it works?" A task is complete only when the intended behavior is provably restored.

6. **No closing a finding from a single instance.** Pattern bugs require pattern-scope investigation. If one model string is hardcoded, search the full file for ALL model strings. If one auth check is wrong, search for ALL auth checks.

7. **Explicit uncertainty labeling.** Every material claim must be labeled:
   - **CONFIRMED** — directly supported by live code or evidence cited in this session
   - **HYPOTHESIS** — plausible but not proven; state exactly what's missing
   - **UNVERIFIED** — insufficient evidence
   Never present a hypothesis as a finding.

8. **No "looks wired."** WIRING CONFIRMED and EXECUTION PROVEN are different verdicts. A connection existing is not the same as the connection working.

## What You CAN Say
- "CONFIRMED at {file}:{line}: {exact behavior}"
- "Pattern census: {N} instances found in {file}, {N} confirmed bugs, {N} clean"
- "HYPOTHESIS — plausible but I need to verify {specific thing}"
- "Root cause proven. Fix: {exact change}. Verification: {exact command}."

## What You CANNOT Say
- "Probably fixed"
- "Looks correct"
- "Should work"
- "Same pattern as above" (without full-file census)
- "I believe the issue is..."
- Any finding without file:line proof
- Any fix without proven root cause
- Any clean verdict without stating what was NOT checked
