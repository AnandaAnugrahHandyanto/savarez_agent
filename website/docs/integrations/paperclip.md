---
title: "Paperclip"
description: "Evaluate Paperclip locally with Hermes webhooks without wiring it into production workflows."
sidebar_label: "Paperclip"
---

# Paperclip

## What this is

Paperclip is an external agent control plane for coordinating AI-agent companies, issues, routines, heartbeats, approvals, and workspaces.

This page documents a local-only evaluation workflow that sends Paperclip routine or issue events into an existing Hermes webhook route. Use it to smoke-test whether Paperclip's issue and routine model is useful for your Hermes workflow without giving Paperclip production repository, Slack, CI, Kanban, or secret access.

The first integration path is one way:

1. Paperclip emits a routine, webhook, or issue event in a sandbox.
2. Paperclip or a local `curl` command sends a signed HTTP POST to Hermes.
3. The Hermes webhook adapter validates the HMAC signature, applies rate limits and idempotency, and accepts the event.
4. Hermes either starts an agent prompt or direct-delivers a notification to an already configured target.

## What this is not

This is intentionally not a production integration. It is not:

- Production PR review or a replacement for your GitHub review process.
- Slack integration, Slack posting, or Slack thread synchronization.
- CI enforcement or a GitHub Action.
- Secret sync between Paperclip and Hermes.
- A replacement for Hermes Kanban or Hermes' existing task ownership model.
- A guide for deploying Paperclip on public infrastructure.

## Architecture

The local smoke workflow uses the existing Hermes webhook platform as the security boundary. Paperclip does not need Hermes credentials. Hermes does not need a Paperclip API key for this one-way test.

```text
Paperclip routine/webhook or issue event
        |
        | signed HTTP POST
        v
Hermes /webhooks/paperclip-local route
        |
        | HMAC validation, event filtering, rate limiting, idempotency
        v
Hermes agent prompt or direct-delivery notification
```

Suggested first-pass mapping:

| Paperclip concept | Hermes local smoke-test mapping |
| --- | --- |
| Paperclip issue | Hermes prompt context, or a manually reviewed Kanban task summary after the smoke test. Do not auto-sync Kanban in this first workflow. |
| Paperclip comment | Hermes prompt text, usually embedded in the signed webhook payload. |
| Paperclip issue document | Markdown artifact reference in the webhook payload or Hermes prompt context. |
| Paperclip routine | Hermes webhook trigger, or a comparison point for a future Hermes cron job design. |

## Local smoke test

Run this only on a development machine or disposable sandbox. Keep the gateway bound to loopback unless you have explicitly configured a signed route and understand the exposure.

```sh
# 1. Enable the Hermes webhook platform locally via gateway setup or config.yaml.
hermes gateway setup

# 2. Create a route for local Paperclip evaluation. The command prints an
# auto-generated HMAC secret; store it in PAPERCLIP_WEBHOOK_SECRET locally.
hermes webhook subscribe paperclip-local \
  --description "Local Paperclip smoke test" \
  --events paperclip.routine,paperclip.issue \
  --prompt "Paperclip event {event_type}: {__raw__}" \
  --deliver log

# 3. Start the gateway in a separate terminal.
hermes gateway run

# 4. From Paperclip or curl, POST JSON to /webhooks/paperclip-local with
# X-Webhook-Signature set to the HMAC-SHA256 hex digest of the request body.
```

For a local `curl` smoke test, set the secret in your shell without printing it, then sign the exact JSON bytes you send:

```sh
# Use the secret printed by `hermes webhook subscribe`; do not commit it.
export PAPERCLIP_WEBHOOK_SECRET="replace-with-local-webhook-secret"

payload='{"event_type":"paperclip.routine","title":"Local Paperclip smoke test","body":"Verify Hermes receives this event."}'

sig=$(PAYLOAD="$payload" python - <<'PY'
import hashlib
import hmac
import os

payload = os.environ["PAYLOAD"].encode()
secret = os.environ["PAPERCLIP_WEBHOOK_SECRET"].encode()
print(hmac.new(secret, payload, hashlib.sha256).hexdigest())
PY
)

curl -sS -X POST "http://localhost:8644/webhooks/paperclip-local" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: ${sig}" \
  -H "X-Request-ID: paperclip-local-smoke-001" \
  --data "$payload"
```

A successful agent-mode route returns `202 Accepted` with a JSON body similar to:

```json
{"status":"accepted","route":"paperclip-local","event":"paperclip.routine","delivery_id":"paperclip-local-smoke-001"}
```

If you prefer a small script, keep the payload and secret in local environment variables or an untracked `.env` file and never paste real secrets into docs, issues, or PR comments.

## Configuration and secrets

Use local environment variables only for the evaluation:

```sh
PAPERCLIP_API_BASE=http://localhost:3100
PAPERCLIP_COMPANY_ID=
PAPERCLIP_WEBHOOK_SECRET=
PAPERCLIP_TELEMETRY_DISABLED=1
```

`PAPERCLIP_API_KEY` is not needed for the one-way webhook smoke test. Only set it if you are separately testing direct Paperclip API reads, and keep it in an untracked local `.env` file or your shell session. Never commit it.

Paperclip agent runs can receive secrets, and local Paperclip plugins are trusted code. Do not pass Hermes credentials, GitHub tokens, Slack tokens, production API keys, or private repository mounts into a Paperclip smoke test.

## Safety rules

- Use loopback (`localhost` / `127.0.0.1`) for unauthenticated or early testing.
- Prefer a signed HMAC webhook route for any non-loopback test.
- Use a disposable Paperclip company, project, and workspace.
- Do not mount private repositories during the smoke test.
- Do not pass internal API keys, GitHub tokens, Slack tokens, or Hermes credentials to Paperclip.
- Do not run untrusted PR code through Paperclip with Hermes credentials available.
- Keep the Hermes route delivery set to `log` for the first smoke test unless you have intentionally configured another destination.
- Treat every webhook payload as untrusted prompt input.

## Acceptance criteria for the smoke test

- A valid signed POST returns HTTP `202` from the Hermes webhook route.
- An invalid or missing signature returns HTTP `401`.
- A duplicate delivery ID, such as a repeated `X-Request-ID`, returns `status=duplicate` and does not trigger another run.
- Gateway logs show one accepted event and do not print secrets.
- No production Slack, Kanban, CI, PR-review, or deployment state changes occur.

## Rollback

Remove the dynamic webhook route:

```sh
hermes webhook remove paperclip-local
```

Then stop any local Hermes gateway or Paperclip processes started only for the evaluation, and delete any disposable local Paperclip data directory.

Because this workflow is docs-only and uses dynamic local configuration, reverting the docs PR is enough to roll back the repository change. There are no database migrations, default config changes, services, or runtime cleanup steps in Hermes.

## Follow-ups

Consider these only after the local smoke-test workflow has been reviewed:

- Validate whether Paperclip's documented `hermes_local` adapter is available and stable in a separate sandbox task.
- Explore one-way artifact export from Paperclip issue documents into Hermes or Slack-ready markdown.
- Consider a private Paperclip plugin only after security review of plugin trust boundaries, secret exposure, and task ownership.
- Compare a Paperclip routine with an equivalent Hermes cron job before adding another recurring-work control plane.
