---
name: github-pr-reviewer
description: |
  Automated GitHub PR code review — fetches the diff, reviews every changed
  file for bugs, security issues, performance problems, and missing error
  handling, then posts structured inline comments directly to the PR.
version: 0.1.0
author: HeLLGURD
license: MIT
platforms: [linux, macos, windows]
category: software-development
triggers:
  - "review PR [URL]"
  - "review this PR"
  - "code review [URL]"
  - "review pull request [URL]"
  - "review the diff"
  - "review [owner/repo#N]"
  - "give me a code review"
toolsets:
  - terminal
  - file
metadata:
  hermes:
    tags: [GitHub, Code-Review, Pull-Request, Security, Quality, Automation]
    related_skills: [code-wiki, rest-graphql-debug, web-pentest]
---

# GitHub PR Reviewer

Perform a thorough, automated code review on any GitHub pull request. Fetches
the diff via the `gh` CLI or GitHub API, reviews every changed file across five
dimensions, and posts structured inline comments directly to the PR — just like
a senior engineer would.

This skill is **additive to human review**, not a replacement. It catches the
mechanical issues (null-checks, error swallowing, SQL injection, missing tests)
so the human reviewer can focus on architecture and intent.

---

## When to Use

- User says "review PR [URL]", "code review this PR", "review [owner/repo#N]"
- User pastes a GitHub PR link and asks for feedback
- User wants a second opinion before merging

Do NOT use for:
- Reviewing local uncommitted diffs — use `git diff` and answer inline
- Architecture-level design reviews — have that conversation directly
- PRs on private repos where the user has not authenticated `gh`

---

## Prerequisites

Either:
- **`gh` CLI** installed and authenticated (`gh auth status`), OR
- **`GITHUB_TOKEN`** env var set (for curl-based fallback)

No other dependencies. All review logic runs in the agent — no external
service calls beyond GitHub API.

---

## How to Run

Trigger phrase examples:
```
review PR https://github.com/owner/repo/pull/42
code review owner/repo#42
review this PR: https://github.com/NousResearch/hermes-agent/pull/40481
```

---

## Execution Workflow

### Step 0 — Parse the PR reference

Extract `OWNER`, `REPO`, `PR_NUMBER` from whatever the user provided:
- Full URL: `https://github.com/OWNER/REPO/pull/N`
- Short form: `OWNER/REPO#N`
- Just a number (if repo context is clear from conversation)

```bash
# Verify gh auth
gh auth status 2>&1 || echo "gh not authenticated — will use curl fallback"
```

### Step 1 — Fetch PR metadata

```bash
gh pr view $PR_NUMBER --repo $OWNER/$REPO \
  --json title,author,body,baseRefName,headRefName,additions,deletions,changedFiles,labels,isDraft
```

Print a one-line summary:
```
PR #N — "<title>" by @author (+additions/-deletions across N files)
```

If the PR is a draft, note it prominently. Do not post comments to draft PRs
without the user confirming they want early feedback.

### Step 2 — Fetch the diff

```bash
gh pr diff $PR_NUMBER --repo $OWNER/$REPO
```

If `gh` is unavailable, fall back to:
```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER
```

Save the diff to a temp file:
```bash
gh pr diff $PR_NUMBER --repo $OWNER/$REPO > /tmp/pr_$PR_NUMBER.diff
```

### Step 3 — Parse changed files

From the diff header lines (`+++ b/path/to/file`), extract every changed file
and its language. Build a review plan:

| File | Language | Added | Removed | Priority |
|------|----------|-------|---------|----------|
| src/auth.py | Python | 45 | 12 | HIGH (auth) |
| lib/db.ts | TypeScript | 23 | 5 | HIGH (db) |
| README.md | Markdown | 8 | 2 | LOW |

Prioritize: **auth, db, crypto, config, API surface** first; docs/tests last.

### Step 4 — Review each file

For each changed file (highest priority first), review the diff hunks through
five lenses:

#### 4a. Correctness & Bugs
- Off-by-one errors, wrong operator (`=` vs `==`, `&` vs `&&`)
- Null/undefined dereference on values that can be absent
- Unreachable code or dead branches
- Wrong return type or missing return
- Race conditions (shared mutable state accessed without a lock)
- Incorrect algorithm (e.g. comparing floats with `==`)

#### 4b. Security
- **Injection** — SQL (`f"SELECT * FROM users WHERE id={user_id}"`),
  shell (`os.system(user_input)`), SSTI, path traversal
- **Secrets in code** — hardcoded API keys, passwords, tokens
- **Insecure defaults** — `verify=False` on TLS, `shell=True`, `pickle.loads`
  on untrusted input, `eval()`/`exec()` on external data
- **Missing auth/authz checks** on new endpoints
- **Timing attacks** — plain `==` on secrets instead of `hmac.compare_digest`
- **Open redirect** — user-controlled redirect targets

#### 4c. Error handling
- Bare `except:` or `except Exception: pass` that swallows errors silently
- Missing error propagation (function returns `None` on failure, caller
  assumes success)
- `TODO` / `FIXME` left in production-path code
- Unclosed resources (file handles, DB connections, HTTP sessions) on the
  error path

#### 4d. Performance
- N+1 query patterns (loop + DB call)
- Large object copies that could be iterators or generators
- Blocking I/O in async context (`time.sleep`, `requests.get` inside `async def`)
- Missing indexes implied by new filter conditions
- Unbounded growth (appending to a list inside an infinite loop)

#### 4e. Test coverage
- New public functions or API endpoints with no corresponding test added
- Tests that only cover the happy path (missing error-branch tests)
- Hardcoded test data that belongs in a fixture

### Step 5 — Compile findings

For each finding, record:

```
FILE: src/auth.py
LINE: 87
SEVERITY: HIGH | MEDIUM | LOW | INFO
CATEGORY: Security | Bug | ErrorHandling | Performance | Tests
FINDING: <one sentence>
SUGGESTION: <concrete fix with code snippet if helpful>
```

Severity guide:
- **HIGH** — exploitable security issue, data loss, crash on common input
- **MEDIUM** — incorrect behavior on edge cases, missing error handling on
  important paths
- **LOW** — style, minor inefficiency, missing test for uncommon path
- **INFO** — suggestion, not a problem

### Step 6 — Post inline comments to GitHub

For every HIGH and MEDIUM finding, post an inline review comment:

```bash
# Post a single inline comment
gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments \
  --method POST \
  --field body="**[$CATEGORY] $FINDING**\n\n$SUGGESTION" \
  --field commit_id="$(gh pr view $PR_NUMBER --repo $OWNER/$REPO --json headRefOid -q .headRefOid)" \
  --field path="$FILE" \
  --field line=$LINE \
  --field side="RIGHT"
```

Batch all comments, then submit the review:

```bash
gh pr review $PR_NUMBER --repo $OWNER/$REPO \
  --comment \
  --body "$(cat /tmp/pr_${PR_NUMBER}_summary.md)"
```

**Do not** post a blocking `--request-changes` review without the user's
explicit approval — comments only by default.

### Step 7 — Print summary to user

After posting, output a formatted summary:

```
## PR #N Review — <title>

Reviewed N files | +X -Y lines

### Findings

| Severity | Category | File | Line | Summary |
|----------|----------|------|------|---------|
| 🔴 HIGH   | Security | src/auth.py | 87 | SQL injection via f-string |
| 🟠 MEDIUM | Bug      | lib/api.ts  | 134 | Unhandled promise rejection |
| 🟡 LOW    | Tests    | tests/      | —   | No test for error branch |

### Verdict

APPROVE / COMMENT / REQUEST_CHANGES (pending user decision)

All HIGH/MEDIUM findings posted as inline comments on the PR.
```

---

## Posting Strategy

**Default behavior (no user override):**
- Post inline comments for HIGH and MEDIUM findings only
- Submit as `COMMENT` (never auto-approve or auto-request-changes)
- Do NOT post for LOW/INFO — include them in the summary printout only

**User can override:**
- "post all findings" → post LOW and INFO too
- "request changes" → submit review as `--request-changes`
- "approve if clean" → if zero HIGH/MEDIUM findings, submit `--approve`
- "dry run" → print all findings, post nothing to GitHub

---

## Edge Cases

**PR is too large (>500 changed files):**
Ask the user which files or directories to focus on. Don't try to review
everything — the review will be shallow and miss things.

**Binary files in diff:**
Skip silently. Note in summary: "N binary files skipped."

**Minified or generated files (`.min.js`, `*_pb2.py`, migration auto-gen):**
Skip. They're not hand-written and findings would be noise.

**`gh` not installed:**
Fall back to curl for diff fetch and comment POST. Inform the user that
`gh` makes authentication easier and link to https://cli.github.com.

**Rate limiting:**
If GitHub returns 403/429, wait 60 seconds and retry once. If still failing,
save findings to `/tmp/pr_${PR_NUMBER}_review.md` and tell the user to post
manually.

---

## What This Skill Does NOT Cover

- Architecture-level design decisions (discuss those in conversation)
- Business logic correctness (requires domain context the agent may not have)
- Performance benchmarking (needs profiling data, not static analysis)
- Dependency vulnerability scanning — use the `osv-check` tool or `osv-scanner`
- Full test execution — use `terminal` directly to run the test suite

---

## Further Reading

- GitHub REST API — Pull Request Review Comments:
  https://docs.github.com/en/rest/pulls/comments
- `gh pr review` reference:
  https://cli.github.com/manual/gh_pr_review
- OWASP Code Review Guide:
  https://owasp.org/www-project-code-review-guide/
