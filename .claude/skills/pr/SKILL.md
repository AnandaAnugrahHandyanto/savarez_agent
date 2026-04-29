<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/pr/SKILL.md
Original purpose: PR preflight + submission: delegates safety checks to code-reviewer, runs typecheck, commits, pushes, opens PR.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: pr
description: >
  PR preflight and submission. Delegates safety checks to the code-reviewer agent
  (project-specific violation list), runs the typecheck for the project's language,
  then commits, pushes, and opens a PR via gh. Declines to proceed on any violation.
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(gh *) Bash(npx tsc *) Bash(pnpm *) Bash(npm *) Read
---

# PR — Pull Request Preflight + Submission

Prepare and open a pull request. Run preflight, then ship.

## Pre-loaded State

**Branch:**
!`git branch --show-current`

**Changed files:**
!`git diff --name-only HEAD`

**Status:**
!`git status --short`

---

## Preflight (all must pass)

### 1. Branch Safety

The current branch must NOT be `main`, `master`, or any name containing `LIVE` or `Production`. If it is, BLOCK immediately: tell the user to switch to a feature branch and stop. Production merges belong to a human.

### 2. Code Review Delegation

Delegate to the `code-reviewer` sub-agent (Claude Code native delegation, based on its description trigger, or via the Agent tool). Pass it the list of changed files. The sub-agent applies this project's violation list (see [.claude/agents/code-reviewer.md](../../.claude/agents/code-reviewer.md)).

If the agent returns BLOCKED, stop and relay its findings verbatim.

### 3. Typecheck / Lint

Run the project's typecheck command (e.g., `npx tsc --noEmit`, `mypy .`, `cargo check`). Must exit 0. If it fails, stop and show the first few errors.

Run the project's lint if configured (e.g., `npm run lint`). Warnings are non-blocking unless the project treats them as blocking.

---

## If All Checks Pass

1. Stage specific files by name. **NEVER** `git add .` or `git add -A` — always name files.
2. Draft a commit message focused on the **why**, not the what (1-2 sentences).
3. Commit with HEREDOC format. Add a `Co-Authored-By:` footer if the project uses one.
4. Push with `-u origin HEAD` if the branch has no upstream.
5. Open the PR with `gh pr create` — HEREDOC body, Summary + Test Plan sections.
6. Return the PR URL to the user.

## If Any Check Fails

STOP. Report:
- Which check blocked
- File:line evidence
- The fix the user needs to make

Do not proceed to commit. Do not suggest `--no-verify` or other bypasses.

## Notes

- Pre-loaded state above is captured at skill invocation time. If the user makes more edits after running `/pr`, re-run it to refresh.
- The code-reviewer agent runs in its own context — it will not see this conversation's history, so pass it the full file list explicitly.
- Never force-push. Never commit to `main`, `master`, `LIVE`, or `Production` branches.
