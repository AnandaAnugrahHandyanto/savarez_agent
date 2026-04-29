<!--
Extracted from: synthesized from Motion-Granted-Production .claude/commands/finalize.md and observed commit-message conventions in the source repo
Original purpose: commit-message format + discipline for AI-assisted codebases.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

# Commit Conventions

Commits in tanner-stack-adopting projects follow a **Conventional Commits**–style format, adapted for AI-assisted workflows where reviewers need more "why" and less "what" in the subject line.

---

## Format

```
<type>(<scope>): <short description>

<body — optional, focused on the WHY and on anything the reviewer must know>

<footer — optional: Co-Authored-By, decision IDs, breaking-change notes>
```

**Subject line length**: ≤ 72 characters. The subject is the only thing that appears in `git log --oneline`, PR lists, and many UIs.

---

## Types

| Type | Use when… |
|---|---|
| `feat` | A new capability is added (new persona, skill, API endpoint, workflow). |
| `fix` | A bug is resolved. Always reference the finding ID or decision code in the body. |
| `refactor` | Internal code restructuring with no behavior change. Must be provable via tests passing unchanged. |
| `docs` | Documentation-only change. No code changes. |
| `test` | Adds or modifies tests, no production code change. |
| `chore` | Infrastructure, dependencies, tooling, config. |
| `perf` | Performance improvement with no behavior change. Include before/after numbers in body. |
| `style` | Formatting, whitespace, comments. No behavior change. |

If the change mixes types (e.g., feat + fix), split it into two commits. If the change is genuinely one logical unit that mixes types, use the more prominent type as the prefix and call out the mix in the body.

---

## Scope

Scope is the subsystem, module, or feature area. Examples from a typical project:

```
feat(auth): ...
fix(payments): ...
refactor(api): ...
docs(architecture): ...
```

Scope is optional if the change is truly global. Prefer specific scope when possible — it makes `git log --grep` far more useful.

---

## The "Why," Not the "What"

The diff shows what. The commit message should explain why.

**Bad**: `fix(compat): change field mapping for severity`
(reader still has to read the diff to understand motivation)

**Good**: `fix(compat): scale severity from 0-1 float to 0-100 int to match downstream reader contract`
(reader knows the motivation without opening the diff; can decide whether this is the right fix)

**Bad**: `feat(skill): add new skill`

**Good**: `feat(skills): add lossy skill to hunt silent data loss across pipeline boundaries`

---

## Body Requirements

The body is **required** for any `fix` commit. It must state:

1. **What was broken** in plain English (the symptom, not the code)
2. **Why it was broken** (the root cause)
3. **How this fix resolves it** (one sentence, mechanism of the fix)
4. **Evidence** — file:line or grep output proving the fix addresses the root cause
5. **Finding ID or decision code** if applicable

For `feat`, `refactor`, and `perf` commits, the body should state **why now** — why this change belongs in this PR rather than later.

For `docs`, `test`, `chore`, `style`: body is optional.

---

## Footers

### Co-Authored-By

If Claude Code assisted the change, add:

```
Co-Authored-By: Claude <noreply@anthropic.com>
```

Adjust the name/email per your project's attribution convention. Some teams use `Co-Authored-By: Claude Code <...>`, others credit a specific model version. Pick one convention and stick to it.

### Decision codes

If the change implements a binding-decision code (e.g., `D-HANDOFF-2`, `FIX-42`, `TASK-101`), reference it explicitly:

```
Implements: D-HANDOFF-2
```

or in the subject when short:

```
fix(pipeline): D-HANDOFF-2 — prevent silent JSON truncation at stage boundary
```

### Breaking changes

Any commit that changes a public contract (API, schema, event payload, function signature in a shared module) must include:

```
BREAKING CHANGE: <what breaks and the migration path>
```

This flags the commit for downstream consumers and tooling that respect the Conventional Commits spec.

---

## Examples

```
feat(skills): add diagnose — structured 4-phase bug investigation

Introduces the diagnose skill that runs LOCATE → CONTEXT → ROOT CAUSE →
FIX PROPOSAL in order, enforcing dead-code-trap checks and explicit
certainty labels at each phase. Replaces ad-hoc debugging with a
verification-first protocol.

Co-Authored-By: Claude <noreply@anthropic.com>
```

```
fix(compat): scale severity from 0-1 float to 0-100 int (LEARNINGS §5)

Downstream reader in src/api/verdict-renderer.ts expects 0-100 integers,
but compat.ts:84 was passing 0.0-1.0 floats. Reader cast them to int,
collapsing all non-zero values to 0 and producing a false "CLEAN"
verdict on rejected items.

Evidence: compat.ts:84 emits `result.severity` raw; verdict-renderer.ts:17
calls `parseInt(severity, 10)`.

Fix: scale at compat.ts:84 before emit (`Math.round(result.severity * 100)`).

Co-Authored-By: Claude <noreply@anthropic.com>
Implements: D-COMPAT-SEV-1
```

```
refactor(skills): add "Also invokable as" alias note on session-start

No behavior change. Canonical session-start skill is authoritative;
operators may still invoke it via the legacy alias when needed. Full
protocol lives in skills/session-start/SKILL.md.

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Rules (binding)

1. **Every fix commit has a body.** No exceptions.
2. **Subject is imperative mood**: "fix X" not "fixed X" or "fixes X".
3. **No WIP commits** in PRs merged to protected branches. Squash or rebase WIP before merge.
4. **One logical change per commit** — unless the change is a grouped set (same contract, same file, interdependent).
5. **Reference decision codes** when implementing a tracked decision. Makes `git log --grep='D-HANDOFF'` trivially useful.
6. **Never `git add .`** in a commit-authoring session. Explicit file staging only.
7. **Never amend a commit that was already pushed** to a shared branch. Create a new commit instead.

---

## Tools

- `pr` skill (preloaded in code-reviewer sub-agent) — runs preflight, delegates review, stages specific files, and uses HEREDOC commit messages. It enforces most of the above automatically.
- `session-end` skill (auto-invokes from "wrap up" / "end session" / "write handoff" signals) — generates handoff docs that reference the commits made this session.
- `git log --oneline --grep='<type>'` — filter by commit type to see change categories.
- `git log --oneline --grep='D-<code>'` — find all commits touching a decision code.
