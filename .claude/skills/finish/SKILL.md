<!--
Written fresh: v0.3.1 cleanup pass (closes dry-run trace #10 from docs/build-notes/adversarial-cleanup-2026-04-22.md)
Original purpose: Commit-and-close-out discipline for when user signals task completion intent without wanting the full PR workflow.
Created: 2026-04-22
Operator: Porter Tanner
-->

---
name: finish
description: Use PROACTIVELY when user says "commit and finish", "wrap this up", "close this out", "finish what you started", "ship it", or signals end-of-task closure on in-progress work. Runs completion sequence — verify work is actually done (not claimed done), stage remaining changes, write commit message matching commit-conventions.md, commit, summarize what shipped. DO NOT USE for pull-request workflows — that is the `pr` skill (preloaded in the code-reviewer sub-agent).
argument-hint: "[optional: specific files or summary of what's finishing]"
allowed-tools: Bash(git *) Read Grep Glob
---

# Finish — Commit-and-Close-Out

End the current work cleanly. Verify, stage, commit, report. Halt before push.

**Context**: $ARGUMENTS

---

## When This Fires vs. `pr`

Both `finish` and `pr` end with a commit. They are NOT the same.

| Signal | Skill |
|---|---|
| "commit and finish what you started" / "wrap this up" / "ship it" | **`finish`** — main-session commit, no PR submission |
| "open a PR" / "submit this" / "review and push" | **`pr`** — preloaded in code-reviewer sub-agent; runs full preflight + submission |

`finish` is the mid-session close-out: your commit discipline without the full PR submission / review-delegation / gh-cli workflow. Use it when the user wants to persist in-progress work and end the task, not when they want to open a pull request.

---

## Protocol

### Step 1: Verify work is actually done

**Do not trust your own claim of "done."** Before committing, prove it:

```bash
git status
git diff --stat HEAD
```

For each modified file:
- Read it. Confirm the changes you intended are actually present.
- Grep for any TODO markers you added as placeholders but forgot to fill in.
- Check for commented-out code, debug prints, or scratch-pad content that shouldn't ship.

If the verification surfaces missing work, stop and report — do not commit partial/false-finished work as done.

### Step 2: Stage remaining changes

**Explicit file-by-file staging**, never `git add .` or `git add -A`:

```bash
git add <file1> <file2> ...
```

Verify the staged set matches the intended finish scope:

```bash
git diff --cached --stat
```

### Step 3: Write the commit message

Follow [workflows/commit-conventions.md](../../workflows/commit-conventions.md):

- **Subject**: `<type>(<scope>): <imperative summary>` — under 70 chars.
- **Body** (required for `fix`, recommended for `feat`): what was done, why, and one line of evidence.
- **Footer**: `Co-Authored-By: Claude <noreply@anthropic.com>` (or project-specific attribution).
- Use HEREDOC format in Bash for multi-line messages.

### Step 4: Execute the commit

```bash
git commit -m "$(cat <<'EOF'
<subject>

<body>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

Report the commit SHA and the first line of the message back to the operator.

### Step 5: Summary report

Report what shipped:
- **Files touched** (from `git diff --name-only HEAD~1`)
- **Commit SHA** (short)
- **Subject line** of the commit
- **What's outstanding** — explicit list of items intentionally deferred (to BACKLOG.md or a follow-up session)

### Step 6: Halt before push

**Never push automatically.** Push is always operator-initiated:
- If the task genuinely needs to go to the remote, tell the operator explicitly: "Ready to push. Run `git push` when you want it live."
- For a PR submission, route to the `pr` skill (preloaded in code-reviewer) — `finish` only commits locally.

---

## Output Format

```
╔══════════════════════════════════════════════════╗
  FINISH
╚══════════════════════════════════════════════════╝

VERIFIED
  - <file>:<line range> — <what was confirmed done>
  - <file>:<line range> — ...

STAGED
  <N files>

COMMITTED
  SHA: <short>
  Subject: <subject line>

OUTSTANDING (deferred)
  - <item 1, to BACKLOG.md / follow-up>
  - <item 2>
  (or "None — task is fully closed.")

NEXT STEP
  <"Ready to push." | "Route to pr skill for PR submission." | "Continue in next session.">
```

---

## Rules

1. **Verify before committing.** "I'm done" is not a verification — read the modified files and confirm the changes present.
2. **Explicit file staging only.** Never `git add .` / `git add -A`. Accidental inclusion of sensitive or unrelated files is how credentials leak.
3. **Commit messages follow [commit-conventions.md](../../workflows/commit-conventions.md).** No WIP commits on protected branches. Imperative mood.
4. **Never push automatically.** Push is an operator action. State readiness; do not execute.
5. **Never delegate to PR submission.** `finish` is main-session close-out. For PR workflows, the user routes to `pr` explicitly or via sub-agent.
6. **Surface outstanding work.** If anything was intentionally deferred, name it and route it to BACKLOG.md.
