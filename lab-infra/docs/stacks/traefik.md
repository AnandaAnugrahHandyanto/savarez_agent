# Stack: Traefik (Reverse Proxy)

**Image:** `traefik:v2.11`
**URL:** [traefik.jaxmind.xyz](https://traefik.jaxmind.xyz) (dashboard, basic auth protected)
**Networks:** `proxy`

---

## Purpose

Traefik is the entry point for all HTTP traffic to the VPS. It:
- Accepts traffic on port 80 (mapped from host port 80)
- Routes by hostname (`Host()` rule) to the correct container
- Discovers services automatically via Docker labels
- Exposes a Prometheus metrics endpoint on port 8082
- Provides a web dashboard at `traefik.jaxmind.xyz`

## Why Traefik v2.11 (not v3)?

v3.x has a Docker API negotiation bug with the Docker daemon version on this host — it fails to start. v2.11 is stable and has all the features we need.

## Config Choices

| Parameter | Value | Reason |
|---|---|---|
| `providers.docker.exposedByDefault=false` | Opt-in routing | Only containers with `traefik.enable=true` get routed |
| `providers.docker.network=proxy` | Named network | Traefik only uses containers' `proxy` network interface for routing |
| `api.insecure=false` | Dashboard not exposed directly | Dashboard served via router `traefik.jaxmind.xyz` with auth middleware |
| `accesslog.format=json` | JSON access logs | Parseable by Promtail → Loki |
| `entrypoints.metrics.address=:8082` | Separate metrics port | Prometheus scrape target, not exposed via Traefik itself |

## Secrets

| Env var | What it is |
|---|---|
| `TRAEFIK_DASHBOARD_AUTH` | bcrypt hash of dashboard credentials (`htpasswd -nB user`) |

## Known Issues

- No HTTPS on the VPS side — Cloudflare Flexible mode means traffic is HTTP between Cloudflare and VPS. This is intentional for simplicity; upgrade to Full Strict would require a valid cert on the VPS.
- `DOCKER_API_VERSION=1.41` is pinned to avoid version negotiation issues with the host Docker daemon.
