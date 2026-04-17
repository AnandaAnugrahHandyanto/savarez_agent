# Stack: Homepage (Dashboard)

**Image:** `ghcr.io/gethomepage/homepage:latest`
**URL:** [home.jaxmind.xyz](https://home.jaxmind.xyz) (basic auth protected)
**Networks:** `proxy`

---

## Purpose

Homepage is a self-hosted dashboard that provides a single URL to access all services. It displays service status, links, and optionally widget data (e.g. active containers, disk usage).

## Config Files

Config lives in `stacks/homepage/config/` (synced to `/lab/stacks/homepage/config/` on deploy):

| File | Purpose |
|---|---|
| `settings.yaml` | Global settings (title, theme, layout, favicon) |
| `services.yaml` | Service groups and links shown on dashboard |
| `widgets.yaml` | Info widgets (datetime, resources, search bar) |
| `docker.yaml` | Docker integration (shows container status) |

Changes to these files are deployed by committing and pushing — Woodpecker syncs them via `deploy-stack.sh`.

## Config Choices

| Parameter | Value | Reason |
|---|---|---|
| `HOMEPAGE_VAR_TITLE=jaxmind.xyz` | Custom title | Used in page title via `{{HOMEPAGE_VAR_TITLE}}` |
| `HOMEPAGE_ALLOWED_HOSTS=home.jaxmind.xyz` | Security | Prevents DNS rebinding attacks |
| `PUID/PGID=1000` | UID/GID | Matches `pablo` user on VPS |
| Docker socket mount (read-only) | Container status | Homepage reads container state for status indicators |

## Auth

Basic auth via Traefik middleware using `HOMEPAGE_AUTH` env var (bcrypt hash). The realm is `jaxmind`.

## Secrets

| Env var | What it is |
|---|---|
| `HOMEPAGE_AUTH` | bcrypt hash for dashboard basic auth |
