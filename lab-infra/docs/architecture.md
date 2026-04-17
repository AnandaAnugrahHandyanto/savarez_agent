# Architecture — jaxmind.xyz Lab Infra

Detailed technical reference for the infrastructure behind `jaxmind.xyz`.

---

## Network Topology

```
┌──────────────────────────────────────────────────────────────┐
│  Internet                                                      │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS (TLS terminated here)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Cloudflare                                                    │
│  ├─ DNS: *.jaxmind.xyz → 46.224.210.100 (A record, proxy ON)  │
│  ├─ SSL: Flexible mode — terminates TLS, sends HTTP to VPS     │
│  └─ DDoS protection + WAF                                      │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP on port 80
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  VPS — jax-mind (46.224.210.100)                               │
│  Ubuntu 24.04 LTS | 4 vCPU | 16 GB RAM                        │
│  Root disk: 75 GB (/)                                          │
│  Data volume: 50 GB (/mnt/data/docker — Docker volumes)        │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Traefik v2.11 (container, port 80 → host port 80)        │ │
│  │  ├─ home.jaxmind.xyz    → homepage:3000                  │ │
│  │  ├─ woodpecker.jaxmind.xyz → woodpecker-server:8000      │ │
│  │  ├─ traefik.jaxmind.xyz → api@internal (dashboard)       │ │
│  │  ├─ vm.jaxmind.xyz      → victoriametrics:8428           │ │
│  │  ├─ loki.jaxmind.xyz    → loki:3100                      │ │
│  │  └─ couchdb.jaxmind.xyz → couchdb:5984                   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Docker Networks:                                              │
│  ┌─────────────────────┐  ┌────────────────────────────────┐  │
│  │  proxy (bridge)     │  │  monitoring (bridge)           │  │
│  │  ├─ traefik         │  │  ├─ victoriametrics             │  │
│  │  ├─ homepage        │  │  ├─ node-exporter               │  │
│  │  ├─ woodpecker      │  │  ├─ docker-stats-exporter       │  │
│  │  ├─ victoriametrics │  │  ├─ loki                        │  │
│  │  ├─ loki            │  │  ├─ promtail                    │  │
│  │  └─ couchdb         │  │  ├─ alertmanager                │  │
│  └─────────────────────┘  │  └─ woodpecker (metrics only)  │  │
│                            └────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Tailscale:** VPS also reachable at `100.94.51.44` on `jax-mind` mesh node for direct, VPN-authenticated access (no Cloudflare, no Traefik).

---

## Data Flow: Metrics → VictoriaMetrics → Grafana Cloud

```
┌─────────────────────────────────────────────────────────────┐
│ Metric Sources (all internal to monitoring network)          │
│                                                              │
│  node-exporter (port 9100)    — VPS system: CPU/RAM/disk/net │
│  docker-stats-exporter (9487) — Container CPU/RAM/net/IO     │
│  traefik (port 8082)          — HTTP req rate/latency/errors │
│  woodpecker-server (port 9001)— CI build counts/queue depth  │
│  victoriametrics (port 8428)  — Self-metrics                 │
└────────────────────┬────────────────────────────────────────┘
                     │ Prometheus scrape (15s interval)
                     │ config: stacks/monitoring/victoriametrics/scrape.yml
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ VictoriaMetrics (port 8428)                                   │
│  - Stores metrics for 90 days (--retentionPeriod=90d)         │
│  - Compatible with Prometheus remote_read/write API           │
│  - Also accessible at https://vm.jaxmind.xyz (basic auth)    │
└────────────────────┬────────────────────────────────────────┘
                     │ Grafana Cloud datasource (remote_read)
                     │ UID: efiwad0exm5tsf
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Grafana Cloud — pablots99.grafana.net                         │
│  Dashboards:                                                  │
│  - Node Exporter Full (cdb74b0f-...)                          │
│  - Docker Container Metrics (2b3fa9a7-...)                    │
│  - Logs / App (ff2a1055-...)                                  │
└─────────────────────────────────────────────────────────────┘
```

**Why VictoriaMetrics instead of Prometheus?** Drop-in replacement, lower memory footprint, better long-term storage with built-in downsampling.

**Why docker-stats-exporter instead of cAdvisor?** This host uses the `overlayfs` Docker storage driver (Ubuntu default). cAdvisor requires `layerdb/mounts` paths that only exist under `overlay2`. `docker-stats-exporter` uses only the Docker socket API and works correctly.

---

## Data Flow: Logs → Promtail → Loki → Grafana Cloud

```
┌─────────────────────────────────────────────────────────────┐
│ Log Sources                                                   │
│                                                              │
│  /var/log/*           — System logs (syslog, auth, etc.)     │
│  Docker JSON driver   — All container stdout/stderr          │
│  (mounted via /var/lib/docker/containers)                    │
└────────────────────┬────────────────────────────────────────┘
                     │ tail + label enrichment
                     │ config: stacks/monitoring/promtail/config.yml
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Promtail                                                      │
│  - Discovers Docker containers via Docker socket              │
│  - Automatically labels logs with: container_name, image,    │
│    compose_project, compose_service                           │
│  - Tails system logs from /var/log                            │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP push to Loki (port 3100)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Loki (port 3100)                                              │
│  - Log aggregation, index-free, stored on /mnt/data volume   │
│  - Query via LogQL                                            │
│  - Accessible at https://loki.jaxmind.xyz (basic auth)       │
└────────────────────┬────────────────────────────────────────┘
                     │ Grafana Cloud datasource (HTTP)
                     │ UID: afiwd6p9kej28e
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Grafana Cloud — Log Explorer + Logs / App dashboard           │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Alerts → Alertmanager → Discord

```
┌────────────────────────────────────────────┐
│ VictoriaMetrics (evaluates alert rules)     │
│  config: stacks/monitoring/alertmanager/    │
└──────────────────┬─────────────────────────┘
                   │ POST alert to Alertmanager (port 9093)
                   ▼
┌────────────────────────────────────────────┐
│ Alertmanager                                │
│  config: stacks/monitoring/alertmanager/   │
│          config.yml                         │
│  - Groups + deduplicates alerts             │
│  - Routes → Discord webhook                 │
└──────────────────┬─────────────────────────┘
                   │ Discord webhook POST
                   ▼
┌────────────────────────────────────────────┐
│ Discord #alerts channel                     │
└────────────────────────────────────────────┘
```

---

## Secrets Flow: SOPS + age

```
┌────────────────────────────────────────────────────────────┐
│ Developer (local machine)                                    │
│                                                              │
│  1. Create plaintext .env with secrets                       │
│     e.g. TRAEFIK_DASHBOARD_AUTH=htpasswd_hash                │
│                                                              │
│  2. Encrypt with age public key:                             │
│     SOPS_AGE_RECIPIENTS=age1snttkxsj... \                    │
│       sops --encrypt stacks/<name>/.env \                    │
│         > stacks/<name>/.env.enc                             │
│                                                              │
│  3. Commit .env.enc to git (safe — encrypted)                │
│     .gitignore blocks .env files                             │
└───────────────────────────┬────────────────────────────────┘
                            │ git push → Woodpecker CI
                            ▼
┌────────────────────────────────────────────────────────────┐
│ VPS                                                          │
│                                                              │
│  Age private key at:                                         │
│  ~/.config/sops/age/keys.txt                                 │
│  (backed up in password manager — NEVER in repo)             │
│                                                              │
│  Decrypt before first deploy of a stack:                     │
│  export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt        │
│  sops --decrypt stacks/<name>/.env.enc \                     │
│    > /lab/stacks/<name>/.env                                 │
│                                                              │
│  deploy-stack.sh rsync EXCLUDES .env — secrets stay on VPS   │
└────────────────────────────────────────────────────────────┘
```

**Encryption algorithm:** X25519 (age) — each `.env.enc` is only decryptable with the private key on the VPS.

**Key:** `age1snttkxsjte460xkh5v6cl0u0t7umuu4q0m7za8vpgzm9yx46zdvs8sdtfz` (public key, safe to store in `.sops.yaml`)

---

## Storage Layout

```
VPS Disk Layout:
/                                  — 75 GB root disk
  /lab/
    stacks/                         — live stack configs (+ .env files)
      traefik/
      woodpecker/
      monitoring/
      homepage/
      obsidian-sync/
    infra/                          — git clone of this repo
    obsidian_vault/                 — Obsidian vault (synced via CouchDB)

/mnt/HC_Volume_105131034/           — 50 GB extra volume
  docker/                           — Docker data root (volumes)

/mnt/data → /mnt/HC_Volume_105131034  — symlink
```

**All Docker named volumes** (vm_data, loki_data, couchdb_data, etc.) live under `/mnt/data/docker/volumes/` — not on the root disk.

---

## GitOps Flow

```
Developer workstation
  │
  │ git push origin main
  ▼
GitHub (pablots99/lab-infra)
  │
  │ webhook (push event)
  ▼
Woodpecker CI (woodpecker.jaxmind.xyz)
  │
  │ .woodpecker.yml runs deploy-changed-stacks step
  │ → git diff HEAD~1 HEAD | grep '^stacks/' | cut -d/ -f2
  │ → detects which stacks changed
  ▼
VPS (via Docker socket mounted in agent)
  │
  │ scripts/deploy-stack.sh <stack>
  │   1. rsync stacks/<stack>/ → /lab/stacks/<stack>/  (skip .env)
  │   2. docker compose pull
  │   3. docker compose up -d --remove-orphans
  │   4. docker image prune -f
  ▼
Updated containers running on VPS
```

**Woodpecker agent** runs as a Docker container with the Docker socket mounted — it can execute `docker compose` commands directly on the host without SSHing in.

---

## Traefik Routing Details

Traefik operates in **HTTP mode only** (no TLS). Cloudflare terminates SSL at the edge (Flexible mode) — Cloudflare → VPS is plain HTTP port 80.

### SSL Mode Decision — Cloudflare Flexible (PAB-15)

**Current mode: Cloudflare Flexible**

- Browser → Cloudflare: HTTPS (TLS terminated at Cloudflare edge)
- Cloudflare → VPS port 80: plain HTTP (unencrypted)

**Security tradeoff:**
The Cloudflare → VPS leg is unencrypted. This is acceptable for a personal homelab because:
- Traffic only traverses Cloudflare's own backbone (not the open internet)
- All services are low-sensitivity (dashboards, monitoring, personal tools)
- No PII or credentials transit this hop in cleartext

**Upgrade path (if needed):**
Switch to **Cloudflare Full (Strict)** mode:
1. Obtain a Let's Encrypt cert via DNS-01 challenge using a Cloudflare API token
   - Traefik has native `cloudflare` DNS challenge provider support
   - Requires `CF_API_TOKEN` env var (scoped to `Zone:DNS:Edit` on `jaxmind.xyz`)
2. Add `certificatesResolvers` block to `traefik.yml` (ACME + cloudflare provider)
3. Flip Cloudflare dashboard → SSL/TLS → Full (Strict)
4. Traefik exposes port 443, docker-compose adds `"443:443"` port mapping

**Decision: Keep Flexible for now.** Revisit if this lab starts handling sensitive data or multi-user credentials.

```
Routing config method: Docker labels (dynamic)
Provider: providers.docker (exposedByDefault=false)
Network: proxy (all containers must be on this network)
Entry points:
  web     — :80  (HTTP, all public traffic)
  metrics — :8082 (Prometheus metrics, internal only)
```

Each service defines its routing via Docker labels:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<name>.rule=Host(`<name>.jaxmind.xyz`)"
  - "traefik.http.routers.<name>.entrypoints=web"
  - "traefik.http.services.<name>.loadbalancer.server.port=<PORT>"
```

Basic auth middleware is applied to all dashboards and internal services:
```yaml
  - "traefik.http.routers.<name>.middlewares=<name>-auth"
  - "traefik.http.middlewares.<name>-auth.basicauth.users=${AUTH_VAR}"
```

Auth hashes are bcrypt (`htpasswd -nB username`) stored in `.env` files on the VPS.
