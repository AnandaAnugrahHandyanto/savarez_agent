---
sidebar_position: 16
title: "Linear"
description: "Connect Hermes Agent to Linear for @mention-driven issue management"
---

# Linear

Connect Hermes to [Linear](https://linear.app), the project management tool for modern software teams. The adapter receives Linear webhooks when you @mention the agent in issue comments, and responds directly on the issue.

## Overview

| Component | Value |
|-----------|-------|
| **Connection** | Webhook (HTTP POST from Linear to your server) |
| **Auth** | HMAC-SHA256 signature verification + IP allowlist |
| **Trigger** | @mention the agent in an issue comment |
| **Response** | Agent posts a comment back on the same issue |
| **Port** | 8645 (configurable) |
| **HTTPS required** | Yes — Linear only sends webhooks to HTTPS endpoints |

---

## Prerequisites

- A Linear workspace with **admin access** (needed to create webhooks)
- A Linear API key ([Settings → Account → Security](https://linear.app/settings/account/security))
- A publicly accessible HTTPS endpoint (your server, behind a reverse proxy)
- The `linear` CLI tool (optional, for enriched channel directory)

---

## Setup

### 1. Configure Hermes

Run the interactive setup:

```bash
hermes gateway setup
# Select "Linear" from the platform list
```

Or manually add to `~/.hermes/.env`:

```bash
# Required
LINEAR_API_KEY=lin_api_...               # Personal API key
LINEAR_WEBHOOK_SECRET=your-secret-here   # HMAC signing secret (you choose this)

# Optional
LINEAR_AGENT_USER_ID=uuid-of-agent-user  # For @mention detection via ProseMirror
LINEAR_TEAM_IDS=AI,ENG                   # Filter to specific teams (empty = all)
LINEAR_WEBHOOK_PORT=8645                 # Webhook listener port (default: 8645)
LINEAR_ENFORCE_IP_ALLOWLIST=true         # Verify source IPs (default: true)
```

Generate a strong webhook secret:

```bash
openssl rand -hex 32
```

### 2. Set Up HTTPS

Linear requires HTTPS for webhook delivery. If your server doesn't have TLS, set up a reverse proxy:

**Caddy** (auto-provisions Let's Encrypt certs):
```
your-domain.com {
    reverse_proxy /hooks/linear localhost:8645
    reverse_proxy /health localhost:8645
}
```

**Nginx**:
```nginx
location /hooks/linear {
    proxy_pass http://localhost:8645;
    proxy_set_header X-Forwarded-For $remote_addr;
}
```

**Tailscale Funnel** (zero-config option):
```bash
tailscale funnel --bg 8645
```

### 3. Create a Linear Webhook

1. Open Linear → **Settings** (gear icon) → **API** (under Workspace)
2. Click **Webhooks** → **New webhook**
3. Configure:
   - **Label**: Hermes Agent
   - **URL**: `https://your-domain.com/hooks/linear`
   - **Secret**: paste the same secret you set as `LINEAR_WEBHOOK_SECRET`
   - **Resource types**: select **Issues** and **Comments**
4. Click **Create webhook**

:::tip
If you don't see the **API** section, you may not have workspace admin access. Ask a workspace admin to create the webhook for you.
:::

### 4. Find Your Agent User ID (Optional)

To enable @mention detection via Linear's ProseMirror data (more reliable than text matching), find the Linear user ID that represents the agent:

```bash
linear api '{ viewer { id name } }'
```

Set this as `LINEAR_AGENT_USER_ID` in your `.env`. Without this, the adapter falls back to detecting `@hermes` in comment text.

### 5. Start the Gateway

```bash
hermes gateway run
```

The Linear webhook server will start on port 8645. Verify it's running:

```bash
curl -s http://localhost:8645/health
# Should return: OK
```

---

## How It Works

```
Linear Comment (@mention)
        │
        ▼
┌───────────────────┐
│   IP Allowlist     │  Only accept from Linear's IPs
│   (6 known IPs)    │  35.231.147.226, 35.243.134.228, ...
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  HMAC-SHA256       │  Verify signature with webhook secret
│  Signature Check   │  Timing-safe comparison
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Timestamp Check   │  Reject if >60s drift (replay protection)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Event Router      │  Filter by team, detect @mentions,
│                    │  skip self-comments (loop prevention)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Agent Dispatch    │  Agent sees comment + issue context,
│                    │  responds via Linear GraphQL API
└───────────────────┘
```

### Supported Events

| Event | Trigger | What the Agent Sees |
|-------|---------|---------------------|
| **Comment @mention** | Someone @mentions the agent in an issue comment | The comment text + issue identifier and title |
| **Issue assigned** | An issue is assigned to the agent's user | Issue title, priority, state, description |
| **New issue created** | A new issue is created and assigned to the agent | Full issue details |

### How the Agent Responds

The agent posts comments back on the issue via the Linear GraphQL API. It has access to the `linear` CLI tool and can:

- Look up related issues
- Update issue status, priority, or assignee
- Add labels
- Create sub-issues
- Query team members and projects

---

## Security

Three layers of protection on the webhook endpoint:

### 1. IP Allowlist

Only requests from Linear's published webhook IPs are accepted:

```
35.231.147.226
35.243.134.228
34.140.253.14
34.38.87.206
34.134.222.122
35.222.25.142
```

Supports `X-Forwarded-For` for reverse proxy setups. Disable for testing with `LINEAR_ENFORCE_IP_ALLOWLIST=false`.

:::note
Linear notes: "We may occasionally update this list to add new IP addresses." If webhooks start failing with 403, check the [Linear developer docs](https://linear.app/developers/webhooks) for updated IPs.
:::

### 2. HMAC-SHA256 Signature

Every webhook includes a `Linear-Signature` header with an HMAC-SHA256 hash of the body, signed with your webhook secret. The adapter verifies this using timing-safe comparison to prevent timing attacks.

### 3. Timestamp Validation

The `webhookTimestamp` field is checked against the current time. Webhooks with >60 second drift are rejected to prevent replay attacks.

---

## Configuration Options

### Team Filtering

Restrict the adapter to specific teams:

```bash
LINEAR_TEAM_IDS=AI,ENG
```

Use team keys (the short prefix like `AI`, not the display name like "EDA - AI"). Find your team keys with:

```bash
linear team list
```

### Self-Comment Prevention

The adapter automatically skips comments authored by the agent's own user ID (set via `LINEAR_AGENT_USER_ID`). This prevents infinite loops where the agent's response triggers another webhook.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LINEAR_API_KEY` | Yes | — | Linear personal API key for posting comments |
| `LINEAR_WEBHOOK_SECRET` | Yes | — | HMAC signing secret (must match the webhook config in Linear) |
| `LINEAR_AGENT_USER_ID` | No | — | Linear user UUID for @mention detection. Find via `linear api '{ viewer { id } }'` |
| `LINEAR_TEAM_IDS` | No | (all teams) | Comma-separated team keys to filter (e.g., `AI,ENG`) |
| `LINEAR_WEBHOOK_HOST` | No | `0.0.0.0` | Webhook server bind address |
| `LINEAR_WEBHOOK_PORT` | No | `8645` | Webhook server port |
| `LINEAR_ENFORCE_IP_ALLOWLIST` | No | `true` | Verify requests come from Linear's IPs |
| `LINEAR_HOME_CHANNEL` | No | — | Issue identifier for cron job delivery (e.g., `AI-100`) |
| `LINEAR_ALLOWED_USERS` | No | — | Comma-separated Linear user UUIDs (not needed — HMAC is the auth) |

---

## Troubleshooting

### Webhook not receiving events

1. Check the gateway is running: `hermes gateway status`
2. Verify the health endpoint: `curl https://your-domain.com/health`
3. Check Linear webhook status: Settings → API → Webhooks → your webhook should show recent deliveries
4. Check logs: `hermes gateway run -v` for verbose output

### 403 Forbidden on webhooks

The IP allowlist is rejecting the request. Either:
- Linear added new IPs — check [their docs](https://linear.app/developers/webhooks) and update the adapter
- Your reverse proxy isn't forwarding `X-Forwarded-For` — add the header in your proxy config
- Temporarily disable with `LINEAR_ENFORCE_IP_ALLOWLIST=false` to confirm

### Agent not responding to @mentions

1. Verify `LINEAR_AGENT_USER_ID` is set correctly — run `linear api '{ viewer { id name } }'`
2. Without `LINEAR_AGENT_USER_ID`, the adapter falls back to detecting `@hermes` in the comment text
3. Check team filtering — if `LINEAR_TEAM_IDS` is set, only matching teams trigger events
4. Check for self-comment loop prevention — the agent won't respond to its own comments

### Invalid signature errors

- Ensure `LINEAR_WEBHOOK_SECRET` matches exactly what you set in the Linear webhook config
- Webhooks must be verified against the raw body, not re-serialized JSON — this is handled automatically

### HTTPS / certificate issues

- Linear requires HTTPS for webhook delivery
- If using Caddy, check `sudo systemctl status caddy` for certificate provisioning errors
- CAA records on your domain may prevent Let's Encrypt — check with your IT team
