# DevOps client-app backup/restore + learning reps

Use when coaching a user through an existing app they are preparing for a friend/client, not only a portfolio demo.

## Client-app priority shift

When the user says the app is for a friend/client, reframe “best” as reliability and safety before advanced features:

1. reliable startup and restart behavior
2. data safety: backup/restore, tested restores, off-server backups later
3. security: no committed secrets, strong admin token, no public DB/app ports, production CORS/domain restrictions
4. HTTPS before real users
5. monitoring/uptime checks
6. deployment/runbook clarity
7. cache only after the basics are stable

Avoid recommending Redis/API cache early for a small ecommerce app unless there is real scale/latency evidence. Static asset caching through Nginx is a later low-risk improvement; do not cache health/admin/mutation/product-freshness-sensitive routes by default.

## AWS hosting recommendation for this class

For a small friend/client app already using Docker Compose, prefer first deployment on EC2 + Docker Compose before ECS/Kubernetes:

- Security group: expose 80/443 publicly, restrict 22, do not expose 5432 or 3000.
- Use Elastic IP + Route 53 when a stable domain is needed.
- Use strong `.env` values generated on the server; never commit `.env`.
- Keep containerized Postgres acceptable for v1 only if backups are tested; later migration path can be RDS.
- Add S3 upload for backups after local backup/restore works.
- CI/CD comes after local checks are understood.

## Backup/restore workflow pattern

A good local backup script:

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
timestamp="$(date +%Y%m%d-%H%M%S)"
output="backups/shop-${timestamp}.sql"
docker compose exec -T db pg_dump -U postgres -d shop > "$output"
echo "Backup written to $output"
```

A good restore script should:

- use `set -euo pipefail`
- accept a backup file argument via `${1:-}`
- check the file exists/is readable
- load `.env` for `DB_USER` and `DB_NAME`, with safe defaults
- use `psql -v ON_ERROR_STOP=1`
- optionally support `--clean` to drop/recreate public schema before restore

Verify restore without mutating the real app DB by creating a temporary database, restoring the SQL dump into it, checking row counts, then dropping the temp DB.

## Git hygiene for backups

Use:

```gitignore
# Keep backup directory, ignore generated backup files
backups/*
!backups/.gitkeep
```

Verify:

```bash
git check-ignore -v backups/.gitkeep backups/some-backup.sql
```

Expected: `.gitkeep` is not ignored; generated backup files are ignored.

## Coaching/pedagogy signal

If the user says they only know commands because the assistant tells them what to type, slow down. Before building full scripts, ask them to explain the command using this pattern:

1. What problem does it solve?
2. What tool is being used?
3. What input does it take?
4. What output/result should happen?

Use prediction → run → compare. Build scripts line-by-line, not as a giant copy-paste, when the task is a learning rep.

Example command meanings to teach:

- `docker compose ps` → services, health/running state, and port mappings.
- `docker compose config --quiet` → validates Compose config; no output means OK.
- `curl -fsS URL` → quiet HTTP check that fails loudly on bad status/errors.
- `find backups -maxdepth 1 -type f -name '*.sql'` → finds SQL backup files directly under backups.
- `git status --short` → compact view of modified/staged/deleted/untracked files.

Also teach shell primitives before automation: `>` overwrite redirect, `>>` append redirect, `|` pipe, and command exit codes (`0` success, non-zero failure). Automation lives on exit codes.