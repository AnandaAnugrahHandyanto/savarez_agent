# DevOps Compose smoke checks and exposure audit

Use this when coaching a user through production-readiness checks for a Docker Compose app where the user owns the DevOps/runtime layer.

## Coaching pattern

Preserve the user's reps: give one small script block at a time, let the user edit, then verify with real commands.

Good sequence:
1. Validate Compose structure: `docker compose config --quiet`.
2. List containers: `docker compose ps`.
3. Strengthen container checks from display-only to assertions for each expected healthy service.
4. Check HTTP health endpoint through the public reverse proxy, not direct app port.
5. Strengthen HTTP checks from status-only to content assertions.
6. Check business/API endpoint response content so frontend fallback HTML cannot pass as a fake success.
7. Check backup existence, but phrase correctly: existence is not freshness or restoreability.
8. Check public exposure: only reverse proxy should publish ports; app and DB should remain internal.
9. End with a final success message only after all checks pass.

## Example `check-stack.sh` blocks

### Compose config

```bash
echo "Checking Compose config..."
docker compose config --quiet
echo "Compose config OK"
```

### Container health assertions

```bash
echo "Checking containers..."
docker compose ps
docker compose ps | grep -q "aa-nginx-1.*healthy"
docker compose ps | grep -q "aa-app-1.*healthy"
docker compose ps | grep -q "aa-db-1.*healthy"
echo "Containers are healthy"
```

Adapt container names to the project name. Do not leave this as `docker compose ps` only; display-only checks are weak.

### DB-backed health endpoint

```bash
echo "Checking /health endpoint..."
health_response="$(curl -fsS http://localhost:8080/health)"
echo "$health_response"
echo "$health_response" | grep -q '"database":"connected"'
echo "Health endpoint OK"
```

`curl -f` alone only proves HTTP status. It can pass on wrong content.

### Product/API endpoint content check

```bash
echo "Checking /products endpoint..."
products_response="$(curl -fsS http://localhost:8080/products)"
echo "$products_response"
echo "$products_response" | grep -q '"name":"Crystal Guardian Pendant"'
echo "Products endpoint OK"
```

Pitfall: `/api/products` may return `200 OK` with frontend HTML if the backend route is actually `/products` and the app falls back to serving static files. Always verify content type/body, not just status.

### Backup existence

```bash
echo "Checking database backups..."
find backups -maxdepth 1 -type f -name "*.sql" | grep -q .
echo "Database backup exists"
```

Say clearly this checks only that a SQL backup exists. Freshness and restoreability are stronger later checks.

### Public exposure

```bash
echo "Checking public port exposure..."
docker compose config | grep -q 'published: "8080"'
! docker compose config | grep -q 'published: "3000"'
! docker compose config | grep -q 'published: "5432"'
echo "Only Nginx is publicly exposed"
```

With `set -e`, Bash `! grep -q` is valid: the script continues only when the forbidden published port is absent.

## Verification commands

After each edit:

```bash
./scripts/check-stack.sh
docker compose config --quiet
docker compose ps
docker compose config | grep -A8 -B3 -n 'ports:' || true
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

If checking host listeners, distinguish a host-level service from a Compose-published container. A host Postgres on `127.0.0.1:5432` does not mean the Compose DB is exposed if `docker compose ps` shows only `5432/tcp` for the DB container.

## Interview framing

Useful phrasing:

> I wrote a reusable local smoke-test script that CI can later call. It validates Compose config, container health, DB-backed health, product API content, backup existence, and public port exposure. Only the reverse proxy is published; app and database stay internal on the Docker network.
