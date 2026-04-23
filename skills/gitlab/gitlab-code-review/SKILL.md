---
name: gitlab-code-review
description: Review code changes on GitLab Merge Requests by analyzing diffs, leaving inline comments, and performing thorough pre-merge review. Uses the gitlab-review plugin tools for native API integration with buffered review submission.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [GitLab, Code-Review, Merge-Requests, Quality]
    related_skills: [gitlab-auth, gitlab-mr-workflow]
---

# GitLab Merge Request Code Review

Perform code reviews on GitLab Merge Requests using native API tools. The `gitlab-review` plugin provides tools for viewing MRs, reading diffs, posting comments, and submitting reviews. **Comments are buffered** and submitted all at once so the reviewer sees the complete review in one shot, with the summary at the top.

## Prerequisites

- `GITLAB_TOKEN` environment variable set (see `gitlab-auth` skill)
- `GITLAB_URL` set for self-hosted GitLab (default: https://gitlab.com)
- The `gitlab-review` plugin enabled

### Quick Auth Check

```bash
if [ -n "${GITLAB_TOKEN:-}" ]; then
  echo "GitLab: ready (${GITLAB_URL:-https://gitlab.com})"
else
  echo "GitLab: NOT CONFIGURED — set GITLAB_TOKEN"
fi
```

---

## 1. Reviewing a Merge Request

### Step 1: Get MR Metadata + Diff

Use `gitlab_mr_view` to understand the MR scope. By default it returns metadata, diff, and file list all in one call:

```
gitlab_mr_view(project="group/project", mr_iid=42)
```

For large MRs, get metadata only (lighter response):

```
gitlab_mr_view(project="group/project", mr_iid=42, include_diff=false)
```

### Step 2: Check Existing Discussions

Avoid duplicating feedback already given:

```
gitlab_mr_discussions(project="group/project", mr_iid=42)
```

### Step 3: Check CI/CD Pipeline Status

```
gitlab_mr_pipelines(project="group/project", mr_iid=42)
```

### Step 4: Start a Buffered Review Session

**Always call this before posting review comments.** It opens a buffer so comments are collected instead of posted immediately:

```
gitlab_mr_review_start(project="group/project", mr_iid=42)
```

This automatically fetches the MR's diff_refs (head_sha, base_sha, start_sha) so you don't need to provide them for inline comments.

### Step 5: Apply the Review Checklist

Go through each category systematically (see Section 2 below). For each file, use `read_file` if you need more context around the changes.

### Step 6: Post Comments (Buffered)

After starting a review session, all comments are **buffered** — they won't appear on GitLab until you submit.

#### General Comment

```
gitlab_mr_comment(project="group/project", mr_iid=42, body="Overall the code looks clean.")
```

#### Inline Comment on a Specific Line

No need to provide `head_sha`/`base_sha`/`start_sha` — they're auto-resolved from the review session:

```
gitlab_mr_comment(
    project="group/project",
    mr_iid=42,
    file_path="src/auth/login.py",
    line=45,
    body="🔴 **Critical:** SQL injection — use parameterized queries."
)
```

For comments on deleted lines (old version):

```
gitlab_mr_comment(
    project="group/project",
    mr_iid=42,
    file_path="src/auth/login.py",
    line=30,
    line_type="old",
    body="This removed line was handling auth correctly — consider keeping it."
)
```

### Step 7: Submit the Review

When done, submit all buffered comments at once. The `summary` appears **first** (at the top of the review), followed by all inline comments below:

```
# Approve with summary
gitlab_mr_review_submit(summary="## Review Summary\n\nOverall clean implementation. Approved.", action="approve")

# Request changes with summary
gitlab_mr_review_submit(summary="## Review Summary\n\nCritical issues found that must be fixed.", action="request_changes")

# Comment only (no approval change)
gitlab_mr_review_submit(summary="## Review Summary\n\nSome suggestions, nothing blocking.", action="comment")
```

**The summary always appears at the top on GitLab UI** — the tool enforces this ordering regardless of when you wrote the summary vs inline comments.

---

## 2. Review Checklist

When performing a code review, systematically check:

### Correctness
- Does the code do what it claims?
- Edge cases handled (empty inputs, nulls, large data, concurrent access)?
- Error paths handled gracefully?
- No off-by-one errors or logic inversions?

### Security
- No hardcoded secrets, credentials, or API keys in the diff
- Input validation on user-facing inputs
- No SQL injection, XSS, or path traversal
- Auth/authz checks where needed
- No sensitive data logged or exposed in error messages

### Code Quality
- Clear naming (variables, functions, classes)
- No unnecessary complexity or premature abstraction
- DRY — no duplicated logic that should be extracted
- Functions are focused (single responsibility)
- No dead code or commented-out blocks

### Testing
- New code paths tested?
- Happy path and error cases covered?
- Tests readable and maintainable?
- No flaky test patterns (time-dependent, race conditions)?

### Performance
- No N+1 queries or unnecessary loops
- Appropriate caching where beneficial
- No blocking operations in async code paths
- Database queries use indexes effectively

### Documentation
- Public APIs documented
- Non-obvious logic has comments explaining "why"
- README updated if behavior changed
- Migration/deployment notes if applicable

---

## 3. Review Output Format

When submitting a review, use this structured format for the summary:

```markdown
## Code Review Summary

**Verdict: [Approved / Changes Requested / Comment]**

### 🔴 Critical
- **src/auth.py:45** — SQL injection: user input passed directly to query.
  Suggestion: Use parameterized queries.

### ⚠️ Warnings
- **src/models/user.py:23** — Password stored in plaintext. Use bcrypt or argon2.
- **src/api/routes.py:112** — No rate limiting on login endpoint.

### 💡 Suggestions
- **src/utils/helpers.py:8** — Duplicates logic in `src/core/utils.py:34`. Consolidate.
- **tests/test_auth.py** — Missing edge case: expired token test.

### ✅ Looks Good
- Clean separation of concerns in the middleware layer
- Good test coverage for the happy path
- Proper error handling in the data transformation pipeline

---
*Reviewed by Hermes Agent*
```

For inline comments, use these severity prefixes:

- 🔴 **Critical** — Must fix before merge
- ⚠️ **Warning** — Should fix, but not a blocker
- 💡 **Suggestion** — Nice to have, optional improvement

---

## 4. Decision: Approve vs Request Changes vs Comment

- **Approve** — No critical or warning-level issues, only minor suggestions or all clear
- **Request Changes** — Any critical or warning-level issue that should be fixed before merge
- **Comment** — Observations and suggestions, but nothing blocking (use when unsure or the MR is a draft)

---

## 5. Self-Hosted GitLab

All tools work identically with self-hosted GitLab. The `GITLAB_URL` environment variable controls the target instance:

```bash
# Point to your self-hosted instance
export GITLAB_URL="https://gitlab.mycompany.com"
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
```

No other configuration changes are needed — the tools use `GITLAB_URL` as the API base.

---

## 6. Complete Review Workflow (End-to-End)

When asked to "review MR #42" or "review the merge request":

1. `gitlab_mr_view(project, mr_iid=42)` — get metadata + diff + file list
2. `gitlab_mr_discussions(project, mr_iid=42)` — check existing feedback
3. `gitlab_mr_pipelines(project, mr_iid=42)` — check CI status
4. `gitlab_mr_review_start(project, mr_iid=42)` — **start buffered review session**
5. For each changed file, use `read_file` if you need more context
6. Apply the review checklist (Section 2)
7. `gitlab_mr_comment(...)` — post inline comments (buffered)
8. `gitlab_mr_review_submit(summary="...", action="approve|request_changes|comment")` — **submit all at once (summary first)**

### Extracting project path

The `project` parameter accepts either:
- A project path: `"group/project"` or `"group/subgroup/project"`
- A numeric project ID: `"12345"`

You can find the project path from the GitLab URL: `https://gitlab.com/group/project/-/merge_requests/42` → project is `"group/project"`.

---

## Tool Reference

| Action | Tool | Notes |
|--------|------|-------|
| View MR (metadata + diff + files) | `gitlab_mr_view(project, mr_iid, include_diff?)` | `include_diff=false` for metadata only |
| Start buffered review | `gitlab_mr_review_start(project, mr_iid)` | Required before review comments |
| Post comment (general or inline) | `gitlab_mr_comment(project, mr_iid, body, file_path?, line?)` | Add `file_path`+`line` for inline |
| Submit review (summary first) | `gitlab_mr_review_submit(summary?, action?)` | Posts all buffered comments at once |
| List MRs | `gitlab_mr_list(project, state?)` | Filter by state, labels, author |
| Check pipelines | `gitlab_mr_pipelines(project, mr_iid)` | CI/CD pipeline status |
| View discussions | `gitlab_mr_discussions(project, mr_iid)` | Existing comment threads |
