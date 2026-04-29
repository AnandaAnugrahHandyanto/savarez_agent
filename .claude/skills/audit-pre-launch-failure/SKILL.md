<!--
Extracted from: prompts/superprompts/chen-audit-protocol.md § AUDIT MODES — MODE 4 — PRE-LAUNCH FAILURE AUDIT
Original purpose: Pre-launch or pre-demo ship gate — revenue-path mapping, trust/safety-path mapping, state-transition review, duplicate/retry/timeout/partial-success analysis, silent-failure risk, user-facing misrepresentation risk, top-5 launch killers ranked.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: audit-pre-launch-failure
description: >
  Chen's MODE 4 playbook — pre-launch / pre-demo failure audit. Use before launch,
  demo, or exposure to real users. Maps top revenue / core-service paths, top trust-
  safety-compliance paths, critical state transitions, duplicate/retry/timeout/race/
  partial-success risk, silent-failure risk, user-facing misrepresentation risk.
  Produces a top-5-launch-killers ranking with minimum fix per killer. This is the
  ship gate.
disable-model-invocation: true
context: fork
argument-hint: "[system or subsystem pending launch]"
effort: max
allowed-tools: Read Grep Glob Bash(grep *) Bash(rg *) Bash(find *) Bash(git *)
---

# Audit — Pre-Launch Failure (Chen MODE 4)

Ship-gate audit before launch, demo, or exposure to real users. This skill encodes Chen's MODE 4 playbook. The full discipline — same-brain problem, authority resolution, CM-1 through CM-10 countermeasures, review agents (especially AGENT 7 Security, AGENT 8 Representation, AGENT 10 Regression/Fix Collision), false-clean prevention, and report format — lives in [prompts/superprompts/chen-audit-protocol.md](../../prompts/superprompts/chen-audit-protocol.md) and is treated as binding context.

## When to Invoke

- "We're about to launch `<system>`. Run the ship-gate audit."
- "Demo is Friday. What would actually break in front of a real user?"
- "We're flipping this feature to `<customer>` tomorrow. Confirm it's safe."
- "Final pre-prod pass on `<subsystem>` — map the failure surface in order of what would kill the launch."

If you are early in development and doing broad audit work, use `audit-deep-subsystem`. For known-defect drill-down, use `audit-finding-expansion`. For spec comparison, use `audit-spec-to-code-delta`. MODE 4 is the last checkpoint before exposure; use it with the full weight of a go/no-go decision.

## Required Sequence

1. **Map the top revenue / core-service paths.** Enumerate the top 3 paths that generate revenue or fulfill the core service promise. Examples: account creation → payment capture → service initiation; workflow execution → output generation → delivery; approval flow → final release. Name each path with its entry point, critical hops, and success criterion. **Do not begin the failure analysis until these paths are named explicitly.**

2. **Map the top trust / safety / compliance paths.** Enumerate the top 3 paths where a failure causes user harm, legal or regulatory exposure, safety-critical misrepresentation, or professional-liability risk. Examples: user-facing status labels that misrepresent actual state; delivery of output containing unverified or fabricated claims; privilege-escalation paths that bypass intended access control. **Do not begin the failure analysis until these paths are named explicitly.**

3. **Map critical state transitions.** For each revenue path and each trust path, identify the state transitions required and the conditions under which each transition can be skipped, bypassed, or silently failed. A critical path with an ungated transition is a P0 even if no defect has fired yet.

4. **Identify duplicate / retry / timeout / race / partial-success risk.** For each critical path, ask:
   - What happens if this step executes twice?
   - What happens if it times out?
   - What happens if it partially succeeds and then the process stops?
   - What state remains behind?
   - What happens on concurrent attempts by the same or different users?

   Any "we haven't tested that" is a P0 or P1 finding depending on blast radius.

5. **Identify silent-failure risk.** Ask explicitly: where can this system fail without surfacing an error to the user, the admin, or the operator? Silent failures on revenue or trust-path code are P0. Do not accept "the logs will catch it" unless the logs are verifiably read by a human or an alerting system that is live.

6. **Identify user-facing misrepresentation risk.** Ask explicitly: where can the system display status, confidence, or verification language that overstates what actually happened? Labels like "verified", "complete", "accurate", "confirmed" on a screen must correspond to a behavior that actually verified / completed / was accurate / was confirmed — not a proxy. Representation risk is AGENT 8 territory in the superprompt and is a top launch-kill pattern.

7. **State the top 5 launch killers in rank order.** Format per row:
   - **Rank** (1–5)
   - **Path** (revenue or trust)
   - **Failure mode** (what breaks, under what input)
   - **Why it is ranked where it is** (likelihood × consequence reasoning)
   - **Minimum fix required to unblock launch** (the smallest change that makes this killer non-blocking)

   Rank by the combination of likelihood and consequence. A low-probability catastrophic failure outranks a high-probability minor nuisance. Do not produce a generic risk list. This is the go/no-go input the operator will use.

## Output Contract

- **Revenue paths named** (top 3, explicit).
- **Trust / safety / compliance paths named** (top 3, explicit).
- **Critical state transitions** per path with skip/bypass/silent-failure conditions.
- **Duplicate/retry/timeout/race/partial-success table** per critical hop.
- **Silent-failure surface map** — every place a failure can occur without alerting.
- **User-facing misrepresentation audit** — every label that makes a verification claim with the evidence behind each.
- **Top 5 launch killers** ranked, each with minimum fix to unblock.
- **Launch verdict**: GO / GO WITH FIXES (list) / NO-GO (with exact blockers).

## Rules

1. Audit-only. This skill produces a go/no-go input. The operator decides launch.
2. Paths must be named before failure analysis. Naming the path is part of the output, not a skip-to-findings shortcut.
3. No generic risk lists. The top 5 launch killers are ranked by likelihood × consequence with explicit reasoning per rank.
4. Silent failure on a revenue or trust path is P0. No exceptions.
5. User-facing verification language is only acceptable when the system actually verified something. "Complete" without a completion check is P0 misrepresentation.
6. Live-verification bridges are mandatory for every unresolved P0 and P1 finding — exact SQL/command/log query, expected passing result, expected failing result, what verdict changes if the result is different.
