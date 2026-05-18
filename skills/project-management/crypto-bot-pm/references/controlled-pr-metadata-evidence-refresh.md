# Controlled PR metadata evidence refresh

Session-derived pattern: after crypto_bot S006 reached local evidence PASS, remote PR branch/head sync, and CI pass, the remaining remote-lifecycle blocker was stale PR body/evidence links. The Operator approved exactly one Gitea PR metadata update: update the existing PR body for one PR only, with no push, no new PR, no statuses/checks, no runner/workflow start, no merge, no deploy, no secrets, and no runtime/broker/trading actions.

Reusable sequence:

1. Reconfirm scope before mutation:
   - PR number, repository, source branch, target branch, and exact source HEAD.
   - Local and remote branch HEAD match the approved SHA.
   - Approved evidence files exist and are the only evidence paths to include.
   - Worktrees are clean if they are part of the evidence claim.
2. Draft the PR body to a local operator-state file first.
   - Include the exact approved evidence paths as literal strings; Markdown links are fine if the literal path text appears in the body.
   - Run a secret-looking token scan over the draft before PATCH.
   - Keep the title/head/base unchanged unless the approval explicitly includes them.
3. Perform one PATCH to the existing PR endpoint only:
   - `PATCH /api/v1/repos/<owner>/<repo>/pulls/<number>`
   - JSON payload: `{ "body": <draft_body> }`
   - Use an existing token or credential helper without printing credential material.
4. Verify with read-only GET/audit:
   - PR number unchanged.
   - title unchanged.
   - state remains open unless a different state was approved.
   - head SHA unchanged and equals the validated source HEAD.
   - actual PR body contains all approved evidence path strings.
5. Run explicit read-only PR/CI audit with fresh evidence arguments, not legacy defaults:
   - `--pr-number <n>`
   - `--source-head <validated-head>`
   - `--pr-evidence-packet <fresh-packet>`
   - `--completion-gate <fresh-gate>`
6. Run merge-readiness dry-run with normalized CI evidence if needed. A valid remote lifecycle may be `merge_ready` in PR/CI audit while actual merge remains blocked by policy.

Important pitfall:

`crypto_bot_pr_ci_audit.py` has legacy defaults for S006 evidence/head. If called without explicit `--source-head`, `--pr-evidence-packet`, and `--completion-gate`, it can report stale mismatch even after the PR body was correctly updated. For post-refresh verification, always use explicit fresh arguments and report the artifact path of that explicit audit.

Reporting checklist:

- The exact mutation endpoint and field changed (`body` only).
- The local body draft path and secret-scan result.
- PATCH status and immutable PR identity fields after PATCH.
- Latest explicit PR/CI audit path and key fields: blockers, warnings, actual PR body link status, PR identity, CI state, evidence pass fields, remote lifecycle state.
- Merge-readiness dry-run result and remaining policy gate.
- Explicit non-actions: no new PR, no push, no statuses/checks, no runner/workflow, no merge, no deploy, no secrets, no runtime/broker/trading actions.
