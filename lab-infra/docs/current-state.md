# Current State — lab-infra

**Last Updated:** 2026-04-16 (PAB-255 audit, PAB-29 blocker audit, PAB-250, PAB-242, PAB-243, PAB-231)
**VPS:** jax-mind — 46.224.210.100 — Ubuntu 24.04 LTS
**Domain:** jaxmind.xyz (Cloudflare proxy → VPS)
**Tailscale:** jax-mind at 100.94.51.44

---

## ✅ What Works

### Infrastructure
- **VPS** — Ubuntu 24.04 LTS, Docker + Docker Compose installed and running
- **Ansible bootstrap** — completed; roles for docker, traefik, woodpecker, netdata, uptime-kuma all exist in `ansible/roles/`
- **Traefik** — deployed, listening on port 80, routing all services by hostname via Docker labels
- **GitOps** — Woodpecker CI deployed and listening for GitHub webhooks

### Deployed Services & URLs

| Service | URL | Notes |
|---|---|---|
| **Traefik** | internal (port 80) | Reverse proxy for all stacks |
| **Woodpecker CI** | https://woodpecker.jaxmind.xyz | GitOps pipeline — push to main = deploy |
| **Homepage** | https://home.jaxmind.xyz | Dashboard / home page |
| **Uptime Kuma** | https://status.jaxmind.xyz | 6 endpoints monitored, Discord alerts active |
| **VictoriaMetrics** | internal | Metrics storage (part of monitoring stack) |
| **Loki** | internal | Log aggregation |
| **Promtail** | internal | Log shipper |
| **Alertmanager** | internal | Alert routing |
| **vmalert** | internal | VictoriaMetrics alert-rule evaluation |
| **docker-stats-exporter** | internal | Container metrics |
| **CouchDB** | internal | Obsidian LiveSync backend |
| **Jax Control Plane** | https://control.jaxmind.xyz | Internal app stack; source-of-truth deploy config now lives in `lab-infra/stacks/jax-control-plane` |

### Health
- Docker healthchecks configured on all monitored services
- VictoriaMetrics, Loki, Promtail, Alertmanager, node-exporter, docker-stats-exporter, vmalert, and CouchDB all show `(healthy)` in `docker compose ps`
- Woodpecker's canonical public route is `https://woodpecker.jaxmind.xyz`; the old `https://ci.jaxmind.xyz` docs path has been retired after re-checking the live Traefik route and OAuth callback base
- The `jax-control-plane` shared deploy path is now live: the first merged-baseline cutover recreated `/lab/deploy-checkouts/jax-control-plane-main` as a clean `origin/main` checkout, rebuilt the stack successfully, and keeps the `/lab:/lab:ro` mount plus dirty-checkout hard-fail guard in place for future deploys
- **vmalert remote write now targets the VictoriaMetrics base URL** (PAB-250): the source-of-truth monitoring compose uses `--remoteWrite.url=http://victoriametrics:8428` so vmalert does not generate `/api/v1/write/api/v1/write` requests after deploy; confirm by watching `docker logs vmalert` stay free of the prior 400 spam

### Secrets
- **AGE_PRIVATE_KEY** — registered as global secret in Woodpecker via direct SQLite injection (PAB-28)
  - Pipeline can now decrypt SOPS `.env.enc` files during deploy
  - `.woodpecker.yml` updated to declare the secret for pipeline injection
  - Live host audit on 2026-04-16 confirmed the secret still exists in the Woodpecker DB and the Woodpecker container env already contains the GitHub OAuth client/secret, so the remaining `PAB-29` gap is not missing OAuth/AGE setup

### Backups
- **Local Restic backup healthy again** (PAB-242)
  - Repaired root-owned snapshot/index/data objects that were blocking reads inside `/mnt/data/backups/restic`
  - Updated `/lab/scripts/backup.sh` so the Docker-volume restic helper runs as container root for readable volume data, then chowns the local repo back to `pablo` before later phases / future cron runs
  - Cleared a stale repository lock and manually re-ran the full backup successfully on 2026-04-16: stack-configs snapshot `620f2884`, docker-volumes snapshot `6c2fe38f`, prune completed, `restic check --read-data-subset=1%` returned clean
- **Offsite backup direction is Cloudflare R2, not Backblaze B2** (PAB-255)
  - The narrowest compatible implementation is to keep using `/lab/scripts/backup.sh` unchanged and point `RESTIC_REPOSITORY` at R2 via restic's existing `s3:` backend (`s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>/restic`)
  - Required credentials are the R2 S3-style access key pair (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`); use `-o s3.region=auto` and path-style lookup if the endpoint needs it
  - The remaining B2-specific references are outside this repo in `/lab/scripts/backup.sh`, `/lab/scripts/restic-backup.conf.template`, and `/lab/scripts/setup-restic-b2.sh`

---

## 🔧 What's Broken / Pending (Needs Pablo)

### 1. DNS A Record — `jaxmind.xyz` → `46.224.210.100`
- **Status:** Not yet updated in Cloudflare
- **Impact:** `jaxmind.xyz` apex domain may not resolve correctly to the VPS
- **Action:** Log into Cloudflare → DNS → update/add A record: `jaxmind.xyz` → `46.224.210.100`

### 2. Woodpecker end-to-end GitOps verification (`PAB-29`)
- **Status:** Not executable truthfully yet; OAuth env and AGE secret are present, but the deploy step image is missing `git`
- **Evidence:**
  - `docker inspect woodpecker-server` shows GitHub OAuth enabled on the live server and both GitHub client credentials present in the container env
  - Live Woodpecker DB contains a global `AGE_PRIVATE_KEY` secret entry
  - Recent Woodpecker pipeline logs for `pablots99/lab-infra` show `/bin/sh: git: not found` inside the `deploy-changed-stacks` step, followed by `No stack changes detected, skipping deploy`
- **Impact:** A new `main` push would not provide a trustworthy end-to-end verification signal because the pipeline currently false-negatives on changed stacks instead of running `deploy-stack.sh`
- **Action:**
  1. Update `.woodpecker.yml` so the deploy step has `git` available before evaluating `git diff` (either install it explicitly or use a base image that already includes it)
  2. Push a trivial `stacks/jax-control-plane/` change through `origin/main`
  3. Confirm Woodpecker triggers, refreshes `/lab/deploy-checkouts/jax-control-plane-main`, and runs the shared deploy path cleanly with SOPS decryption active
  4. Mark GitOps fully verified in repo continuity docs once the run succeeds

### 3. Offsite Restic backup (`PAB-255`)
- **Status:** R2 direction is clear, but the bucket/token do not exist yet
- **Impact:** Offsite backup remains blocked on Cloudflare-side provisioning, while local restic backups remain healthy
- **Action:**
  1. Pablo creates a private Cloudflare R2 bucket plus an API token/access key pair scoped to that bucket
  2. Jax writes `/etc/default/restic-backup` for the R2 S3 endpoint (`RESTIC_REPOSITORY=s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>/restic`)
  3. Jax exports `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, runs an initial `restic init` if needed, then validates a stack-config snapshot before scheduling ongoing offsite runs

---

## 📋 Next Steps

1. **Pablo** — Fix DNS A record (Cloudflare)
2. **Jax** — Fix the Woodpecker deploy-step `git` prerequisite, then rerun the end-to-end GitOps validation for `PAB-29`
3. **Pablo** — Create the Cloudflare R2 bucket + API token/access key for offsite restic backup
4. **Jax** — Once R2 credentials exist, wire `/etc/default/restic-backup` to R2 and run an initial validation snapshot
5. **Jax** — Keep `/lab/deploy-checkouts/jax-control-plane-main` disposable/clean; if it drifts, recreate it instead of building from a dirty checkout
6. **Decision** — Netdata is not currently deployed on the VPS (`docker ps` shows no Netdata container). Treat `stacks/netdata/` as historical repo scaffolding unless we intentionally bring it back

---

## Stacks Directory

All stacks live under `/lab/infra/stacks/` (repo) and are deployed to `/lab/stacks/` on the VPS:

```
stacks/
├── traefik/          ✅ deployed
├── woodpecker/       ✅ deployed (OAuth + AGE present; deploy-step image still needs `git` before truthful end-to-end verification)
├── homepage/         ✅ deployed
├── monitoring/       ✅ deployed (VictoriaMetrics, Loki, Promtail, Alertmanager)
├── obsidian-sync/    ✅ deployed (CouchDB)
├── uptime-kuma/      ✅ deployed
├── jax-control-plane/ ✅ source-of-truth stack added and first shared-toolchain cutover completed; live rebuilds now come from clean `/lab/deploy-checkouts/jax-control-plane-main` snapshots
└── netdata/          💤 stack files still exist in-repo, but no Netdata container is running on the live host
```
