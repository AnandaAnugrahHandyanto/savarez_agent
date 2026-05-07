# PR Review Policy (Flexible)

This repo uses a lightweight review model:

- PRs should be reviewed, but process stays practical.
- Maintainers can approve manually in GitHub UI.
- Maintainers can also approve via CLI/agent.
- No heavy mandatory checklist beyond baseline safety.

## Recommended Review Standard

Use severity tags in comments:
- 🔴 Critical: must fix before merge
- ⚠️ Warning: should fix before merge
- 💡 Suggestion: optional improvement

Decision guideline:
- Approve when no critical/warning issues remain.
- Request changes when blocking issues exist.
- Comment for non-blocking suggestions.

## Approve Manually (GitHub UI)

1. Open PR
2. Click **Files changed**
3. Add comments if needed
4. Click **Review changes** → **Approve**

## Approve via CLI / Hermes

```bash
# approve
gh pr review <PR_NUMBER> --approve --body "Looks good"

# request changes
gh pr review <PR_NUMBER> --request-changes --body "Please address inline comments"

# non-blocking comment
gh pr review <PR_NUMBER> --comment --body "A few suggestions"
```

## Keep It Unrestrictive

Recommended repo settings:
- Require PRs before merge: ON
- Required approvals: 0 or 1 (team preference)
- Auto-dismiss stale approvals: OFF (for speed) unless needed
- Required status checks: only core CI checks
- Allow squash merge: ON

This keeps safety high while preserving fast manual control.
