# GitHub authority allowlist and preflight enforcement

This document records the live downstream implementation of the Hermes Maintenance GitHub operation authority policy.

Scope: terminal-command approval behavior in Hermes Agent. The current implementation is conservative and downstream-first: it adds deterministic classification and evidence logging, allows only simple read-only green GitHub commands to avoid unnecessary approval prompts, and converts yellow/red GitHub operations into approval warnings rather than blanket allowlisting them.

## Live behavior

The terminal approval guard now calls `tools.github_authority.classify_github_command()` from `tools.approval.check_all_command_guards()` after the hardline and sudo-stdin floors and alongside Tirith/dangerous-command checks.

Layering is intentional:

1. Hardline catastrophic blocks still run before all yolo/off/smart behavior.
2. Sudo stdin guessing still remains unconditionally blocked before yolo/off/smart behavior.
3. `approvals.mode: off`, `--yolo`, and session yolo keep their existing behavior after those unconditional floors.
4. GitHub authority classification never disables Tirith or existing dangerous-command warnings.
5. Green GitHub classification only avoids prompts when no other guard emits a warning.
6. Yellow/red GitHub classification adds a non-permanent approval warning even when generic dangerous-command regexes would not have matched the command.
7. Smart approval is bypassed for GitHub yellow/red policy warnings. These gates require objective preflight/Yunuen approval, not an auxiliary risk guess.
8. Yellow/red GitHub warnings hide permanent `[a]lways` approval and are never written to the permanent command allowlist.

## Green prompt-free allowlist

Only simple, parseable, single-command read-only GitHub operations are classified green for prompt-free execution:

- `gh pr view`, `gh pr diff`, `gh pr checks`, `gh pr status`, `gh pr list`
- `gh run view`, `gh run list`, `gh run watch`
- `gh repo view`, `gh repo list`
- `gh workflow view`, `gh workflow list`
- read-only `gh api` requests using GET/default method
- read-only GitHub `curl`/`wget` requests without mutating HTTP method or data payload
- read-only `git status`, `git diff`, `git log`, `git show`, `git branch`, and `git remote` forms, except branch deletion flags

Compound shell strings such as `gh pr view 25 && gh pr merge 25` are not green allowlisted. They fall back to the normal terminal guard path.

## Yellow preflight-required operations

Yellow operations are detected and surfaced as approval warnings that say mechanical preflight evidence is required. They are not automatically allowed yet.

Current yellow examples:

- `gh pr merge`
- `gh pr close`
- `gh pr create`, `gh pr comment`, `gh pr edit`, `gh pr review`, `gh pr ready`, `gh pr reopen`
- `gh run rerun`, `gh run cancel`, `gh run delete`
- mutating non-red `gh api` / GitHub HTTP requests
- `git push` to non-protected branches
- `git push --force-with-lease` to non-protected branches
- remote branch deletion
- `git commit --amend`

Required yellow preflight evidence remains the policy set: repository owner/scope, downstream/upstream boundary, task/profile branch identity, Kanban linkage, worktree cleanliness, changed-file review, secret scan, status checks, mergeability/review state, destructive target, replacement preservation when closing, and independent-review status.

## Red Yunuen-approval operations

Red operations are detected and surfaced as approval warnings that explicitly require Yunuen approval. They are not smart-approved and are not permanently allowlisted.

Current red examples:

- `gh repo delete`, `gh repo archive`, `gh repo unarchive`, `gh repo transfer`
- repository visibility/default-branch/settings edits through `gh repo edit`
- `gh secret ...`
- release create/upload/delete/edit
- workflow dispatch/enable/disable
- GitHub API/HTTP mutations targeting secrets, branch protection, rulesets, releases, packages, hooks, keys, deployments, or repository settings/deletion-sensitive paths
- plain `git push --force` / `git push -f`
- force/direct pushes to protected/shared branches such as `main`, `master`, `develop`, `production`, `prod`, or `staging`
- destructive git worktree/history operations such as `git reset` and `git clean`

## Evidence logging

Every classified non-unknown GitHub command emits an INFO log line with:

- tier
- command family
- preflight requirement flag
- reason
- truncated command
- parser evidence summary

This is audit evidence only; it is not a substitute for Kanban/GitHub/Matrix evidence after green write or yellow actions.

## Implementation boundary

This implementation intentionally does not execute yellow preflight checks. It only prevents yellow/red commands from slipping past the approval layer unnoticed and removes unnecessary prompts for read-only green commands. A future task can add a separate mechanical preflight executor for yellow operations after review of repository/branch/API context handling.
