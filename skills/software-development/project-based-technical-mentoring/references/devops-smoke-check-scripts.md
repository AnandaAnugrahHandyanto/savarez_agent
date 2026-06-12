# DevOps smoke-check scripts for Compose app handoffs

Use this reference when coaching the user through local operational smoke checks before CI/deploy.

## Pattern: grow the script incrementally

For learning-focused DevOps reps, build `scripts/check-stack.sh` in small verified steps:

1. Compose syntax/config validation:
   ```bash
   docker compose config --quiet
   ```
2. Container visibility, then assertions:
   ```bash
   docker compose ps
   docker compose ps | grep -q "<project>-nginx-1.*healthy"
   docker compose ps | grep -q "<project>-app-1.*healthy"
   docker compose ps | grep -q "<project>-db-1.*healthy"
   ```
3. DB-backed health endpoint:
   ```bash
   health_response="$(curl -fsS http://localhost:8080/health)"
   echo "$health_response"
   echo "$health_response" | grep -q '"database":"connected"'
   ```
4. Product/API endpoint content check:
   ```bash
   products_response="$(curl -fsS http://localhost:8080/products)"
   echo "$products_response"
   echo "$products_response" | grep -q '"name":"Crystal Guardian Pendant"'
   ```
5. Backup existence check:
   ```bash
   find backups -maxdepth 1 -type f -name "*.sql" | grep -q .
   ```
6. Final success marker:
   ```bash
   echo "Stack check passed"
   ```

## Important pitfall: HTTP 200 is not enough

`curl -f` proves only that the response status is not 4xx/5xx. It does **not** prove the route returned the correct resource. A wrong path can return `200 OK` with frontend HTML and still pass a weak script.

When a route is supposed to return JSON/API data, assert on response content or content type. For simple Bash checks, capture the body and `grep -q` for a stable expected field/value.

Example failure pattern:
- `/api/products` returned `200 OK`
- body was the frontend `index.html`
- weak script printed `Products endpoint OK`
- stronger check against a real product name exposed/fixed the route mismatch

## Coaching notes

- Let the user apply each script step when it is part of their DevOps learning lane; inspect and verify after they say `check`.
- If you gave a wrong endpoint/path, own it clearly and patch the guidance/script if takeover is appropriate.
- Keep the explanation focused on operational meaning: config validity, container health, reverse proxy routing, DB connectivity, API behavior, and backup presence.
- Before committing, verify generated backup SQL files are ignored and only placeholders like `backups/.gitkeep` are tracked.
