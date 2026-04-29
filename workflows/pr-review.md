<!--
Extracted from: synthesized from Motion-Granted-Production .github/pull_request_template.md, .claude/.claude/skills/\1/SKILL.md, .claude/agents/code-reviewer.md
Original purpose: end-to-end PR review discipline for AI-assisted changes.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

# PR Review Workflow

PR review in tanner-stack is a layered discipline: the author does a preflight, the code-reviewer agent does a structural sweep, a human (or a second Chen pass) does the merge decision. No layer is optional. Skipping a layer is how false positives and regressions ship.

---

## Layer 1 — Author Preflight (`pr` skill)

Before opening the PR, the author invokes the `pr` skill (preloaded in the code-reviewer sub-agent; also auto-invokes from "open a PR" / "submit this" signals), which:

1. **Branch safety**: confirms the current branch is not `main` / `master` / `LIVE` / `Production`. Blocks immediately if it is.
2. **Code Reviewer delegation**: launches the code-reviewer sub-agent (see [.claude/agents/code-reviewer.md](../.claude/agents/code-reviewer.md)) with the changed-file list. Sub-agent returns CLEAN / WARNINGS / BLOCKED.
3. **Typecheck / lint**: runs the project's typecheck (e.g., `npx tsc --noEmit`, `mypy .`, `cargo check`). Must exit 0.
4. **Test suite**: runs tests relevant to the changed files.
5. **Stage and commit**: explicit file-by-file staging (**never** `git add .`). Commit message per [commit-conventions.md](commit-conventions.md).
6. **Push + PR**: `git push -u origin HEAD`, then `gh pr create` with Summary + Test Plan body (see below).

If any check fails, the `pr` skill stops. It does not suggest `--no-verify` or other bypasses.

---

## Layer 2 — Code Reviewer Agent (structural sweep)

The code-reviewer agent (Sonnet, high effort, max 30 turns) runs through the project's violation list, combining **structural evidence** (GitNexus call-graph queries) with **text evidence** (grep). Typical checks:

- Highest-severity protocol violation (P0 BLOCK): project-specific cardinal rule (e.g., no "success from error path" — see project's inviolable-decisions list).
- Dead-code edits: filename check + structural dead-code check via `gitnexus context`.
- Inviolable-rule violations: pattern-by-pattern grep for each binding rule.
- Config-drift: hardcoded values that should come from the config module.
- Sensitive-field leaks: fields that may exist in DB but must not appear in user-facing output.
- Logging discipline: no `console.log` in production hot-path files.
- Blast-radius analysis: `gitnexus impact` on every modified symbol; HIGH/CRITICAL risk triggers a WARNING with explicit confirmation required.
- Scope-drift check: `gitnexus detect-changes` vs. `git diff --stat` — flag unexpected symbols affected.

Verdict:
- **CLEAN** — no violations found
- **WARNINGS** — non-blocking issues listed
- **BLOCKED** — P0 or inviolable-rule violation. Do not commit.

The agent runs in its own context. It does not see the current conversation. Pass the full file list explicitly.

---

## Layer 3 — Merge Decision (human)

The operator — not the Claude Code session — makes the merge decision. The session's role ends at "PR opened."

Merge checklist (human side):

- [ ] PR body follows the template (Summary + Test Plan)
- [ ] Code Reviewer agent verdict is CLEAN or WARNINGS (with explicit sign-off on WARNINGS)
- [ ] All tests pass in CI (if configured)
- [ ] Production migrations, if any, have landed first (see LEARNINGS.md Meta-Lesson: Schema Before Code)
- [ ] No merges from a Claude Code session to `main` / `master` / `LIVE` / `Production`

For high-risk changes (pipeline boundaries, scoring logic, routing rules, inviolable-rule surfaces), run a second Chen pass as an independent reviewer before merge. Spec-to-code delta audit (MODE 3 of the Chen protocol) is the right tool here.

---

## PR Body Template

```markdown
## Summary
<1–3 bullets on what changed and WHY, not what>

## Test Plan
- [ ] <What you ran manually or against test data to verify>
- [ ] <What automated tests cover this change>
- [ ] <What downstream impact you checked and how>

## Breaking Changes
<None / list>

## Deploy Notes
<Migration order, feature flags, rollback plan if applicable>

## Related
<Finding IDs, decision codes, linked issues>
```

---

## Rules (binding)

1. **No force-push.** Configure `.claude/settings.json` to deny `git push --force`. If an override is ever needed, the operator does it outside a Claude Code session.
2. **No direct commits to protected branches.** Enforced by the `pr` skill's branch-safety check and ideally by repo branch-protection rules.
3. **Explicit file staging.** `git add .` / `git add -A` is banned because it accidentally captures unrelated edits. Stage each file by name.
4. **Commit messages follow the convention** (see [commit-conventions.md](commit-conventions.md)) or the PR is blocked.
5. **Code Reviewer runs on every PR**, even trivial ones. The few-second cost is insurance against the 38–54% false-positive category of mistakes.
6. **WARNINGS do not silently become CLEAN.** If the author chooses to merge despite WARNINGS, they record the rationale in the PR body.

---

## When to Skip This Workflow

Very rarely. The only acceptable skips:

- Pure documentation changes that touch no code paths.
- `.gitignore` / editor-config / CI-only tweaks that cannot affect runtime.

Even then, open a PR — just skip the code-reviewer delegation and typecheck on trivial changes. When in doubt, don't skip. The workflow is cheap.
