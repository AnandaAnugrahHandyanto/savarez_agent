# Stack: Monitoring (VictoriaMetrics + Loki + Promtail + Alertmanager + vmalert)

**Networks:** `monitoring` (internal), `proxy` (VictoriaMetrics + Loki for external access)

---

## Services

| Container | Image | Port | URL |
|---|---|---|---|
| `victoriametrics` | `victoriametrics/victoria-metrics:v1.101.0` | 8428 | [vm.jaxmind.xyz](https://vm.jaxmind.xyz) |
| `node-exporter` | `prom/node-exporter:v1.8.2` | 9100 | internal |
| `docker-stats-exporter` | `wywywywy/docker_stats_exporter:latest` | 9487 | internal |
| `loki` | `grafana/loki:3.1.0` | 3100 | [loki.jaxmind.xyz](https://loki.jaxmind.xyz) |
| `promtail` | `grafana/promtail:3.1.0` | — | internal (push only) |
| `alertmanager` | `prom/alertmanager:v0.27.0` | 9093 | internal |
| `vmalert` | `victoriametrics/vmalert:v1.101.0` | 8880 | internal |

---

## VictoriaMetrics

**Purpose:** Prometheus-compatible metrics storage. Scrapes all targets every 15s, stores for 90 days.

**Scrape targets** (`victoriametrics/scrape.yml`):

| Job | Target | What it collects |
|---|---|---|
| `node` | `node-exporter:9100` | CPU, RAM, disk, network, filesystem |
| `docker` | `docker-stats-exporter:9487` | Per-container CPU %, RAM, net I/O |
| `traefik` | `traefik:8082` | HTTP request rate, latency, error rate |
| `woodpecker` | `woodpecker-server:9001` | Build counts, queue depth |
| `victoriametrics` | `victoriametrics:8428` | Self-metrics |

**Why not Prometheus?** VictoriaMetrics uses ~3–5x less RAM and has better compression for long-term storage. It's a drop-in Prometheus replacement.

**Why not cAdvisor for container metrics?** This host uses the `overlayfs` Docker storage driver. cAdvisor requires `layerdb/mounts` paths that only exist under `overlay2`. `docker-stats-exporter` uses only the Docker socket API and works on any driver.

**Grafana Cloud integration:**
- Datasource name: `Jax-Metrics`
- Datasource UID: `efiwad0exm5tsf`
- Connection: Grafana Cloud remote_read from `https://vm.jaxmind.xyz`

---

## Node Exporter

**Purpose:** Exposes VPS system metrics (CPU, RAM, disk I/O, network, filesystems) in Prometheus format.

**Config choices:**
- `pid: host` — must run in host PID namespace to see all processes
- `--path.rootfs=/host` with `/:/host:ro,rslave` mount — reads host filesystem for accurate disk stats
- Filesystem exclusion regex prevents noise from pseudo-filesystems

---

## docker-stats-exporter

**Purpose:** Exposes per-container metrics using Docker `stats` API. Replaces cAdvisor.

**Config:** Mounts Docker socket read-only. No additional config needed — auto-discovers all running containers.

---

## Loki

**Purpose:** Log aggregation. Stores structured logs from all containers + system logs.

**Config** (`loki/config.yml`):
- Filesystem storage backend (data volume: `loki_data` → `/mnt/data/docker`)
- Accessible externally at `loki.jaxmind.xyz` (basic auth via Traefik)

**Grafana Cloud integration:**
- Datasource name: `jax-loki`
- Datasource UID: `afiwd6p9kej28e`
- Connection: HTTP from Grafana Cloud to `https://loki.jaxmind.xyz`

---

## Promtail

**Purpose:** Log shipper — tails Docker container logs and system logs, labels them, pushes to Loki.

**Config** (`promtail/config.yml`):
- Scrapes Docker logs via socket: auto-discovers containers, labels with `container_name`, `image`, `compose_service`
- Tails `/var/log` for system logs
- Pushes to `loki:3100` on the `monitoring` network

---

## Alertmanager

**Purpose:** Routes alerts from VictoriaMetrics to notification channels (Discord).

**Config** (`alertmanager/config.yml`):
- Single receiver: Discord webhook
- Groups alerts to reduce noise
- Alert rules defined in VictoriaMetrics config

---

## vmalert

**Purpose:** Evaluates infrastructure alert rules against VictoriaMetrics and forwards firing alerts to Alertmanager.

**Config:**
- Rule file lives at `victoriametrics/alerts.yml`
- Reads from `victoriametrics:8428`
- Sends notifications to `alertmanager:9093`
- Exposes internal health/metrics on port `8880`

---

## Secrets

| Env var | What it is |
|---|---|
| `VM_AUTH` | bcrypt hash for VictoriaMetrics dashboard basic auth |
| `LOKI_AUTH` | bcrypt hash for Loki endpoint basic auth |

---

## Grafana Dashboards

| Dashboard | UID |
|---|---|
| Node Exporter Full | `cdb74b0f-49d8-4c01-82ff-e192fc7fbb98` |
| Docker Container Metrics | `2b3fa9a7-452f-488f-969a-094548671ffa` |
| Logs / App | `ff2a1055-bb7a-424f-8f22-b7dc3cad742b` |

Grafana itself is **not self-hosted** — Grafana Cloud (free tier) is used. This avoids managing another stateful container and the free tier is sufficient.
