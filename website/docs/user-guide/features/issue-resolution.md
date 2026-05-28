---
title: "Issue Resolution Lane"
description: "Headless GitHub issue automation with SQLite state, FIFO execution, Master Epic decomposition, and cloud review."
sidebar_label: "Issue Resolution Lane"
---

# Issue Resolution Lane

Hermes Gateway includes a headless `/issue` automation lane for GitHub issue
resolution. The lane is designed for daemon operation: it can be triggered from a
messaging command or a GitHub `issues` webhook, persists its own state in SQLite,
resumes interrupted work after gateway restarts, and does not require an active
editor, GUI, or desktop session.

The implementation lives in:

- `gateway/issue_resolution.py` — state machine, queue worker, Aider command
  construction, Guardian decomposition, and GitHub issue/PR operations.
- `gateway/run.py` — `/issue` command dispatch and startup resume.
- `gateway/platforms/webhook.py` — GitHub issue webhook conversion into `/issue`.
- `hermes_cli/commands.py` — central slash-command registry.

## Triggering

Manual messaging command:

```text
/issue owner/repo 123 --workdir /path/to/checkout
```

GitHub URL form is also accepted:

```text
/issue https://github.com/owner/repo/issues/123 --workdir /path/to/checkout
```

The command is gateway-only. It queues the request and returns a run id; local
coding work then proceeds from the persistent queue.

Webhook trigger:

```yaml
platforms:
  webhook:
    enabled: true
    extra:
      routes:
        github-issues:
          events: ["issues"]
          secret: "github-webhook-secret"
          automation: github_issue_resolution
          deliver: telegram
```

When `automation: github_issue_resolution` is set, GitHub `issues` payloads are
converted into `/issue --repo owner/name --issue N`. Payloads that represent pull
requests are ignored.

## State Database

The default state database is:

```text
~/.hermes/issue_resolution.db
```

`issue_runs` stores the queue. `master_subissues` stores Master Epic child issue
mappings.

Run statuses:

| Status | Meaning |
| --- | --- |
| `queued` | Persisted and waiting for the worker. |
| `running` | Claimed by the single-flight worker. |
| `expanded` | Master Epic has been decomposed and child sub-issues have been queued. |
| `completed` | Issue/sub-issue produced PR feedback, or all Master Epic children completed. |
| `failed` | Execution raised an exception; truncated error text is stored. |

Run types:

| Type | Meaning |
| --- | --- |
| `issue` | Normal GitHub issue. |
| `master` | Master Epic issue. |
| `sub_issue` | Generated child issue from a Master Epic. |

## FIFO Single-Flight Execution

`submit_issue_resolution()` persists the run and starts the worker if needed.
`_issue_queue_worker()` repeatedly claims the oldest queued row using `ORDER BY id
ASC LIMIT 1`. `claim_next_run()` marks that row `running` before execution.

This gives the local coder lane strict FIFO behavior and prevents multiple local
Aider/Guardian jobs from competing for the same host inference capacity.

## Startup Resume

`GatewayRunner.start()` calls `resume_issue_resolution_queue()` during gateway
startup. Resume performs three steps:

1. Reset every interrupted `running` row back to `queued`.
2. Count pending `queued` rows.
3. Start the single-flight worker when pending work exists.

This covers gateway restarts, host reboots, and crashes where a local coder run
was interrupted before it could mark the row `completed`, `expanded`, or
`failed`.

## Master Epic Decomposition

An issue is treated as a Master Epic when either trigger matches:

- It has the `master-plan` label.
- Its body starts with `# Master Project Plan` after leading whitespace is
  ignored.

Master Epics are decomposed locally through Guardian using the OpenAI-compatible
`/v1/chat/completions` API. The model resolves in this order:

1. `HERMES_ISSUE_DECOMPOSE_MODEL`
2. `DEFAULT_MODEL`
3. `qwen3-35b-uncensored`

Expected response shape:

```json
{
  "tasks": [
    {
      "title": "Add persistent queue",
      "body": "Implement SQLite-backed issue run persistence."
    }
  ]
}
```

Each task becomes a GitHub sub-issue. Hermes writes `Part of Master Issue #X` in
the sub-issue body, records the mapping in `master_subissues`, and queues each
child as `sub_issue` work.

## Aider Roles

Local coder:

- Uses Guardian through `http://127.0.0.1:11434/v1`.
- Requires `AIDER_GUARDIAN_API_KEY`.
- Defaults to `openai/qwen3-35b-uncensored` unless `AIDER_LOCAL_MODEL`,
  `AIDER_MODEL`, or `DEFAULT_MODEL` overrides it.

Cloud reviewer:

- Uses OpenRouter.
- Requires `OPENROUTER_API_KEY` or `OPENROUTER_API_KEY_FILE`.
- Defaults to `openrouter/deepseek/deepseek-v4-flash`.
- Runs with prompt caching and no auto-commits.

## PR Feedback

Normal and generated sub-issues follow the same flow:

1. Checkout or create `issue/<number>-<slug>`.
2. Run local Aider against Guardian.
3. Push the branch.
4. Create or find a PR.
5. Store `pr_number` and `pr_url` on the run.
6. Run cloud Aider reviewer through OpenRouter.
7. Post reviewer output as an inline PR comment when a diff anchor is available,
   otherwise as a regular PR review comment.

## Operational Inspection

Queue state:

```bash
sqlite3 ~/.hermes/issue_resolution.db \
  'SELECT id, repo, issue_number, run_type, status, parent_run_id, pr_number FROM issue_runs ORDER BY id;'
```

Master Epic children:

```bash
sqlite3 ~/.hermes/issue_resolution.db \
  'SELECT master_run_id, position, sub_issue_number, title FROM master_subissues ORDER BY master_run_id, position;'
```

## Current Limitations

- There is no cancellation command yet.
- Per-repo allowlists and richer retry policy are still future hardening.
- Guardian decomposition currently creates sub-issues from returned tasks; it
  should be hardened to detect existing issue references such as `#182` and reuse
  or link them instead of creating duplicates.
