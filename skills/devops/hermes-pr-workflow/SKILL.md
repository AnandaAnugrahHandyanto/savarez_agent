---
name: hermes-pr-workflow
description: Use when creating pull requests for hermes-agent or any GitHub fork-based project. Covers branch creation, conventional commits, pushing to fork, and creating PRs with gh CLI.
version: 1.0.0
author: Hermes
license: Apache-2.0
metadata:
  hermes:
    tags:
      - github
      - pull-requests
      - git
      - gh-cli
      - workflow
    related_skills: []
---

# GitHub Fork PR Workflow

## Overview

Standard workflow for contributing PRs to a GitHub project via fork. Works with any fork-based contribution model.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`)
- Fork created on GitHub
- `upstream` remote configured pointing to the original repo

## Remote Setup

```bash
# One-time setup
git remote add upstream https://github.com/OWNER/REPO.git
git remote add fork https://github.com/YOUR_FORK/REPO.git
```

Verify:
```bash
git remote -v
# origin    → YOUR_FORK/REPO (push target)
# upstream  → OWNER/REPO (read-only)
```

**Push to `fork`/`origin` (your fork), never `upstream`.**

## Workflow

### 1. Sync & Branch

```bash
git checkout main
git fetch upstream
git merge upstream/main          # or: git rebase upstream/main
git checkout -b feat/short-desc  # or fix/, docs/, refactor/, etc.
```

### 2. Commit (Conventional Commits)

```
feat(scope): description
fix(scope): description
docs(scope): description
refactor(scope): description
```

Keep commits focused — one logical change per commit.

**Squash if needed:**
```bash
git reset --soft HEAD~N
git commit -m "feat(scope): description"
```

### 3. Push to Fork

```bash
git push -u origin branch-name
```

### 4. Create PR

```bash
gh pr create \
  --repo OWNER/REPO \
  --head YOUR_FORK:branch-name \
  --base main \
  --title "feat(scope): description" \
  --body-file - <<'EOF'
## What does this PR do?

Clear description of the problem and solution.

## Related Issue

Fixes #123

## Type of Change

- [ ] 🐛 Bug fix
- [ ] ✨ New feature
- [ ] ♻️ Refactor
- [ ] 📝 Documentation
- [ ] ✅ Tests

## Changes Made

- `path/to/file.py`: what changed and why

## How to Test

1. Step to reproduce
2. Expected result

## Checklist

- [ ] Conventional Commits format
- [ ] Only related changes (no drive-by fixes)
- [ ] Tested on target platform
- [ ] Added tests (if applicable)
EOF
```

**⚠️ Use `--body-file -` with heredoc — `--body "..."` breaks on `&` and special chars.**

## Common Pitfalls

| Problem | Fix |
|---------|-----|
| Push to `upstream` fails (403) | Push to your fork remote instead |
| `gh pr create` fails with `&` in body | Use `--body-file -` with heredoc |
| Wrong commit message format | `git reset --soft HEAD~1` and recommit |
| Branch has unrelated commits | `git reset --soft` to squash |
| Fork out of sync with upstream | `git fetch upstream && git rebase upstream/main` |
| PR shows wrong file changes | Check branch is based on latest upstream main |
