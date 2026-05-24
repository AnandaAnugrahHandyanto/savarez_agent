# GitHub label router for Hermes Kanban

`scripts/github_router.py` ports the Snowman-style GitHub router contract into
Hermes. It is designed to run as a deterministic cron script (`--no-agent`): it
scans configured GitHub repositories, creates idempotent Kanban tasks for
explicit labels, and prints only when work is created or a lane fails.

## Label contract

Only these labels are used:

| Label | Meaning |
| --- | --- |
| `snowman:work` | Issue implementation or PR fix work |
| `snowman:review` | PR code-review work |
| `snowman:blocked` | Human/automation block; router skips the item |

Old progress labels such as `snowman:queued`, `snowman:working`, or
`snowman:reviewed` should not be used. Progress lives in Kanban tasks and
GitHub review/check state.

## Lanes

Each tick runs lanes independently per repo, so one failure does not stop the
rest:

1. `issue-dependency-unblock`
   - Parses issue-body lines like `Depends on: #123` and `Blocked by: #123, #456`.
   - Adds `snowman:blocked` while dependencies are open.
   - Removes `snowman:blocked` once all explicit dependencies close.
2. `issue-work`
   - Open issue + `snowman:work` + not blocked -> implementation task.
3. `pr-work`
   - Open non-draft PR + `snowman:work` + not blocked -> PR fix task.
4. `pr-review`
   - Open non-draft PR + `snowman:review` + not blocked + successful/no checks -> review task.

## Idempotency keys

The router checks Kanban before creating and only writes a GitHub tracking
comment for newly-created work.

- Issue implementation: `<owner>/<repo>:issue:<number>:work`
- PR fix: `<owner>/<repo>:pr:<number>:work:<head_sha>`
- PR review: `<owner>/<repo>:pr:<number>:review:<head_sha>:label:<latest_review_label_event>`

Including the PR head SHA lets new commits trigger fresh PR work/review tasks.
Including the latest `snowman:review` label event lets a human remove/re-add the
label to request another review at the same SHA.

## Configuration

Set either `HERMES_GITHUB_ROUTER_CONFIG` (recommended) or the simpler comma list.

```bash
export HERMES_GITHUB_ROUTER_CONFIG='{
  "board": "deepwork",
  "assignee": "default",
  "max_runtime": "2h",
  "skills": ["github-pr-workflow"],
  "repos": [
    {
      "full_name": "code-mandarin/project1",
      "workspace": "/Users/mr_p/project1"
    }
  ]
}'
python scripts/github_router.py
```

Simple mode:

```bash
export HERMES_GITHUB_ROUTER_REPOS="code-mandarin/project1"
export HERMES_GITHUB_ROUTER_WORKSPACE_ROOT="/Users/mr_p"
python scripts/github_router.py
```

Per-repo options in the JSON config override top-level defaults: `board`,
`assignee`, `max_runtime`, and `skills`.

## Cron registration

Copy or symlink `scripts/github_router.py` into `~/.hermes/scripts/`, or run it
from a repo checkout with an absolute path. Example:

```bash
hermes cron create "every 3m" \
  --name github-router \
  --script /Users/mr_p/.hermes/hermes-agent/scripts/github_router.py \
  --no-agent \
  --profile default \
  --deliver origin
```

No-op ticks produce empty stdout and therefore no delivery. Non-zero exits are
reserved for lane errors or configuration errors.

## Required access

The execution environment must have `gh` authenticated for every configured
repo and enough permissions for:

- repo metadata/read
- issues read/write
- pull requests read/write
- commit statuses read
- checks read

Actions API permissions are not required for review gating; the router uses
commit check-runs and combined commit status only.

## Verification checklist

1. `gh auth status`
2. `gh repo view OWNER/REPO`
3. `gh api repos/OWNER/REPO/issues?per_page=1`
4. `gh api repos/OWNER/REPO/commits/main/status`
5. Run the router twice against a test `snowman:work` issue.
6. Confirm only one Kanban task and one tracking comment were created.
7. Add `snowman:review` to a non-draft PR with green/no checks and confirm a review task.
8. Push a new commit to the PR and confirm a fresh review task for the new SHA.

## Emergency disable

In priority order:

1. Pause the cron job: `hermes cron list`, then `hermes cron pause <job-id>`.
2. Remove `snowman:work` / `snowman:review` from affected items.
3. Add `snowman:blocked` to affected items.
4. Pause/stop Kanban dispatchers or workers.
5. Revoke/suspend the bot token/App if necessary.
