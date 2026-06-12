# EC2 + Docker Compose CI/routing coaching notes

Use this when coaching a DevOps portfolio/client app from local Compose to GitHub Actions CI and EC2 deployment.

## CI: never require real `.env`

If GitHub Actions fails because Compose expects `.env`, do not tell the user to commit secrets or add production secrets for a config-only check. For validation/smoke-test CI, create a temporary safe env file:

```yaml
- name: Create CI env file
  run: cp .env.example .env
```

Then run config/build/smoke tests:

```yaml
- run: docker compose config --quiet
- run: docker compose build
- run: docker compose up -d
- run: |
    for i in {1..30}; do
      if curl -fsS http://localhost:8080/health | grep -q '"status":"ok"'; then
        exit 0
      fi
      docker compose ps
      sleep 3
    done
    docker compose logs
    exit 1
- run: curl -fsS http://localhost:8080/api/products | grep -q "Crown Charm Chain"
- if: always()
  run: docker compose down -v
```

Principle: CI uses safe test config copied from `.env.example`; production secrets stay in server-side `.env` or GitHub secrets only when a workflow actually needs them.

## EC2 production `.env` permissions

When editing `.env` on EC2 fails with `Permission denied`, check ownership before retrying:

```bash
pwd
ls -la
ls -la .env
whoami
```

If the project should belong to the current SSH user, fix ownership inside the repo:

```bash
sudo chown -R $USER:$USER .
nano .env
chmod 600 .env
```

Generate real values instead of weak placeholders:

```bash
openssl rand -base64 32   # DB_PASSWORD
openssl rand -base64 32   # ADMIN_TOKEN
```

Do not ask the user to paste `.env` back into chat. Ask for `docker compose ps` or endpoint checks instead.

## Remote verification pattern

After the user says the EC2 URL works, verify these endpoints externally when possible:

```text
http://SERVER_IP:8080/
http://SERVER_IP:8080/health
http://SERVER_IP:8080/api/products
```

Good signs:
- `/` returns storefront HTML
- `/health` returns JSON with `status: ok` and `database: connected`
- `/api/products` returns product JSON, not frontend HTML

## Nginx API routing pitfall

If `/health` works but `/api/products` returns the frontend HTML page, the app is alive but Nginx is probably sending API paths to the frontend fallback. Coach the user to inspect `nginx/default.conf` and add explicit API routes above the catch-all `/` route, for example:

```nginx
location /api/ {
    proxy_pass http://app:3000/api/;
}

location /health {
    proxy_pass http://app:3000/health;
}

location / {
    proxy_pass http://app:3000;
}
```

Then restart only Nginx and retest locally on the server:

```bash
docker compose restart nginx
curl http://localhost:8080/health
curl http://localhost:8080/api/products
```

Do not treat “homepage loads” as deployment complete. A deployed DB-backed app must prove API routing and database-backed health too.
