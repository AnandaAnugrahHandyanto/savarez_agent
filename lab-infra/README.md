# lab-infra

Infrastructure as Code for **jaxmind.xyz** — Pablo's self-hosted VPS lab.

All services run as Docker Compose stacks behind Traefik. GitOps via Woodpecker CI — push to `main` deploys changed stacks automatically. Secrets are encrypted at rest with SOPS + age.

> **For AI agents:** See [AGENTS.md](./AGENTS.md) for full operational context, known issues, and session handoff notes.

---

## Architecture Overview

```
Internet
   │
   ▼
Cloudflare (DNS + SSL termination)
   │  *.jaxmind.xyz → 46.224.210.100
   ▼
VPS — Ubuntu 24.04 LTS (4 CPU, 16GB RAM)
   │  port 80 (Cloudflare proxy handles SSL)
   ▼
Traefik v2.11 (reverse proxy)
   │  routes by hostname → containers on `proxy` network
   ├── home.jaxmind.xyz        → Homepage
   ├── woodpecker.jaxmind.xyz  → Woodpecker CI
   ├── traefik.jaxmind.xyz     → Traefik dashboard
   ├── vm.jaxmind.xyz          → VictoriaMetrics
   ├── loki.jaxmind.xyz        → Loki
   └── couchdb.jaxmind.xyz     → CouchDB (Obsidian sync)

Docker networks:
  proxy      — all public-facing services (Traefik discovers via labels)
  monitoring — metrics/logs pipeline (internal only)
```

**SSL:** Cloudflare terminates TLS at the edge. Traffic between Cloudflare and the VPS is plain HTTP on port 80 (Flexible mode). Traefik does not hold any certificates.

**Docker data root:** `/mnt/HC_Volume_105131034/docker` (symlinked as `/mnt/data/docker`) — all volumes live on the 50GB extra volume, not the root disk.

---

## Stack

| Service | Image | Role | URL |
|---|---|---|---|
| **Traefik** | `traefik:v2.11` | Reverse proxy, service discovery | [traefik.jaxmind.xyz](https://traefik.jaxmind.xyz) |
| **Woodpecker CI** | `woodpeckerci/woodpecker-server:v2.7.0` | GitOps CI/CD, GitHub webhooks | [woodpecker.jaxmind.xyz](https://woodpecker.jaxmind.xyz) |
| **Homepage** | `ghcr.io/gethomepage/homepage:latest` | Dashboard / service index | [home.jaxmind.xyz](https://home.jaxmind.xyz) |
| **VictoriaMetrics** | `victoriametrics/victoria-metrics:v1.101.0` | Metrics storage (Prometheus-compatible) | [vm.jaxmind.xyz](https://vm.jaxmind.xyz) |
| **Node Exporter** | `prom/node-exporter:v1.8.2` | VPS system metrics (CPU, RAM, disk, net) | internal |
| **docker-stats-exporter** | `wywywywy/docker_stats_exporter:latest` | Container metrics via Docker API | internal |
| **Loki** | `grafana/loki:3.1.0` | Log aggregation | [loki.jaxmind.xyz](https://loki.jaxmind.xyz) |
| **Promtail** | `grafana/promtail:3.1.0` | Log shipper (Docker containers + syslog) | internal |
| **Alertmanager** | `prom/alertmanager:v0.27.0` | Alert routing → Discord | internal |
| **CouchDB** | `couchdb:3.3` | Obsidian LiveSync backend | [couchdb.jaxmind.xyz](https://couchdb.jaxmind.xyz) |
| **Grafana Cloud** | _(external)_ | Dashboards UI for metrics + logs | [pablots99.grafana.net](https://pablots99.grafana.net) |

> **Traefik v2.11 note:** v3.x is intentionally avoided — Docker API negotiation breaks with the daemon version on this host.

> **docker-stats-exporter note:** cAdvisor was replaced because this host uses the `overlayfs` Docker storage driver (not `overlay2`). cAdvisor requires `layerdb/mounts` paths that don't exist with this driver. `docker-stats-exporter` uses only the Docker socket API and works correctly.

---

## Repo Layout

```
lab-infra/
├── AGENTS.md                        ← AI agent context + session notes
├── README.md                        ← you are here
├── .sops.yaml                       ← SOPS encryption rules (age key)
├── .gitignore                       ← blocks .env, allows .env.enc
├── .woodpecker.yml                  ← CI pipeline (auto-deploy on push)
├── scripts/
│   └── deploy-stack.sh              ← sync + docker compose up for a stack
└── stacks/
    ├── traefik/
    │   └── docker-compose.yml
    ├── woodpecker/
    │   └── docker-compose.yml
    ├── monitoring/
    │   ├── docker-compose.yml
    │   ├── victoriametrics/
    │   │   └── scrape.yml           ← Prometheus scrape targets
    │   ├── loki/
    │   │   └── config.yml
    │   ├── promtail/
    │   │   └── config.yml           ← Docker + syslog log scraping
    │   └── alertmanager/
    │       └── config.yml           ← Discord webhook routing
    ├── homepage/
    │   ├── docker-compose.yml
    │   └── config/                  ← Homepage YAML configs
    ├── jax-control-plane/
    │   ├── docker-compose.yml
    │   ├── .env.example
    │   └── README.md                ← Internal app stack routed through Traefik
    └── obsidian-sync/
        └── docker-compose.yml       ← CouchDB for Obsidian LiveSync
```

**Live stacks run from `/lab/stacks/`** (on the VPS). This repo is the source of truth — the deploy script syncs from here to there.

---

## Secrets Management (SOPS + age)

Secrets are never committed in plaintext. Each stack has a `.env.enc` file (SOPS-encrypted with age) alongside the compose file.

```
stacks/traefik/.env.enc        ← encrypted
stacks/woodpecker/.env.enc
stacks/monitoring/.env.enc
stacks/homepage/.env.enc
```

**Decrypt a stack's env (requires age private key):**
```bash
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt

# Decrypt to live dir
sops --decrypt stacks/monitoring/.env.enc > /lab/stacks/monitoring/.env
```

**Re-encrypt after editing:**
```bash
SOPS_AGE_RECIPIENTS=age1snttkxsjte460xkh5v6cl0u0t7umuu4q0m7za8vpgzm9yx46zdvs8sdtfz \
  sops --encrypt /lab/stacks/monitoring/.env > stacks/monitoring/.env.enc
```

**Rules** (`.sops.yaml`):
```yaml
creation_rules:
  - path_regex: stacks/.*/.env.enc$
    age: age1snttkxsjte460xkh5v6cl0u0t7umuu4q0m7za8vpgzm9yx46zdvs8sdtfz
```

> ⚠️ The age **private** key lives at `~/.config/sops/age/keys.txt` on the VPS. Back it up in a password manager — without it, all `.env.enc` files are unrecoverable.

---

## GitOps — How Deploys Work

```
git push origin main
      │
      ▼
GitHub webhook → Woodpecker CI
      │
      ▼
.woodpecker.yml detects changed stacks
(git diff HEAD~1 HEAD | grep '^stacks/')
      │
      ▼
scripts/deploy-stack.sh <stack>
  1. rsync infra/stacks/<stack>/ → /lab/stacks/<stack>/  (excludes .env)
  2. docker compose pull
  3. docker compose up -d --remove-orphans
  4. docker image prune -f
```

**Manual deploy** (when not using CI):
```bash
# On the VPS
bash /lab/infra/scripts/deploy-stack.sh monitoring
```

**Deploy all stacks:**
```bash
for stack in traefik woodpecker monitoring homepage obsidian-sync; do
  bash /lab/infra/scripts/deploy-stack.sh $stack
done
```

> ⚠️ **Known gap:** The CI pipeline doesn't yet decrypt `.env.enc` → `.env` automatically. Until [PAB-6](https://linear.app/pablot/issue/PAB-6) is resolved, `.env` files must be manually decrypted on the VPS before deploying a fresh stack.

---

## Monitoring Pipeline

```
VPS system          Container stats        Application logs
     │                    │                      │
node-exporter    docker-stats-exporter        Promtail
(port 9100)          (port 9487)            (Docker socket)
     │                    │                      │
     └──────────┬─────────┘               Loki (port 3100)
                ▼                               │
        VictoriaMetrics                         │
          (port 8428)                           │
               │                               │
               └──────────────┬────────────────┘
                               ▼
                        Grafana Cloud
                    pablots99.grafana.net
                               │
                    ┌──────────┴──────────┐
                    │                     │
              Metrics dashboards      Log explorer
```

**Grafana Cloud datasources:**
| Name | UID | Endpoint |
|---|---|---|
| Jax-Metrics | `efiwad0exm5tsf` | `https://vm.jaxmind.xyz` |
| jax-loki | `afiwd6p9kej28e` | `https://loki.jaxmind.xyz` |

**VictoriaMetrics scrape targets:**

| Job | Target | What it collects |
|---|---|---|
| `node` | `node-exporter:9100` | CPU, RAM, disk, network, filesystem |
| `docker` | `docker-stats-exporter:9487` | Per-container CPU %, RAM, net I/O, block I/O |
| `traefik` | `traefik:8082` | Request rate, latency, error rate per service |
| `woodpecker` | `woodpecker-server:9001` | Build counts, queue depth |
| `victoriametrics` | `victoriametrics:8428` | Self-metrics |

**Grafana dashboards:**
| Dashboard | UID |
|---|---|
| Node Exporter Full | `cdb74b0f-49d8-4c01-82ff-e192fc7fbb98` |
| Docker Container Metrics | `2b3fa9a7-452f-488f-969a-094548671ffa` |
| Logs / App | `ff2a1055-bb7a-424f-8f22-b7dc3cad742b` |

---

## Adding a New Stack

1. **Create the compose file** in `stacks/<name>/docker-compose.yml`
2. **Create `.env`** with required secrets, then encrypt it:
   ```bash
   SOPS_AGE_RECIPIENTS=age1snttkxsjte460xkh5v6cl0u0t7umuu4q0m7za8vpgzm9yx46zdvs8sdtfz \
     sops --encrypt stacks/<name>/.env > stacks/<name>/.env.enc
   ```
3. **Pre-create Docker networks** if needed (they're external):
   ```bash
   docker network create proxy     # if not exists
   docker network create monitoring # if not exists
   ```
4. **Add Traefik labels** to route traffic:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.<name>.rule=Host(`<name>.jaxmind.xyz`)"
     - "traefik.http.routers.<name>.entrypoints=web"
     - "traefik.http.services.<name>.loadbalancer.server.port=<PORT>"
   ```
5. **Add DNS record** in Cloudflare: `A` record `<name>.jaxmind.xyz → 46.224.210.100` (proxy ON)
6. **Commit and push** — Woodpecker deploys automatically

---

## VPS Quick Reference

| Property | Value |
|---|---|
| OS | Ubuntu 24.04 LTS |
| CPU / RAM | 4 vCPU / 16 GB |
| Root disk | 75 GB (`/`) |
| Extra volume | 50 GB (`/mnt/HC_Volume_105131034`, symlink `/mnt/data`) |
| Docker data root | `/mnt/data/docker` |
| Docker storage driver | `overlayfs` (Ubuntu default — not `overlay2`) |
| Public IP | `46.224.210.100` |
| Tailscale | `jax-mind` (100.94.51.44) |
| SSH | port 22, user `pablo` |
| Domain registrar | GoDaddy |
| DNS / CDN | Cloudflare (proxy ON, Flexible SSL) |

**Docker networks (pre-created, external):**
```bash
docker network create proxy
docker network create monitoring
```

---

## Documentation

- **[docs/architecture.md](./docs/architecture.md)** — Detailed network topology, data flows (metrics, logs, alerts), secrets flow, GitOps flow, Traefik routing internals
- **[docs/stacks/traefik.md](./docs/stacks/traefik.md)** — Traefik reverse proxy config decisions
- **[docs/stacks/woodpecker.md](./docs/stacks/woodpecker.md)** — Woodpecker CI GitOps setup + GitHub OAuth
- **[docs/stacks/monitoring.md](./docs/stacks/monitoring.md)** — VictoriaMetrics, Loki, Promtail, Alertmanager
- **[docs/stacks/homepage.md](./docs/stacks/homepage.md)** — Homepage dashboard config
- **[docs/stacks/obsidian-sync.md](./docs/stacks/obsidian-sync.md)** — CouchDB + Obsidian LiveSync

---

## Known Issues / Backlog

Tracked in [Linear — jaxmind.xyz Lab Infra](https://linear.app/pablot/project/jaxmindxyz-lab-infra-a18e3fedc322):

| # | Issue | Priority |
|---|---|---|
| PAB-5 | Fix CouchDB restart loop in obsidian-sync stack | 🔴 Urgent |
| PAB-6 | Wire SOPS decryption into Woodpecker CI deploy pipeline | 🟠 High |
| PAB-7 | Add Prometheus alerting rules for critical infra conditions | 🟠 High |
| PAB-8 | Replace obsidian-livesync-bridge with native CouchDB setup | 🟠 High |
| PAB-9 | Add VPS data backup strategy (volumes + configs) | 🟠 High |
| PAB-10 | Configure Woodpecker pipeline secrets properly | 🟡 Medium |
| PAB-11 | Add health checks to all Docker Compose services | 🟡 Medium |
| PAB-12 | Add Homepage dashboard widgets for monitoring services | 🟡 Medium |
| PAB-13 | Document disaster recovery runbook | 🟡 Medium |
| PAB-14 | Set up uptime monitoring for public endpoints | 🟡 Medium |
| PAB-15 | Add Traefik static config file and review SSL mode | 🔵 Low |
