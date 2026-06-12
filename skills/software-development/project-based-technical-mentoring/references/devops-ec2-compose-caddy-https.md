# EC2 + Docker Compose + Caddy HTTPS coaching notes

Use this when a Docker Compose app is already running on EC2 behind a domain and the next step is production HTTPS.

## Good target shape

For a small EC2 Compose deployment, Caddy is a clean HTTPS front door:

```text
rscollection.online
  ↓ 80/443
Caddy container
  ↓ Docker network
app container :3000
  ↓
Postgres/container or external DB
```

Caddy should own host ports `80:80` and `443:443`. The app and database ports should stay internal.

## Compose pattern

```yaml
services:
  app:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      app:
        condition: service_healthy

volumes:
  caddy_data:
  caddy_config:
```

Use named Caddy volumes so Let's Encrypt certificates survive container recreation.

## Caddyfile pattern: local/CI vs production

Avoid hard-coding production domains in the Caddyfile if CI/local tests run before DNS points to the current machine. Use an env var with a safe local default:

```caddyfile
# Local/CI default is :80.
# Production .env should set:
# CADDY_SITE=example.com, www.example.com
{$CADDY_SITE::80} {
    reverse_proxy app:3000
}
```

`.env.example` can contain:

```env
CADDY_SITE=:80
```

Production `.env` should contain a comma followed by a space between hostnames:

```env
CADDY_SITE=rscollection.online, www.rscollection.online
```

Caddy rejects `rscollection.online,www.rscollection.online` with: `Site addresses cannot contain a comma ',' ... put a space after the comma`.

## Deployment sequence

1. Verify DNS authoritative records point to the EC2 Elastic IP.
2. Ensure the EC2 security group allows `80` and `443` from the internet.
3. Commit/push the Caddy Compose/Caddyfile changes.
4. On EC2, set production `.env` with `CADDY_SITE=domain, www.domain`.
5. Remove/stop old reverse-proxy containers that still bind port 80:

```bash
docker compose down --remove-orphans
```

6. Recreate the stack:

```bash
docker compose up -d --build
```

7. Watch Caddy logs for successful ACME validation and certificate issuance:

```bash
docker compose logs --tail=120 caddy
```

Good log signs include:

```text
served key authentication
authorization finalized
certificate obtained successfully
```

## Pitfalls

- If replacing `nginx` with `caddy`, an orphan `nginx` container may keep port 80 allocated. Use `docker compose down --remove-orphans`, not just `up -d`.
- If local/CI Caddyfile hard-codes production domains, local test stacks can attempt real Let's Encrypt validation against the live domain and fail. Use `CADDY_SITE=:80` for CI/local.
- `curl http://localhost/health` may show an empty reply for a few seconds while Caddy starts; check logs before assuming the app failed.
- Do not treat HTTPS as done until external checks prove both root and `www` work over HTTPS and HTTP redirects to HTTPS.

## Verification

External checks:

```bash
curl -i https://example.com/health
curl -i https://www.example.com/health
curl -i https://example.com/products
curl -I http://example.com/health
```

Expected:
- HTTPS endpoints return `200` with app JSON/content.
- Response includes `via: 1.1 Caddy` or equivalent Caddy evidence.
- HTTP returns `308 Permanent Redirect` to HTTPS.
- CI passes with local `CADDY_SITE=:80`.
