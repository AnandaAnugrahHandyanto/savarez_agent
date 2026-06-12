# Live GitHub + EC2 triage for DevOps coaching

Use this when the user asks what to do next for a deployed app and gives both a GitHub repo/context and a live EC2 IP/domain.

## Goal

Ground the recommendation in real state, not generic architecture advice. Inspect the repo and externally reachable endpoints, compare expected routes/ports/docs against live behavior, then give the next smallest DevOps moves.

## Read-only inspection pattern

1. Inspect the live endpoint externally:

```bash
curl -sS -I --max-time 10 http://SERVER/
curl -sS --max-time 10 http://SERVER/ | head -c 1200
curl -sS -i --max-time 10 http://SERVER/health | head -c 1200
curl -sS -i --max-time 10 http://SERVER/products | head -c 1200
curl -sS -i --max-time 10 http://SERVER/api/products | head -c 1200
```

Good signs:
- homepage returns storefront HTML
- `/health` returns JSON and proves database connectivity, not just static OK
- product endpoint returns JSON, not frontend fallback HTML

2. Inspect the GitHub repo read-only:

```bash
gh repo list OWNER --limit 30 --json nameWithOwner,description,updatedAt,url,visibility
# or clone shallow:
git clone --depth 1 https://github.com/OWNER/REPO.git /tmp/repo
```

Check:
- `docker-compose*.yml`
- `Dockerfile`
- `nginx/default.conf` or proxy config
- `.github/workflows/*`
- `.env.example`
- README/runbook
- server route definitions (`index.js`, API router files, etc.)

## Route mismatch pitfall

If a live endpoint like `/api/products` returns the homepage HTML while `/health` works, do not call the deployment healthy yet. It usually means one of these:

- the backend actually exposes `/products`, not `/api/products`
- CI/runbook checks use the wrong path
- Nginx/frontend fallback is masking API route failures

Coach the user to choose one API style and make repo, CI, docs, and live proxy agree. For a simple Express shop, keeping `/products`, `/featured-products`, and `/health` is acceptable; then CI should check `/products`, not `/api/products`.

## Docker Compose EC2 port mismatch

If local Compose exposes Nginx as `8080:80` but the live EC2 serves on port 80, recommend a production override instead of mutating the local file blindly:

```yaml
# docker-compose.prod.yaml
services:
  nginx:
    ports:
      - "80:80"
```

Run production with:

```bash
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d
```

This preserves local dev ergonomics while making production intent explicit.

## Multi-EC2 Docker warning

Do not recommend two EC2 instances running the full same Compose stack if it includes Postgres/MySQL as a local service. That creates split-brain application data:

```text
EC2-1 -> local DB A
EC2-2 -> local DB B
```

Before real multi-EC2/high availability, move state out of the instances:

```text
ALB -> EC2 app containers only -> shared RDS
uploads/static mutable assets -> S3
```

Static product images baked into the app image are fine temporarily; user/admin uploads need shared storage.

## Recommended next-step ordering after live triage

For a small Dockerized EC2 shop:

1. Fix route/CI/docs mismatches found by live checks.
2. Add a production Compose override for host ports/environment differences.
3. Attach/verify an Elastic IP if pointing DNS directly to one EC2.
4. Point domain DNS to Elastic IP for single-EC2 v1, or to ALB only after multi-instance architecture is ready.
5. Add HTTPS after HTTP/domain resolution works.
6. Move DB to RDS before adding a second EC2 behind an ALB.
7. Add CI/CD image build/deploy after the runtime architecture is stable.

## Coaching boundary

For Hevar-style DevOps reps, default to inspect -> explain -> exact target/snippet -> user applies -> verify. Do not silently patch Docker/Compose/Nginx/CI files unless the user explicitly asks for takeover.
