# AGENTS.md — lab-infra

> READ THIS FIRST before touching anything in this repo.
> Update at the end of every session.

**Last Updated:** 2026-04-16 (updated by Jax — PAB-255 R2 path + PAB-29 GitOps blocker audit)
**Owner:** Pablo Torres (@pablots99)
**VPS:** jax-mind — 46.224.210.100 — Ubuntu 24.04 LTS
**Domain:** jaxmind.xyz (Cloudflare proxy → VPS)
**Tailscale:** jax-mind at 100.94.51.44

---

## What This Repo Is

Infrastructure as Code for Pablo's VPS lab at `jaxmind.xyz`.
All services run as Docker Compose stacks behind Traefik.
Woodpecker CI handles GitOps — push to main = deploy.

---

## Repo Structure

```
lab-infra/
├── AGENTS.md                  ← you are here
├── README.md
├── ansible/
│   ├── playbook.yml           ← full machine bootstrap (run once)
│   ├── inventory.ini          ← target hosts
│   ├── group_vars/
│   │   └── all.yml            ← shared vars (domain, paths, etc.)
│   └── roles/
│       ├── docker/            ← install Docker + Compose
│       ├── traefik/           ← deploy Traefik stack
│       ├── woodpecker/        ← deploy Woodpecker CI
│       ├── netdata/           ← deploy Netdata
│       └── uptime-kuma/       ← deploy Uptime Kuma
├── stacks/
│   ├── traefik/
│   │   ├── docker-compose.yml
│   │   └── traefik.yml        ← static config
│   ├── woodpecker/
│   │   └── docker-compose.yml
│   ├── netdata/
│   │   └── docker-compose.yml
│   └── uptime-kuma/
│       └── docker-compose.yml
└── scripts/
    └── deploy-stack.sh        ← manually deploy/update a stack
```

---

## Architecture

- **Cloudflare** terminates SSL, proxies HTTP to VPS port 80
- **Traefik** runs on port 80, routes by hostname to containers
- **All services** on the `proxy` Docker network — Traefik discovers them via labels
- **Woodpecker** listens to GitHub webhooks, SSHes into VPS to run deploy steps
- **Secrets** never in repo — always in `.env` files on the VPS at `/lab/stacks/<service>/.env`

## Networking

```
Internet → Cloudflare (SSL) → VPS:80 → Traefik → containers
Tailscale → VPS:100.94.51.44 → direct access
```

---

## Current State (2026-04-16)

**✅ Working:**
- VPS provisioned, Docker running
- /lab/infra repo scaffolded
- Traefik deployed and routing all services
- Woodpecker CI deployed (GitOps active)
- Homepage deployed at https://home.jaxmind.xyz
- Monitoring stack (VictoriaMetrics, Loki, Promtail, Alertmanager, vmalert) deployed
- **Docker healthchecks now cover all monitored services** — VictoriaMetrics, Loki, Promtail, Alertmanager, node-exporter, docker-stats-exporter, vmalert, and CouchDB all show `(healthy)` in `docker compose ps`
- **Uptime Kuma deployed at https://status.jaxmind.xyz — all 6 endpoints monitored, Discord alerts active**
- **vmalert deployed — 7 alert rules active: HostDown, HighCPU, HighMemory, DiskFull, DiskCritical, ContainerDown, LokiDown — wired to Alertmanager → Discord** (PAB-7)
- **Monitoring repo config now uses the correct vmalert remote-write base URL** (PAB-250): `--remoteWrite.url=http://victoriametrics:8428` so vmalert no longer appends `/api/v1/write` twice at runtime; after deploy, verify the old `/api/v1/write/api/v1/write` 400 log spam stays gone
- **Homepage dashboard updated — Monitoring section now shows VictoriaMetrics, Loki, Alertmanager, CouchDB, Node Exporter, Docker Stats** (PAB-12)
- **Restic backup repaired and healthy again** (PAB-242) — fixed root-owned objects inside `/mnt/data/backups/restic`, updated `/lab/scripts/backup.sh` so Docker-volume backups run as container root but chown the local repo back to `pablo`, cleared a stale restic lock, and manually re-ran the backup successfully end-to-end (`stack-configs` snapshot `620f2884`, `docker-volumes` snapshot `6c2fe38f`, prune + `restic check` clean)
- **Woodpecker OAuth env is already populated on the VPS** — `docker inspect woodpecker-server` shows the live server is configured for GitHub OAuth at `https://woodpecker.jaxmind.xyz` with closed registration enabled and both GitHub client credentials present, so the old “Pablo still needs to create the OAuth app / populate .env” note is no longer accurate
- **SOPS decrypt is already wired into the live deploy pipeline** (PAB-6 / PAB-28) — the live Woodpecker DB contains a global `AGE_PRIVATE_KEY` secret entry and `.woodpecker.yml` declares it for injection
- **The remaining `PAB-29` blocker is now the pipeline step image, not OAuth/AGE setup** — Woodpecker can receive pushes, but the `deploy-changed-stacks` step currently runs in `alpine:3.20` without `git`; recent pipeline logs show `/bin/sh: git: not found`, after which the `CHANGED=$(git diff ...)` command substitution collapses to empty and the workflow incorrectly prints `No stack changes detected, skipping deploy`
- **Woodpecker canonical public hostname is `https://woodpecker.jaxmind.xyz`** (PAB-243): repo routing already served `woodpecker.jaxmind.xyz` while some continuity/recovery docs still pointed at `https://ci.jaxmind.xyz`; docs now consistently use the live hostname and GitHub OAuth callback base.
- **Jax Control Plane now runs through the shared deploy path** (PAB-177/PAB-228/PAB-229/PAB-231): the onboarding branch landed on `origin/main`, `/lab/deploy-checkouts/jax-control-plane-main` was recreated as a clean mainline checkout at `30d6064`, and the first shared `deploy-stack.sh jax-control-plane` cutover rebuilt the live container successfully with the required `/lab:/lab:ro` runtime mount parity and deploy-checkout hygiene guard in place.

**🔧 In Progress / Needs Pablo:**
- DNS A record update (jaxmind.xyz → 46.224.210.100) — needs Pablo to update Cloudflare
- **Restic offsite backup** — local backup works, and the narrowest offsite path is now Cloudflare R2 via restic's existing `s3:` backend support (`RESTIC_REPOSITORY=s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>/restic` plus `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `-o s3.region=auto` / path-style lookup if needed). Pablo still needs to create the R2 bucket + API token before Jax can wire/test it.

---

## What to Do Next

1. **Pablo** — Update DNS A record in Cloudflare: `jaxmind.xyz` → `46.224.210.100`
2. **Jax** — For `PAB-29`, fix the Woodpecker step image or bootstrap so `git` is available inside `deploy-changed-stacks`, then rerun the end-to-end validation with a trivial `stacks/jax-control-plane/` push and confirm `/lab/deploy-checkouts/jax-control-plane-main` refreshes before rebuild
3. **Pablo** — Create the Cloudflare R2 bucket + API token for offsite restic backup
4. **Jax** — Once R2 credentials exist, wire `/etc/default/restic-backup` to the R2 S3 endpoint and run a stack-config-only validation snapshot before scheduling it
5. **Jax** — Keep the deploy-checkout contract intact: `/lab/deploy-checkouts/jax-control-plane-main` should remain disposable and clean; if it drifts, recreate it instead of building from a dirty tree
6. **Jax** — Confirm the monitoring stack stays quiet after the PAB-250 deploy: `docker logs vmalert` should no longer emit `/api/v1/write/api/v1/write` 400s
7. Treat Netdata as historical repo scaffolding only unless we intentionally redeploy it later — it is not part of the current live host baseline (`docker ps` shows no Netdata container)

---

## Hard Rules — Do NOT

- ❌ Never commit `.env` files or secrets to this repo
- ❌ Never run `docker compose down` on traefik without a plan — it takes everything offline
- ❌ Never bypass Traefik by exposing container ports directly (except Traefik itself on 80)
- ❌ Never touch stacks manually if Woodpecker is handling them — use git push

---

## Open Questions — Needs Pablo

- [ ] Cloudflare API token for Traefik? (needed if we want Let's Encrypt DNS challenge instead of Cloudflare edge SSL)
- [ ] DNS A record pointed to 46.224.210.100?
