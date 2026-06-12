# DevOps Portfolio App-Handoff Checklist

Use this reference when the user has an existing web/ecommerce app and wants to prove DevOps/web-operations ability rather than build product features.

## Core framing

The app is a handoff artifact. The user's proof is taking it from "runs locally" to "safe, reproducible, deployable, observable, and documented."

Phrase the portfolio claim like:

> I took an existing e-commerce app and handled the operational layer: containerization, database setup, environment configuration, deployment, reverse proxy, HTTPS, CI/CD, backups, monitoring, and runbook documentation.

Avoid framing the user as the full backend developer unless they actually owned the backend feature work.

## Audit commands/patterns

Run from project root where appropriate:

```bash
git status --short
git branch --show-current
git remote -v

docker compose ps
docker compose config --quiet
curl -fsS http://localhost:3000/api
curl -fsS http://localhost:3000/health
npm audit --audit-level=moderate
```

Also inspect presence/absence of:

```text
Dockerfile / dockerfile
docker-compose.yaml / docker-compose.yml
.env
.env.example
.gitignore
.dockerignore
README.md
.github/workflows/
nginx.conf / Caddyfile
scripts/backup*
scripts/restore*
```

## Already-done evidence to look for

- App image builds successfully.
- Compose includes app + DB services.
- DB uses a named volume for persistence.
- DB is not unnecessarily published to the host/public internet.
- DB init script is mounted into `/docker-entrypoint-initdb.d/` for reproducible bootstrap.
- App config uses environment variables.
- Smoke tests return real API data.

## Common remaining work

Prioritize in this order:

1. Git hygiene: `.gitignore`, keep `.env` private, do not commit `node_modules`.
2. `.env.example` documenting required variables without secrets.
3. `.dockerignore` to exclude `.env`, `.git`, `node_modules`, logs, local artifacts.
4. Dockerfile hardening: standard `Dockerfile` name, slim/base pinning, `npm ci`, production deps, non-root user.
5. Health endpoint that checks app + DB.
6. Compose healthchecks and `depends_on: condition: service_healthy` where supported.
7. `restart: unless-stopped` for long-lived services.
8. Reverse proxy with Nginx/Caddy; expose 80/443, keep app internal.
9. HTTPS with Certbot/Caddy/Cloudflare depending target.
10. Deployment target: VPS or AWS EC2 for portfolio proof.
11. GitHub Actions CI/CD with build, deploy, restart, and health verification.
12. Postgres backup/restore scripts using `pg_dump`/`pg_restore` or `psql` for SQL dumps.
13. Monitoring: uptime checks first; Prometheus/Grafana later only if useful.
14. Security maintenance: package audit, restricted CORS, secret handling, no public DB.
15. README/runbook/case study explaining architecture and operations.

## Coaching rule

For users preserving DevOps reps, do not patch DevOps files unless asked. Diagnose, give exact next change, let the user apply it, then verify.