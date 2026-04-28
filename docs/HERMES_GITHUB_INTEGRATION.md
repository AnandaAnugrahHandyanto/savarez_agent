# Hermes GitHub Integration

P1 adds a secure GitHub metadata and ChatOps bridge for Hermes Code Mode. It is backend/API/CLI only in this checkout because `hermesWeb/` is not present and the legacy `web/` directory is deprecated for new HermesWeb work.

## Capabilities

- Register GitHub App installations and repositories in Hermes state.
- Generate GitHub App installation tokens from `HERMES_GITHUB_APP_ID` and `HERMES_GITHUB_APP_PRIVATE_KEY_PATH`.
- Keep installation tokens in memory only, with expiry metadata.
- Sync repository, branch, issue, pull request, webhook delivery, ChatOps, and status metadata.
- Validate GitHub webhook signatures before processing payloads.
- Parse `@hermes plan`, `@hermes review`, `@hermes fix`, `@hermes explain`, and `@hermes status`.
- Convert ChatOps requests into `ArtifactLedger` artifacts and `AgentOrchestrator` runs.
- Prepare PR metadata without pushing branches or creating/merging PRs automatically.
- Gate GitHub comment writes through Hermes approvals.

## GitHub App Setup

Create a GitHub App with these minimum repository permissions:

- Metadata: read
- Contents: read
- Issues: read/write
- Pull requests: read/write
- Checks: read/write
- Commit statuses: read/write

Subscribe only to these webhook events for P1:

- `installation`
- `installation_repositories`
- `issues`
- `issue_comment`
- `pull_request`
- `pull_request_review`
- `pull_request_review_comment`
- `check_suite`
- `check_run`
- `push`

Configure environment variables with example names only:

```bash
HERMES_GITHUB_APP_ID=
HERMES_GITHUB_APP_PRIVATE_KEY_PATH=
HERMES_GITHUB_WEBHOOK_SECRET=
HERMES_GITHUB_DEV_PAT=
HERMES_GITHUB_ALLOW_DEV_PAT=
```

`HERMES_GITHUB_DEV_PAT` is ignored unless `HERMES_GITHUB_ALLOW_DEV_PAT=1`. This fallback is only for local development and should not be used as the primary integration model.

## Security Model

- Private key contents are read from the configured path and are never stored in SQLite.
- Installation access tokens are cached only in memory and expire according to GitHub metadata.
- Webhook payloads are processed only after `X-Hub-Signature-256` validation.
- Secrets, tokens, private keys, webhook secrets, and Authorization headers are redacted from service errors.
- GitHub write actions are approval-gated by default.
- P1 never auto-merges, force-pushes, deletes branches, modifies repository settings, or changes GitHub permissions.

## API

GitHub endpoints live under `/api/code/github/*`:

- `GET /api/code/github/status`
- `GET /api/code/github/installations`
- `GET /api/code/github/repositories`
- `POST /api/code/github/repositories/sync`
- `GET /api/code/github/repositories/{owner}/{repo}`
- `GET /api/code/github/repositories/{owner}/{repo}/issues`
- `GET /api/code/github/repositories/{owner}/{repo}/pulls`
- `POST /api/code/github/webhooks`
- `POST /api/code/github/chatops/{command_id}/run`
- `POST /api/code/github/comments`
- `POST /api/code/github/pull-requests/prepare`

Only `/api/code/github/webhooks` bypasses the local HermesWeb session token. It is protected by the GitHub webhook HMAC signature instead.

## CLI

Minimal CLI commands:

```bash
/github status
/github repos
/github sync
/github sync --dry-run
```

The commands degrade gracefully when GitHub is unconfigured, authentication is missing, the backend is offline, or no repositories are synced.

## Local Webhook Testing

Use a tunnel such as `ngrok` or `cloudflared` to expose the local backend, then configure the GitHub App webhook URL:

```text
https://<tunnel-host>/api/code/github/webhooks
```

Set `HERMES_GITHUB_WEBHOOK_SECRET` locally and use the same value in the GitHub App webhook settings. Do not commit `.env` values.

## P1 Limitations

- No HermesWeb panel is implemented because `hermesWeb/` is absent.
- No automatic clone flow is implemented.
- No autonomous coding loop is triggered directly from webhooks.
- PR creation is prepared as metadata/artifacts only; branches are not pushed and PRs are not opened automatically.
- Line-specific PR review comments are deferred until diff mapping is implemented cleanly.

## P2 Recommendation

P2 should add a `hermesWeb/` GitHub panel, richer approval UX for GitHub writes, PR diff mapping for line comments, approval-gated clone/workspace registration, and check/status publishing tied to real orchestration lifecycle events.
