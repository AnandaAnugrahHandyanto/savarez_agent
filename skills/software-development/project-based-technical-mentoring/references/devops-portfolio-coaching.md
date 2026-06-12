# DevOps Portfolio Coaching Notes

Use this reference when coaching the user through an existing application used as a DevOps portfolio/practice project.

## Ownership split
- The app/product can be treated as developer-owned or assistant-built support material.
- The user should own the operational layer: Git hygiene, Dockerfile, Compose, environment variables, database bootstrap/reset, healthchecks, restart policies, reverse proxy, deployment, CI/CD, backups, monitoring, and runbooks.
- Do not patch DevOps files for the user unless they explicitly ask for takeover. Prefer: inspect → explain → give exact change → user edits → verify.

## Good DevOps progression for a small Node/Postgres ecommerce app
1. Git hygiene: `.gitignore`, keep `.env` and `node_modules/` out, track `.env.example`, Dockerfile, Compose, `.dockerignore`.
2. Docker build hygiene: standard `Dockerfile` casing, `.dockerignore`, slim base image, `npm ci`, production-only deps, non-root runtime user.
3. Compose reliability: app + DB services, internal DB networking, named volume, mounted DB init script, DB healthcheck, app healthcheck, `depends_on.condition: service_healthy`, `restart: unless-stopped`.
4. Security maintenance: run `npm audit`, apply safe `npm audit fix`, rebuild and smoke-test. Avoid `--force` unless reviewed.
5. Documentation: README/runbook explaining local run, env vars, architecture, backup/restore, troubleshooting, and the user's DevOps ownership.
6. Production layers: Nginx/Caddy reverse proxy, HTTPS, VPS/AWS deployment, CI/CD, backup/restore test, uptime monitoring.

## Verification pattern
For each user-applied DevOps change, verify with real commands when available:
- `docker compose config --quiet`
- `docker compose build`
- `docker compose up -d` if needed, tracked/background if tooling treats it as long-lived
- `docker compose ps` and health status
- smoke-test app endpoints with `curl`
- inspect runtime user for non-root hardening: `docker compose exec -T app sh -lc 'id && whoami'`
- use `git status --short --ignored` and `git ls-files` to confirm important files are tracked and secrets/local deps are ignored

## Pitfalls seen
- `.gitignore` and `.dockerignore` are different: Git should track Dockerfile/Compose/README/`.dockerignore`; Docker build context may exclude Compose/README/secrets.
- Case matters on Linux: `Dockerfile`, `docker-compose.yaml`, and `.dockerignore` are conventional/expected names; accidental `Docker-compose.yaml` or `.Dockerignore` can break tooling.
- `docker compose config` expands env values; prefer `docker compose config --quiet` when validating in shared output to avoid exposing secrets.
- `depends_on: [db]` only orders container startup; it does not wait for DB readiness. Use a DB healthcheck plus `condition: service_healthy`.
- If the app image lacks `curl`/`wget`, an app healthcheck can use `node -e` with the built-in `http` module.
