<!--
Extracted from: synthesized from Motion-Granted-Production AGENTS.md + CLAUDE.md + LEARNINGS.md + .claude/agents/ + .claude/skills/chen, /diagnose, /verify, /pr
Original purpose: the default three-phase workflow for any non-trivial change in an AI-assisted codebase.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

# Audit → Fix → Build Loop

The default workflow for any non-trivial change. Three phases, staged approvals between them. Each phase has a distinct persona, distinct evidence discipline, and distinct commit semantics.

Use this loop when the change touches:
- A boundary between subsystems
- A state transition, contract, or schema
- An inviolable rule surface
- More than one file
- Any code path that produces user-visible output or persists state

Skip it only for trivial single-line cosmetic changes (typo fixes, import reordering).

---

## Phase 1 — AUDIT (find truth, propose nothing)

**Goal:** determine what is actually wrong. Do not fix anything in this phase.

**Invocation:**
- chen sub-agent (auto-delegates from "audit this subsystem" / "is this safe to ship") for adversarial deep audit
- `diagnose` skill (auto-invokes from error / stack-trace / "why is this failing" signals) for a focused 4-phase bug investigation
- code-reviewer sub-agent (auto-delegates from "review this diff" / PR-review signals) for post-diff pass (defensive, pre-commit)

**Deliverable:** a findings report with:
- Severity for each finding (P0 / P1 / P2 / P3)
- Certainty label (CONFIRMED / HYPOTHESIS / UNVERIFIED / DISPROVEN)
- File:line evidence for every CONFIRMED finding
- Pattern vs instance classification — full-file pattern census for any pattern-level finding
- Blast radius (GitNexus impact analysis if available)
- Upstream cause and downstream consequence
- Proposed fix sketch (but do NOT implement it)
- Missing-evidence list — what live verification is still required to close each P0/P1

**Rules:**
- No fix proposals without root cause proven.
- No finding without file:line evidence or explicit uncertainty label.
- No clean bill of health without stating what was NOT checked and residual risk.
- If the same-brain problem applies (see [prompts/superprompts/chen-audit-protocol.md § Same-Brain Problem](../prompts/superprompts/chen-audit-protocol.md)), call it out.

**Halt gate:** the operator reviews the report and approves specific findings for Phase 2. Never self-promote from AUDIT to FIX.

---

## Phase 2 — FIX (one finding at a time)

**Goal:** resolve approved findings with surgical changes. One finding per commit.

**Invocation:**
- Work from the Phase 1 report.
- For each approved finding: read the current code, confirm root cause still holds, implement the smallest fix that closes it.
- Invoke the grep-verifier sub-agent (or the `grep-verify` skill preloaded in it) on each claim the fix rests on.
- Run the project's typecheck / lint after every edit (enforced by PostToolUse hook if configured in `.claude/settings.json`).
- If the finding is pattern-level (same bug in multiple places), do a full-file / full-codebase pattern census before claiming complete.

**Discipline:**
- **Surgical changes** (Karpathy pitfall 8.3): touch only what you must. Match surrounding style. Do not "improve" unrelated areas.
- **No speculative fixes**: if you can't prove the root cause, you can't propose the fix. Diagnose → prove → fix.
- **Restrictive fallbacks** (LEARNINGS.md §5): unknown or missing states produce the safest outcome, never the happy-path default.
- **Live path only**: verify you are editing the live file, not the dead-code twin (see the project's DO NOT Edit list in its project CLAUDE.md).
- **Write-side before read-side** (LEARNINGS.md §4): when both sides need fixing, fix the writer first and verify data is produced, then fix the reader.

**Commit per finding** with the project's commit convention (see [commit-conventions.md](commit-conventions.md)). Reference the finding ID or decision code in the commit message.

**Halt gate:** after each fix, optionally re-invoke the grep-verifier sub-agent and the code-reviewer sub-agent. Before moving to Phase 3, verify every approved finding has either been implemented or explicitly deferred.

---

## Phase 3 — BUILD (integrate, verify, ship)

**Goal:** integrate the fixes, prove the behavior is restored, open a PR.

**Invocation:**
- `/verify <scope>` command — 3-leg verification (typecheck, grep fact-check, test suite)
- `adverse` skill (auto-invokes from "what am I missing" / "edge cases" signals) — adversarial completeness check across security / business-logic / integration-wiring dimensions
- Optionally the `st` skill (auto-invokes from "stress test" / "production-ready" signals) for a full stress test if the change touches a production-readiness surface
- `pr` skill (preloaded in code-reviewer sub-agent; auto-invokes from "open a PR" / "submit this") — preflight + PR submission. Delegates to the code-reviewer sub-agent for a final safety pass

**Deliverable:**
- All approved findings either implemented or deferred (deferred ones recorded in BACKLOG.md)
- All tests pass (existing + any new ones from the `/project-tdd` command if the change used TDD)
- Adversarial completeness scores are honest — low percentages are valuable information
- PR opened via `gh pr create` with Summary + Test Plan
- Post-merge: log learnings in LEARNINGS.md if any pattern-level insight emerged

**Rules:**
- **Execution proof, not wiring proof**: WIRING CONFIRMED ≠ EXECUTION PROVEN. State both separately.
- **No "probably fixed"**: answer "will this actually work? what could still be broken? what verification proves it works?" explicitly.
- **Session-end discipline**: invoke the `session-end` skill (auto-invokes from "wrap up" / "end session" / "write handoff" signals) to produce a structured handoff for the next session.

**Halt gate:** the operator owns PR merge. Never merge to `main` / `master` / `LIVE` / `Production` branches from a Claude Code session.

---

## Loop Semantics

- A bug discovered in Phase 2 or Phase 3 that is out of scope for the current fix goes to **BACKLOG.md**, not inline expansion (see LEARNINGS.md §5 on scope drift).
- A bug discovered in Phase 2 or 3 that invalidates a Phase 1 finding requires returning to Phase 1 for re-audit of the affected scope. Do not silently amend findings.
- Multi-file refactors that share a common contract (same event, same schema, same state transition) form a **grouped change set** — the whole group becomes one Phase 2 commit, not N.
- If you are Claude and you catch yourself batching multiple findings into one fix, STOP. One finding per commit unless grouped.

## Anti-Patterns (LLM-assisted coding failure modes)

These are specific ways the loop breaks when an AI session is the one running it:

1. **"I already know the bug"** — skipping Phase 1 because the error message looks obvious. This is how the 38–54% false-positive rate lives in production. Do the audit.
2. **Pattern-level close-from-one-hit** — finding the bug on line 51, fixing it, moving on without checking lines 89, 147, 203. Run the full-file census.
3. **Writing code before the success criteria exist** — Karpathy pitfall 8.4. If you can't state how you'll verify the fix works, you're not ready to write the fix.
4. **Dead-code edits** (LEARNINGS.md §1) — correct fixes to files that don't execute in production. Always grep-verify the import chain before editing.
5. **"Should work" / "looks correct"** — banned language under the `100`, `soft`, `zero` rigor-mode skills (auto-invoke from "no margin for error" / "no guessing" / "no false positives" signals). Hard evidence or honest uncertainty. Nothing in between.
