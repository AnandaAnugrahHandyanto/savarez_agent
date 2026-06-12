# DevOps portfolio: PostgreSQL backup/restore scripts

Use this when coaching a user through backup/restore work on an existing Docker Compose app where the user owns DevOps reps.

## Target artifacts

- `scripts/backup-db.sh` — creates timestamped SQL dumps under `backups/`.
- `scripts/restore-db.sh` — restores a selected SQL dump into the Compose PostgreSQL service.
- `backups/.gitkeep` — keeps the backup directory in Git.
- `.gitignore` — tracks `.gitkeep` but ignores real generated backup files.
- README/runbook — documents script usage and restore warnings.

## Good `.gitignore` pattern

Avoid `backups/`, because that hides `backups/.gitkeep` too.

```gitignore
# Keep backup directory, ignore generated backup files
backups/*
!backups/.gitkeep
```

Verify:

```bash
git check-ignore -v backups/.gitkeep backups/shop-YYYYMMDD-HHMMSS.sql scripts/backup-db.sh scripts/restore-db.sh || true
```

Expected:
- `backups/.gitkeep` is not ignored.
- real `.sql`/dump files are ignored.
- scripts are not ignored.

## Backup script checks

A simple local Compose script is acceptable:

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p backups
timestamp="$(date +%Y%m%d-%H%M%S)"
output="backups/shop-${timestamp}.sql"

docker compose exec -T db pg_dump -U postgres -d shop > "$output"
echo "Backup written to $output"
```

Verify without leaking data:

```bash
find backups -maxdepth 1 -type f -printf '%f\t%s bytes\n' | sort
file backups/*.sql
wc -c backups/*.sql
grep -q -- '-- PostgreSQL database dump complete' backups/*.sql && echo complete
```

Inspect structure, not product/customer rows:

```bash
grep -nE '^-- Name: |^CREATE TABLE |^COPY public\.|^ALTER TABLE ONLY public\.|^CREATE SEQUENCE ' backups/latest.sql | sed -n '1,120p'
```

Count rows per COPY block with a small parser rather than printing data.

## Restore script checks

Prefer:

- `set -euo pipefail`
- `backup_file="${1:-}"` so no-arg behavior is controlled under `set -u`
- usage function
- file readability check
- load `.env` safely for `DB_USER`/`DB_NAME` with defaults
- `psql -v ON_ERROR_STOP=1`
- optional `--clean` that drops/recreates `public` before restore

Common pitfall: restoring to placeholder DB names like `my_database` instead of the real Compose DB (`shop` or `$DB_NAME`). Confirm actual names with:

```bash
docker compose exec -T db psql -U postgres -tAc "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
```

## Non-destructive restore verification

Do not mutate the user's real app DB just to prove the script/dump works. Restore the dump into a temporary database, validate row counts/schema, then drop it:

```bash
TMPDB="restore_check_$(date +%s)"
docker compose exec -T db createdb -U postgres "$TMPDB"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d "$TMPDB" < backups/shop-YYYYMMDD-HHMMSS.sql
rows=$(docker compose exec -T db psql -U postgres -d "$TMPDB" -tAc "SELECT COUNT(*) FROM products;")
echo "restored_products_rows=$rows"
docker compose exec -T db dropdb -U postgres "$TMPDB"
```

For this class of small ecommerce portfolio app, a successful temp restore with the expected row count is strong evidence while preserving the user's real runtime state.

## README/runbook drift

After adding scripts, update README backup/restore sections to show:

```bash
./scripts/backup-db.sh
./scripts/restore-db.sh backups/shop-YYYYMMDD-HHMMSS.sql
./scripts/restore-db.sh --clean backups/shop-YYYYMMDD-HHMMSS.sql
```

State explicitly that generated backup files are ignored and should not be committed if they contain production/customer data.
