# DevOps local smoke-check scripts for Compose apps

Use this when coaching the user through a local `scripts/check-stack.sh` or similar operational smoke test for a Docker Compose app.

## Coaching pattern

Preserve the user's reps: give one small check at a time, let the user edit, then verify with real commands.

Good sequence:
1. `docker compose config --quiet` — validates Compose/YAML before runtime checks.
2. `docker compose ps` — show current services, then strengthen into assertions.
3. Container health assertions — grep expected service names and `healthy` status.
4. HTTP health endpoint — `curl -fsS`, then capture response and assert DB-connected content.
5. Feature/API endpoint — `curl -fsS`, then assert response contains expected JSON/application data, not just HTTP 200.
6. Backup existence check — `find backups -maxdepth 1 -type f -name "*.sql" | grep -q .`.
7. Final success message — makes CI/log output easy to scan.

## Important pitfall: HTTP 200 is not enough

A wrong route can return `200 OK` with frontend HTML and still pass `curl -f`. Do not call a smoke check successful only because curl exits 0.

Strengthen checks by capturing response bodies and grepping for meaningful content:

```bash
health_response="$(curl -fsS http://localhost:8080/health)"
echo "$health_response"
echo "$health_response" | grep -q '"database":"connected"'

products_response="$(curl -fsS http://localhost:8080/products)"
echo "$products_response"
echo "$products_response" | grep -q '"name":"Crystal Guardian Pendant"'
```

If an endpoint returns HTML instead of JSON, inspect actual app routes before changing Nginx or the script. In one ecommerce app, `/api/products` returned the frontend page while the real JSON endpoint was `/products`.

## Container health assertion pattern

For a Compose project with stable container names, a simple beginner-friendly assertion is acceptable:

```bash
docker compose ps
docker compose ps | grep -q "aa-nginx-1.*healthy"
docker compose ps | grep -q "aa-app-1.*healthy"
docker compose ps | grep -q "aa-db-1.*healthy"
echo "Containers are healthy"
```

Teach the limitation: this is project-name-specific. A more portable future version can inspect service names or Docker health via `docker inspect`, but simple grep is fine while the user is learning.

## Backup check nuance

A backup existence check proves at least one SQL dump exists; it does not prove freshness or restorability. For client/friend apps, eventually add a restore test into a temporary database, but keep it as a separate milestone so the user understands each layer.

## Verification after each user edit

After the user says `check ...`, verify:
- file content with line numbers;
- executable bit if it is a script;
- real script execution from the project root;
- direct endpoint/content-type/body when an HTTP check is involved;
- `git status --short` to keep milestones clean.

Report pass/fail based on tool output, not assumptions. If the script passes but the response is semantically wrong, say it failed logically and fix the instruction path.