# Stack: Woodpecker CI (GitOps)

**Images:** `woodpeckerci/woodpecker-server:v2.7.0`, `woodpeckerci/woodpecker-agent:v2.7.0`
**URL:** [woodpecker.jaxmind.xyz](https://woodpecker.jaxmind.xyz)
**Networks:** `proxy`, `monitoring`

---

## Purpose

Woodpecker CI handles GitOps for this repo — every push to `main` on GitHub triggers a deploy of changed stacks. It replaces a manual SSH + rsync workflow.

## Architecture

Two containers work together:
- **woodpecker-server** — web UI, webhook receiver, build scheduler
- **woodpecker-agent** — executes pipeline steps; has Docker socket access to run containers/compose on the host

The agent connects to the server on the internal gRPC port (9000). The server has no direct access to the VPS filesystem or Docker — only the agent does.

## Why Woodpecker?

- Lightweight, self-hosted CI — no external dependencies
- GitHub OAuth integration (triggers on push/PR webhooks)
- Agent architecture isolates execution from the server
- Native Docker backend — agent runs pipeline steps as Docker containers

## Config Choices

| Parameter | Value | Reason |
|---|---|---|
| `WOODPECKER_OPEN=false` | Closed registration | Only admin can add repos/users |
| `WOODPECKER_DATABASE_DRIVER=sqlite3` | SQLite | Simple, no external DB needed for this scale |
| `WOODPECKER_MAX_WORKFLOWS=4` | Concurrency limit | VPS has 4 vCPUs; prevents overload |
| `WOODPECKER_BACKEND=docker` | Docker execution | Agent runs pipeline steps as containers |
| Agent volume: `/var/run/docker.sock` | Docker socket | Agent needs Docker access to run `compose` commands |
| Agent volume: `/lab:/lab` | VPS lab path | Agent can write to `/lab/stacks/` and run deploy scripts |

## The Deploy Pipeline

Defined in `.woodpecker.yml` at repo root:

```yaml
steps:
  - name: deploy-changed-stacks
    image: alpine:3.20
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /lab:/lab
    commands:
      - CHANGED=$(git diff --name-only HEAD~1 HEAD | grep '^stacks/' | cut -d'/' -f2 | sort -u)
      - for STACK in $CHANGED; do bash /lab/infra/scripts/deploy-stack.sh "$STACK"; done
```

The pipeline detects exactly which stacks changed (by looking at which `stacks/<name>/` paths appear in the diff) and deploys only those.

## Secrets

| Env var | What it is |
|---|---|
| `WOODPECKER_GITHUB_CLIENT` | GitHub OAuth App client ID |
| `WOODPECKER_GITHUB_SECRET` | GitHub OAuth App client secret |
| `WOODPECKER_AGENT_SECRET` | Shared secret for server↔agent gRPC auth |
| `WOODPECKER_ADMIN` | GitHub username(s) granted admin access |
| `WOODPECKER_PROMETHEUS_AUTH_TOKEN` | Bearer token for Prometheus metrics scrape |

## Setup: GitHub OAuth App

Required for Woodpecker to authenticate with GitHub webhooks:
1. GitHub → Settings → Developer Settings → OAuth Apps → New
2. Homepage URL: `https://woodpecker.jaxmind.xyz`
3. Callback URL: `https://woodpecker.jaxmind.xyz/authorize`
4. Copy Client ID and Secret into `.env`

> Live-host note (2026-04-16): the running Woodpecker server already has `WOODPECKER_GITHUB_CLIENT` and `WOODPECKER_GITHUB_SECRET` populated, so the current blocker for `PAB-29` is not missing OAuth env.

## Known Gaps

- `AGE_PRIVATE_KEY` is already configured as a global Woodpecker secret and `.woodpecker.yml` consumes it, so SOPS/AGE setup should no longer be treated as the blocker for `PAB-29`.
- The live `deploy-changed-stacks` step is currently not truthful for end-to-end verification because it runs in `alpine:3.20` without `git`; recent step logs show `/bin/sh: git: not found`, after which the `CHANGED=$(git diff ...)` detection falls through to `No stack changes detected, skipping deploy`.
- Before rerunning `PAB-29`, update the step image/bootstrap so `git` is installed, then push a trivial `stacks/jax-control-plane/` change and verify Woodpecker refreshes `/lab/deploy-checkouts/jax-control-plane-main` and executes `deploy-stack.sh jax-control-plane`.
