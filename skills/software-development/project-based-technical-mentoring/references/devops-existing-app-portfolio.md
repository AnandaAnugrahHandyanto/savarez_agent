# DevOps existing-app portfolio mentoring reference

Use when the user has an existing app and wants to prove DevOps/web-operations work without owning all app feature development.

## Role split to preserve

Assistant/developer lane:
- App features, UI, business logic, schema design, small support endpoints like `/health` if explicitly needed.

User DevOps lane:
- Git hygiene and reproducibility
- Dockerfile and `.dockerignore`
- Docker Compose services, networks, volumes, healthchecks, restart policies
- `.env.example`, secret hygiene, env wiring
- DB bootstrap/init/reset as operational state management
- Reverse proxy, HTTPS, deployment, CI/CD
- Backup/restore, monitoring, logs, docs/runbook

## Coaching loop

1. Inspect current files/state read-only.
2. State what is wrong/missing and why it matters operationally.
3. Give the smallest next task.
4. Provide reference snippets only when useful; tell the user to type/adapt and understand them.
5. User applies change.
6. Verify with commands and report exact evidence.
7. Move to the next smallest DevOps task.

## Reproducibility checks

Git hygiene:
```bash
git status --short
git status --ignored --short | sed -n '1,120p'
git check-ignore -v docker-compose.yaml .dockerignore README.md .env node_modules 2>/dev/null || true
git ls-files | sed -n '1,140p'
```
Expected: `.env` and `node_modules/` ignored; Compose, `.dockerignore`, `.env.example`, Dockerfile, README tracked.

Compose validation:
```bash
docker compose config --quiet && echo 'compose config OK'
```
Avoid sharing full `docker compose config` output casually because it expands `.env` values and may expose secrets.

Build/runtime smoke test:
```bash
docker compose build
docker compose up -d
docker compose ps
curl -fsS http://localhost:3000/api
curl -fsS http://localhost:3000/products
```
If the tool wrapper blocks `docker compose up -d` as long-lived, run it as a tracked background process, wait/poll, then test endpoints separately.

## Compose healthcheck pattern

DB healthcheck using the Postgres image tool:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

App healthcheck when the container lacks curl/wget but has Node:
```yaml
healthcheck:
  test:
    [
      "CMD",
      "node",
      "-e",
      "require('http').get('http://localhost:3000/api', res => process.exit(res.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
    ]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 20s
```

Make app wait for DB health:
```yaml
depends_on:
  db:
    condition: service_healthy
```

Verify health:
```bash
docker compose ps
docker inspect --format '{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' <app-container> <db-container>
```

## Restart policy pattern

Add to both app and db services:
```yaml
restart: unless-stopped
```

Verify without leaking env values:
```bash
python3 - <<'PY'
import yaml, pathlib
data=yaml.safe_load(pathlib.Path('docker-compose.yaml').read_text())
for name, svc in data.get('services', {}).items():
    print(f'{name}: restart={svc.get("restart", "MISSING")}')
PY
```

## Case-sensitive filename pitfalls

On Linux, case matters.
- Use `Dockerfile` for the image build file.
- Keep Compose as `docker-compose.yaml` unless the project intentionally uses `compose.yaml`.
- Keep Docker ignore as `.dockerignore`, not `.Dockerignore`.

If a rename goes wrong, inspect with:
```bash
git status --short
python3 - <<'PY'
from pathlib import Path
for name in ['Dockerfile','dockerfile','docker-compose.yaml','Docker-compose.yaml','.dockerignore','.Dockerignore']:
    print(f'{name}:', 'exists' if Path(name).exists() else 'missing')
PY
```

Use `git mv` for tracked file casing fixes, e.g.:
```bash
git mv dockerfile Dockerfile
git mv Docker-compose.yaml docker-compose.yaml
git mv .Dockerignore .dockerignore
```

## Progress checklist

A useful ordered checklist for this class of project:
```text
[x] .gitignore protects secrets/local deps
[x] .env.example present
[x] Dockerfile + .dockerignore tracked
[x] docker-compose.yaml tracked and valid
[x] App + DB run through Compose
[x] DB init/bootstrap mounted
[x] API smoke tested
[x] Healthchecks for app and DB
[x] App waits for healthy DB
[x] Restart policies
[ ] Dockerfile hardening: NODE_ENV, production deps, non-root user
[ ] README/runbook
[ ] Nginx reverse proxy
[ ] HTTPS
[ ] Deployment target
[ ] CI/CD
[ ] Backup/restore tested
[ ] Monitoring/uptime/logs
[ ] Portfolio case study
```
